"""Ghidra server client library.

Pure HTTP/JSON-RPC client — ZERO pyghidra imports, ZERO JVM startup.
The only process that starts a JVM is the server itself.

Strategy for concurrent clients:
  1. Probe /health — if alive, all good.
  2. If dead, each client tries to start its own server in background.
  3. Each client then waits (up to 90s) for /health to respond.
     The FIRST one whose server binds the port will succeed; others will see
     their own server exit immediately (EADDRINUSE) but still wait for the
     winning server's /health.
  4. All clients end up talking to the same single server.

No lock files anywhere.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


_SERVER_SCRIPT = Path(__file__).resolve().parent / "core.py"
_PID_FILE = Path(__file__).resolve().parent.parent.parent / "ghidra_server.pid"
_LOG_FILE = Path(__file__).resolve().parent.parent.parent / "ghidra_server.log"
_PORT = int(os.environ.get("GHIDRA_SERVER_PORT", "18960"))
_DEBUG = os.environ.get("GHIDRA_SERVER_DEBUG", "0") in ("1", "true", "yes")


def _http_get(path: str, timeout: float = 1.0) -> bool:
    """Try to GET a URL. Returns True if HTTP 2xx response received."""
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{_PORT}{path}", timeout=timeout)
        return True
    except Exception:
        return False


def _http_get_json(path: str, timeout: float = 1.0) -> dict | None:
    """Try to GET a URL and parse JSON body. Returns dict or None on failure."""
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{_PORT}{path}", timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def is_server_running() -> bool:
    """Check if the server responds to /health."""
    return _http_get("/health", timeout=1)


def _wait_for_server(max_wait: int = 90) -> bool:
    """Poll /health until it responds or timeout. Returns True on success."""
    for i in range(max_wait):
        if _http_get("/health", timeout=1):
            return True
        time.sleep(1)
    return False


def _wait_for_init(max_wait: int = 600) -> bool:
    """Poll /progress after /health is up, show analysis status until DONE.

    The server responds to /health as soon as the HTTP server starts (before
    analysis begins). This method keeps polling /progress every 2 seconds
    and printing status updates until the server reports 'done'.

    Args:
        max_wait: Maximum seconds to wait for initialization (default: 600 = 10 min).
                  Full analysis can take 15-45 min, so this is generous.

    Returns:
        True if initialization completed successfully, False on timeout/error.
    """
    print("[*] Server is up — waiting for analysis to complete...")

    last_msg = ""
    last_status = ""
    poll_count = 0
    t0 = time.time()

    for i in range(max_wait):
        prog = _http_get_json("/progress", timeout=2)
        if prog is None:
            # Server disappeared — check if it's truly dead or just slow.
            if not _http_get("/health", timeout=5):
                print("[!] Server crashed during initialization.")
                print(f"    Log file: {_LOG_FILE}")
                try:
                    lines = _LOG_FILE.read_text().splitlines()[-30:]
                    print("    Last 30 log lines:")
                    for l in lines:
                        print(f"      {l}")
                except Exception:
                    pass
                return False
            # Health came back but /progress didn't — server is recovering.
            print("[!] Server disappeared, waiting for it to come back...")
            continue

        status = prog.get("analysis_status", "")
        message = prog.get("message", "")
        initialized = prog.get("initialized", False)
        qstatus = prog.get("queue_status", "idle")
        qprogress = prog.get("queue_progress", -1)

        # Show queue status if it's not idle.
        if qstatus != "idle" and qstatus != last_status:
            if qprogress >= 0:
                print(f"[ ] Queue: {qstatus} ({qprogress:.0f}%)")
            else:
                print(f"[ ] Queue: {qstatus}")

        # Only print when status or message changes.
        if status != last_status or message != last_msg:
            last_status = status
            last_msg = message
            poll_count += 1
            is_done = status == "done" or initialized is True
            marker = "[+]" if is_done else "[ ]"
            elapsed = time.time() - t0
            print(f"{marker} {message}")

            if is_done:
                print(f"[+] Server is ready for requests ({elapsed:.0f}s total).")
                return True

        # Progress indicator every 30 seconds.
        if i % 30 == 29:
            elapsed = time.time() - t0
            print(f"    ... still initializing ({elapsed:.0f}s elapsed)")

        time.sleep(2)

    # Timeout reached.
    elapsed = time.time() - t0
    print(f"[!] Initialization timed out after {elapsed:.0f}s.")
    return False


def _ensure_server():
    """Start the server in background if not already running.

    Handles concurrent clients without any lock file:
    - Each client probes /health first. If alive, skips start.
    - All dead clients each fire off their own Popen simultaneously.
    - Only one binds successfully; the rest exit immediately (EADDRINUSE).
    - Every client then waits for /health — the winner's server is up,
      and the losers also succeed because they're waiting for the same port.

    After /health responds, polls /progress to show analysis status until
    initialization completes. This provides continuous feedback during the
    typically long full analysis phase (15-45 minutes).

    Returns:
        True if server is ready, False on failure.
    """
    t0 = time.time()

    env = os.environ.copy()
    env["GHIDRA_SERVER_PORT"] = str(_PORT)
    if _DEBUG:
        env["GHIDRA_SERVER_DEBUG"] = "1"

    # Phase 1: fast path — is server already alive?
    if is_server_running():
        # Even if the server is running, check if it's initialized.
        prog = _http_get_json("/progress", timeout=2)
        if prog and (prog.get("initialized") or prog.get("analysis_status") == "done"):
            elapsed = time.time() - t0
            qstatus = prog.get("queue_status", "idle")
            qprogress = prog.get("queue_progress", -1)
            if qstatus != "idle":
                if qprogress >= 0:
                    print(f"[ ] Queue: {qstatus} ({qprogress:.0f}%) — waiting...")
                else:
                    print(f"[ ] Queue: {qstatus} — waiting...")
            else:
                if _DEBUG:
                    print(f"[client] Server already running and ready ({elapsed:.1f}s).")
            # If busy with an operation, wait for it to finish.
            while qstatus != "idle":
                time.sleep(2)
                prog = _http_get_json("/progress", timeout=2)
                if prog is None:
                    return False
                qstatus = prog.get("queue_status", "idle")
                qprogress = prog.get("queue_progress", -1)
                if qstatus != "idle":
                    if qprogress >= 0:
                        print(f"[ ] Queue: {qstatus} ({qprogress:.0f}%)")
                    else:
                        print(f"[ ] Queue: {qstatus}")
            return True
        # Server is up but not initialized yet — wait for it.
        return _wait_for_init()

    # Phase 1b: check PID file — if a server was recently launched,
    # don't spawn another one even if /health doesn't respond yet.
    if _PID_FILE.exists():
        try:
            old_pid = int(_PID_FILE.read_text().strip())
            os.kill(old_pid, 0)  # Check if process exists (no error = alive).
            # Process is alive but not responding — it may be initializing.
            # Wait briefly for /health to come up instead of spawning a new one.
            print(f"[client] PID {old_pid} exists but not responding, waiting...")
            for _ in range(15):
                time.sleep(1)
                if is_server_running():
                    return _wait_for_init()
            # Still not responding — kill the stale process and fall through.
            os.kill(old_pid, signal.SIGKILL)
        except (ProcessLookupError, ValueError):
            pass  # Process died, fall through to spawn new one

    # Phase 2: each client starts its own copy in background.
    # The first one wins the port; the rest die with EADDRINUSE.
    # Every client then waits for /health — all succeed once the winner is up.
    print("[*] Starting Ghidra server in background...")
    print(f"[*] Server script: {_SERVER_SCRIPT}")
    print(f"[*] Log file: {_LOG_FILE}")
    print(f"[*] Port: {_PORT}")
    print(f"[*] Debug: {_DEBUG}")
    print("[*] Python: " + sys.executable)
    print()

    proc = subprocess.Popen(
        [sys.executable, str(_SERVER_SCRIPT)],
        stdout=open(_LOG_FILE, "a"),
        stderr=open(_LOG_FILE, "a"),
        env=env,
        start_new_session=True,
    )
    _PID_FILE.write_text(str(proc.pid))
    my_pid = proc.pid
    print(f"[*] Launched server process (PID {my_pid})")

    # Quick crash detection: wait 3s to see if the process exits.
    for i in range(6):
        time.sleep(0.5)
        try:
            os.kill(my_pid, 0)
        except ProcessLookupError:
            # Process died — show logs immediately.
            print(f"[!] Server crashed after {i*0.5:.1f}s (PID {my_pid} exited).")
            print(f"    Log file: {_LOG_FILE}")
            try:
                lines = _LOG_FILE.read_text().splitlines()[-30:]
                print("    Last 30 log lines:")
                for l in lines:
                    print(f"      {l}")
            except Exception:
                pass
            return False
        if _http_get("/health", timeout=1):
            break

    # Phase 3: wait for /health. Every client does this — only one actually
    # bound the port, but they all converge on the same server.
    print("[*] Waiting for server to become responsive...")

    for i in range(120):
        if _http_get("/health", timeout=1):
            elapsed = time.time() - t0
            print(f"[+] Server is up after {elapsed:.0f}s (PID {my_pid})")
            # Now wait for analysis to complete.
            return _wait_for_init()
        # Show progress every 15s
        if i % 15 == 14:
            try:
                lines = _LOG_FILE.read_text().splitlines()[-3:]
                print(f"[{i+1}/120] Still starting... (last log lines:)")
                for l in lines:
                    print(f"    {l}")
            except Exception:
                print(f"[{i+1}/120] Still starting...")
        time.sleep(1)

    # Final check
    if _http_get("/health", timeout=1):
        elapsed = time.time() - t0
        print(f"[+] Server is up after {elapsed:.0f}s")
        return _wait_for_init()

    elapsed = time.time() - t0
    print(f"[!] Server not responsive after {elapsed:.0f}s.")
    print(f"    PID was: {my_pid}")
    print(f"    Log file: {_LOG_FILE}")
    try:
        lines = _LOG_FILE.read_text().splitlines()[-30:]
        print("    Last 30 log lines:")
        for l in lines:
            print(f"      {l}")
    except Exception:
        pass
    return False


def rpc(method: str, params: dict | None = None) -> Any:
    """Send a JSON-RPC request to the server and return the result.

    Auto-starts the server if not running. Each call is a separate HTTP request;
    the server queues them internally (single JVM session).

    Args:
        method: RPC method name (e.g. 'decompile', 'export_all').
        params: Request parameters dict, or None.

    Returns:
        The 'result' field from the JSON-RPC response.

    Raises:
        RuntimeError: If the server returns an error.
    """
    import urllib.request

    t0 = time.time()
    _ensure_server()

    payload = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    data = json.dumps(payload).encode("utf-8")

    if _DEBUG:
        print(f"[client] RPC -> {method} (params keys: {list((params or {}).keys())})")

    req = urllib.request.Request(
        f"http://127.0.0.1:{_PORT}/rpc",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        resp = urllib.request.urlopen(req, timeout=None)
        result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        elapsed = time.time() - t0
        raise RuntimeError(f"Server RPC failed for '{method}' after {elapsed:.1f}s: {e}")

    if "error" in result:
        code = result["error"].get("code", "?")
        msg = result["error"].get("message", "?")
        raise RuntimeError(f"Server error ({code}): {msg}")

    elapsed = time.time() - t0
    if _DEBUG:
        print(f"[client] RPC <- {method} OK ({elapsed:.1f}s)")

    return result.get("result")


def shutdown():
    """Gracefully shut down the server.

    Sends /interrupt to cancel any in-flight work, then sends a JSON-RPC
    'shutdown' method to the server, which triggers:
    1. close_project() — releases Ghidra program and closes project (frees JVM/native resources)
    2. self.server.shutdown() — stops the HTTP server (non-blocking, exits serve_forever loop)

    Then sends SIGTERM to the process, waits up to 5s, then SIGKILL if still alive.
    Also kills all child processes (e.g. the JVM/decompile helper).
    Removes the PID file on success.
    """
    import urllib.request

    # Step 1: Interrupt any in-flight work (export, decompile, etc.).
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{_PORT}/interrupt", timeout=2)
    except Exception:
        pass

    # Step 2: Send graceful shutdown request to the server.
    try:
        data = json.dumps({"jsonrpc": "2.0", "method": "shutdown", "id": 0}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{_PORT}/rpc",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        json.loads(resp.read().decode())
    except Exception:
        # Server may already be shutting down or not responding.
        pass

    # Step 3: Wait for the server to finish closing the project and stopping.
    time.sleep(1)

    # Step 4: Kill the process and all its children (belt-and-suspenders).
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            # Kill process group to get children (JVM, decompile helper).
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                os.kill(pid, signal.SIGTERM)
            for _ in range(40):  # Up to 20 seconds of graceful shutdown.
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)  # Check if process still exists (0 = no error = alive).
                except ProcessLookupError:
                    break  # Process exited cleanly.
            else:
                # Still alive after 20s — force kill everything.
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, FileNotFoundError, ValueError):
            pass
        _PID_FILE.unlink()
