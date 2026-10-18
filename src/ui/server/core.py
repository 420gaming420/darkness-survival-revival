"""Ghidra JSON-RPC HTTP server with single-JVM lifecycle.

Runs initialization (system lib imports + full analysis) in a background thread.
All RPC requests stall/wait in the queue until analysis completes, then proceed
normally. Provides /progress endpoint for real-time status updates.

ALL LOGGING IS ALWAYS-ON via print(flush=True). Set GHIDRA_SERVER_DEBUG=1 for
extra-deep tracing (full tracebacks on every error, per-request timing).
"""

# Ensure project root is on sys.path when this file is run directly
import os as _os
_project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
if _project_root not in __import__("sys").path:
    __import__("sys").path.insert(0, _project_root)

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path

# ── Debug flag (set GHIDRA_SERVER_DEBUG=1 for extra-deep tracing) ─────────────

DEBUG = os.environ.get("GHIDRA_SERVER_DEBUG", "0") in ("1", "true", "yes")


# ── Dependency checks ────────────────────────────────────────────────────────

def _check_dependencies() -> None:
    """Check required Python dependencies and print helpful errors if missing."""
    errors: list[str] = []

    try:
        import dotenv  # noqa: F401
    except ImportError:
        errors.append(
            "python-dotenv not installed. Install with: pip3 install python-dotenv"
        )

    try:
        import pyghidra  # noqa: F401
    except ImportError:
        errors.append(
            "pyghidra not installed. Install from the bundled Ghidra wheel: "
            "pip3 install <GHIDRA_INSTALL_DIR>/Ghidra/Features/PyGhidra/pypkg/dist/pyghidra"
        )

    # Ghidra installation check (deferred — raised lazily by cfg.ghidra_install_dir)
    try:
        from src.logic.config import cfg as _cfg
        _cfg.ghidra_install_dir  # triggers RuntimeError if missing
    except RuntimeError as e:
        errors.append(str(e))

    # System libs check (deferred — raised lazily by cfg.system_libs_dir)
    try:
        from src.logic.config import cfg as _cfg2
        if not _cfg2.system_libs_skip:
            _cfg2.system_libs_dir  # triggers RuntimeError if missing
    except RuntimeError as e:
        errors.append(str(e))

    if errors:
        print("", flush=True)
        print("=" * 60, flush=True)
        print("ERROR: Missing dependencies for Ghidra server", flush=True)
        print("=" * 60, flush=True)
        for err in errors:
            print(f"  - {err}", flush=True)
        print("", flush=True)
        print("Install requirements: pip3 install -r requirements.txt", flush=True)
        print("Configure Ghidra:      set GHIDRA_INSTALL_DIR in .env", flush=True)
        print("=" * 60, flush=True)
        print("", flush=True)
        sys.exit(1)


_check_dependencies()


def _v(msg):
    """VERBOSE — always printed, no prefix. Every state transition."""
    print(f"[  ] {msg}", flush=True)


def _log(msg):
    """INFO — prefixed with [server]."""
    print(f"[server] {msg}", flush=True)


def _debug(msg):
    """DEBUG — only when GHIDRA_SERVER_DEBUG=1."""
    if not DEBUG:
        return
    print(f"[DEBUG] {msg}", flush=True)


_v("IMPORTS: loading src.logic.paths...")
from src.logic.paths import binary_path, ghidra_project_dir, textdata_en_path

_v("IMPORTS: loading src.logic.server.init...")
from src.logic.server.init import run_initialization

_v("IMPORTS: loading src.logic.server.state...")
from src.logic.server.state import (
    AnalysisStatus,
    get_analysis_status,
    lock,
    wait_for_analysis_done,
)
from src.logic.server.state_lifecycle import (
    close_project,
    get_binary_sha256,
    get_fpa,
    get_program,
    is_initialized,
    open_project,
    set_binary_sha256,
    set_before_sha256,
    set_initialized,
)
from src.logic.server.state import set_analysis_status

_v("IMPORTS: loading handlers...")
from src.logic.server.decompile import handle_decompile
from src.logic.server.export import handle_export_all, handle_export_single
from src.logic.server.patcher_apply import (
    handle_patcher_apply,
    handle_patcher_export,
    handle_patcher_status,
    handle_patcher_undo,
)
from src.logic.server.patcher_show import handle_patcher_preview, handle_patcher_show
from src.logic.server.asm_to_bytes import handle_asm_to_bytes
from src.logic.server.execute import handle_execute
from src.logic.server.rpc import DISPATCH, register_handlers

_v("IMPORTS: registering handlers...")
register_handlers(
    handle_decompile=handle_decompile,
    handle_export_single=handle_export_single,
    handle_export_all=handle_export_all,
    handle_patcher_show=handle_patcher_show,
    handle_patcher_preview=handle_patcher_preview,
    handle_patcher_apply=handle_patcher_apply,
    handle_asm_to_bytes=handle_asm_to_bytes,
    handle_patcher_undo=handle_patcher_undo,
    handle_patcher_export=handle_patcher_export,
    handle_patcher_status=handle_patcher_status,
    handle_status=lambda p: _build_status(),
    handle_execute=handle_execute,
)

_v("IMPORTS: ALL COMPLETE")

_PORT = int(os.environ.get("GHIDRA_SERVER_PORT", "18960"))
_INACTIVITY_TIMEOUT = 5400  # 90 minutes of inactivity before auto-shutdown

# Flag to track whether init thread has been started (per-process).
_init_started = False


def _build_status() -> dict:
    """Build server status response."""
    sha = get_binary_sha256()
    return {
        "initialized": is_initialized(),
        "binary_sha256": sha[:16] + "..." if sha else None,
    }


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_init_started():
    """Start the initialization background thread on first call.

    Only starts once per server lifetime. Subsequent calls are no-ops.
    """
    global _init_started
    if _init_started:
        _v("INIT: already started, skipping")
        return
    _init_started = True

    _log("INIT: starting background initialization thread...")
    _v(f"INIT: binary={binary_path()}")
    _v(f"INIT: ghidra_project_dir={ghidra_project_dir()}")
    _v(f"INIT: project_name=ds_offline")
    libs_dir = binary_path().parent.parent.parent.parent / "sources" / "lib"
    _v(f"INIT: system_libs_dir={libs_dir}")

    t = threading.Thread(
        target=run_initialization,
        args=(binary_path(), ghidra_project_dir(), "ds_offline", libs_dir),
        daemon=True,
        name="init-thread",
    )
    _v("INIT: thread started, waiting...")
    t.start()


def _open_session():
    """Open the Ghidra project and load the program (called after init completes)."""
    _log("SESSION: opening Ghidra project...")
    open_project(ghidra_project_dir(), "ds_offline", "/libcocos2dcpp.so")
    sha = get_binary_sha256() or _sha256(binary_path())
    set_binary_sha256(sha)
    set_initialized(True)
    _log(f"SESSION: opened. Binary SHA256: {sha[:16]}...")


def _execute(method, params):
    """Execute an RPC method inside the JVM session."""
    from src.logic.server.rpc import execute as _exec
    return _exec(method, params)


# ── HTTP Handler ─────────────────────────────────────────────────────────────

class _GhidraRPCHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the JSON-RPC endpoint."""

    def do_GET(self):
        if self.path == "/health":
            _debug("GET /health")
            _v("HANDLER: GET /health -> 200 ok")
            self._send_json(200, {"status": "ok"})
        elif self.path == "/interrupt":
            _debug("GET /interrupt")
            _log("INTERRUPT: export cancelled by client (Ctrl+C)")
            # Force-close the project to kill the JVM session mid-export.
            try:
                close_project()
                set_initialized(False)
                _v("INTERRUPT: project closed forcefully")
            except Exception as e:
                _debug(f"INTERRUPT: error closing project: {e}")
            self._send_json(200, {"interrupted": True})
        elif self.path == "/progress":
            # Trigger init if not yet started — allows /progress polling to
            # kick off the background analysis without needing an RPC call first.
            _ensure_init_started()
            status, message = get_analysis_status()
            resp = {
                "analysis_status": status.value if isinstance(status, AnalysisStatus) else status,
                "message": message,
                "initialized": is_initialized(),
            }
            # If analysis is done but session isn't open yet, open it now.
            # This lets /progress polling itself complete the init flow.
            if status == AnalysisStatus.DONE and not is_initialized():
                with lock():
                    if not is_initialized():
                        _open_session()
                        resp["initialized"] = True
            # Include queue/operation status and export status.
            from src.logic.server.state import get_queue_status as _get_qstatus
            from src.logic.server.export import _exporting as _is_exporting, _export_status as _exp_status
            qstatus, qprogress = _get_qstatus()
            resp["queue_status"] = qstatus
            if qprogress >= 0:
                resp["queue_progress"] = round(qprogress * 100, 1)
            if _is_exporting:
                resp["export_status"] = {"status": "running"}
            elif _exp_status is not None:
                resp["export_status"] = _exp_status
            if not resp["initialized"]:
                resp["waiting_for_init"] = True
                # If init thread hasn't started yet (very first /progress poll),
                # show a brief startup message.
                if status == AnalysisStatus.IDLE and message == "":
                    resp["message"] = "Starting up..."
            _v(f"HANDLER: GET /progress -> 200 {resp}")
            self._send_json(200, resp)
        else:
            _debug(f"GET {self.path} -> 404")
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/rpc":
            _debug(f"POST {self.path} -> 404")
            self._send_json(404, {"error": "Not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            _debug(f"POST /rpc — JSON parse error: {e}")
            self._send_json(400, {"jsonrpc": "2.0", "error": {"code": -32700, "message": f"Invalid JSON: {e}"}, "id": None})
            return

        if isinstance(request, list):
            _debug(f"POST /rpc — batch request ({len(request)} items)")
            results = []
            for req in request:
                try:
                    result = self._process_request(req)
                    results.append(result)
                except Exception as e:
                    _debug(f"  batch item error: {e}")
                    results.append({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": req.get("id")})
            self._send_json(200, results)
            return

        result = self._process_request(request)
        self._send_json(200, result)

    def _process_request(self, request):
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "shutdown":
            _debug("POST /rpc — shutdown requested")
            _v("HANDLER: shutdown requested, starting shutdown thread")
            threading.Thread(target=self._shutdown_server, daemon=True).start()
            return {"jsonrpc": "2.0", "result": True, "id": req_id}

        # Kick off init thread on first real request
        _ensure_init_started()

        _last_request_time[0] = time.time()
        _debug(f"POST /rpc — method={method} params_keys={list(params.keys())}")
        _v(f"HANDLER: processing RPC method={method}")

        # Poll for analysis completion (non-blocking per-request).
        # The init thread sets status to DONE when complete.
        # The handler then opens the JVM session and marks is_initialized=True.
        _log("HANDLER: waiting for initialization to complete...")
        init_done = False
        poll_count = 0
        while not init_done:
            status, msg = get_analysis_status()
            if status == AnalysisStatus.DONE:
                init_done = True
                _v(f"HANDLER: init DONE after {poll_count} polls")
            elif status in (AnalysisStatus.IDLE,) and is_initialized():
                # Already initialized from a previous request
                init_done = True
                _v(f"HANDLER: already initialized")
            else:
                poll_count += 1
                if poll_count % 5 == 0:
                    _log(f"HANDLER: still waiting... (status={status.value}, msg={msg})")
                time.sleep(2)

        # Open the JVM session once analysis is done (only if not already open)
        with lock():
            if not is_initialized():
                _log("HANDLER: opening session after init...")
                _open_session()

        # Auto-export all functions to versioned decompiled/ folder if pending.
        # This runs once per init/re-analysis cycle, right after the JVM session opens.
        from src.logic.server.init import check_and_clear_auto_export_pending
        if check_and_clear_auto_export_pending():
            _log("HANDLER: running auto-export of all functions to versioned decompiled/...")
            try:
                from src.logic.paths import decompiled_dir as _get_decompiled
                from src.logic.server.export_on_complete import export_all_on_complete

                result = export_all_on_complete("all", decompiled_base=_get_decompiled())
                _log(f"HANDLER: Auto-export complete: {result.get('exported', 0)}/{result.get('total', 0)} functions exported")
            except Exception as e:
                import traceback
                _log(f"HANDLER: Auto-export FAILED:\n{traceback.format_exc()}")

        t0 = time.time()
        try:
            response_result = _execute(method, params)
            elapsed = time.time() - t0
            _debug(f"POST /rpc — method={method} done in {elapsed:.3f}s")
            _v(f"HANDLER: RPC {method} succeeded in {elapsed:.1f}s")
            return {"jsonrpc": "2.0", "result": response_result, "id": req_id}
        except Exception as e:
            import traceback
            elapsed = time.time() - t0
            _debug(f"POST /rpc — method={method} FAILED after {elapsed:.3f}s: {e}")
            _v(f"HANDLER: RPC {method} ERROR:\n{traceback.format_exc()}")
            return {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": req_id}

    def _shutdown_server(self):
        """Gracefully shut down the server.

        Closes the Ghidra project first (frees JVM/Ghidra resources), then
        signals the HTTP server to stop serving. Uses a small delay after
        close_project() to ensure all in-flight requests complete before
        the server socket closes.
        """
        _log("SHUTDOWN: shutting down...")

        # Close Ghidra project first (frees JVM/Ghidra native resources).
        try:
            close_project()
            _v("SHUTDOWN: project closed")
        except Exception as e:
            _debug(f"Shutdown error closing project: {e}")

        # Give in-flight requests a moment to complete before stopping the
        # HTTP server. This ensures the socket isn't closed mid-response.
        time.sleep(0.5)

        # HTTPServer.shutdown() is non-blocking when called from another thread.
        # It sets an internal flag that causes serve_forever() to exit on its
        # next loop iteration. We need to call it from the main thread for a
        # clean shutdown, so we do it via the server's own socket.
        try:
            self.server.shutdown()
            _v("SHUTDOWN: server shutdown called")
        except Exception as e:
            _debug(f"Shutdown error stopping server: {e}")

        _log("SHUTDOWN: complete.")

    def _send_json(self, status_code, data):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default HTTP logging unless DEBUG is on."""
        if DEBUG:
            _debug(f"HTTP {format % args}")


# ── Inactivity watchdog ──────────────────────────────────────────────────────

def _inactivity_watchdog():
    """Shut down server after _INACTIVITY_TIMEOUT seconds of no requests. If 0, never auto-shutdown."""
    while True:
        time.sleep(30)
        if _INACTIVITY_TIMEOUT <= 0:
            continue
        elapsed = time.time() - _last_request_time[0]
        if elapsed > _INACTIVITY_TIMEOUT:
            _log(f"WATCHDOG: no requests for {elapsed:.0f}s, shutting down.")
            import urllib.request
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{_PORT}/rpc",
                    data=json.dumps({"jsonrpc": "2.0", "method": "shutdown", "id": 0}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                _debug(f"Watchdog shutdown request failed: {sys.exc_info()[1]}")
            break


_last_request_time = [time.time()]

# ── Main entry point ─────────────────────────────────────────────────────────

def main():
    """Start the Ghidra JSON-RPC server."""
    _log(f"STARTUP: Ghidra RPC server on port {_PORT}")
    _log(f"STARTUP: Project: {ghidra_project_dir()}")
    _log(f"STARTUP: Binary:  {binary_path()}")
    if _INACTIVITY_TIMEOUT <= 0:
        _log("STARTUP: Inactivity timeout: disabled")
    else:
        _log(f"STARTUP: Inactivity timeout: {_INACTIVITY_TIMEOUT}s")
    if DEBUG:
        _log("STARTUP: DEBUG MODE ENABLED")

    watchdog = threading.Thread(target=_inactivity_watchdog, daemon=True)
    watchdog.start()
    _v("STARTUP: watchdog thread started")

    class _ThreadedServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = _ThreadedServer(("127.0.0.1", _PORT), _GhidraRPCHandler)
    _log(f"STARTUP: Listening on http://127.0.0.1:{_PORT}/rpc")
    _v("STARTUP: HTTPServer created, calling serve_forever()")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Interrupted, shutting down...", flush=True)
        close_project()
        server.server_close()
        _log("STOPPED.")


if __name__ == "__main__":
    main()
