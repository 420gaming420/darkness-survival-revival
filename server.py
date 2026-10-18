#!/usr/bin/env python3
"""Thin entry point for managing the Ghidra background server.

Usage:
    python3 server.py status          # Show server state, analysis progress, patch info
    python3 server.py start           # Start server in background (if not running)
    python3 server.py stop            # Gracefully shut down the server
    python3 server.py restart         # Stop then start the server
    python3 server.py logs [LINES]    # Show last N log lines (default: 20)
    python3 server.py wait            # Wait for analysis to complete, then return

Examples:
    python3 server.py status          # Quick status check
    python3 server.py stop            # Clean shutdown before deleting project
    python3 server.py restart         # Restart the server (stop + start)
    python3 server.py logs 50         # Last 50 lines of server log
    python3 server.py wait            # Block until server is ready for requests
"""

import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))


def _get_log_path():
    """Return the path to the server log file.

    The client writes to src/ghidra_server.log (same dir as this script's parent).
    """
    return _PROJECT_ROOT / "src" / "ghidra_server.log"


def cmd_status():
    """Show server status: running state, analysis progress, patch info."""
    from src.ui.server.client import is_server_running

    print("[*] Server status:")

    if not is_server_running():
        print("  Status:   NOT RUNNING")
        print("  PID:      (none)")
        print()
        print("  Start the server with: python3 server.py start")
        return

    # Server is running — get detailed status.
    from src.ui.server.client import rpc as server_rpc

    try:
        import json
        import urllib.request
        resp = urllib.request.urlopen(f"http://127.0.0.1:18960/progress", timeout=3)
        prog = json.loads(resp.read().decode())
    except Exception:
        print("  ERROR: Could not reach server /progress endpoint.")
        return

    status = prog.get("analysis_status", "unknown")
    message = prog.get("message", "")
    initialized = prog.get("initialized", False)

    if status == "done" or initialized is True:
        print("  Status:   RUNNING (ready)")
    else:
        print(f"  Status:   RUNNING ({status})")
        print(f"  Message:  {message}")

    # Show queue/operation status.
    qstatus, qprogress = prog.get("queue_status", "idle"), prog.get("queue_progress", -1)
    if qstatus != "idle":
        if qprogress >= 0:
            print(f"  Queue:    {qstatus} ({qprogress:.0f}%)")
        else:
            print(f"  Queue:    {qstatus}")

    # Get patcher state.
    try:
        patch_state = server_rpc("patcher_status", {})
        current_sha = patch_state.get("current_sha256", "")
        before_sha = patch_state.get("before_sha256", "")
        history_count = patch_state.get("history_count", 0)

        if current_sha:
            print(f"  SHA256:   {current_sha[:16]}...")
        else:
            print("  SHA256:   (none)")
        if before_sha and before_sha != current_sha:
            print(f"  Before:   {before_sha[:16]}... (patches applied, not yet exported)")
        elif before_sha == current_sha:
            print("  Before:   (same as current — no unexported patches)")
        else:
            print("  Before:   (none — unpatched)")
        print(f"  Patches:  {history_count} in history")

        # Show last few patch entries.
        for entry in patch_state.get("last_patches", [])[-3:]:
            sha_b = (entry.get("sha_before", "") or "")[:16] or "?"
            sha_a = (entry.get("sha_after", "") or "")[:16] or "?"
            patches = entry.get("patches", [])
            n_bytes = sum(len(p.get("original_bytes", [])) for p in patches)
            print(f"    Patch #{entry.get('patch_id', '?')}: {sha_b}... -> {sha_a} ({n_bytes} byte(s) changed)")
    except Exception as e:
        print(f"  Patcher:  ERROR - {e}")


def _check_python_deps():
    """Check Python dependencies and binary existence before starting the server."""
    errors = []
    try:
        import dotenv  # noqa: F401
    except ImportError:
        errors.append("python-dotenv not installed. Install with: pip3 install python-dotenv")
    try:
        import pyghidra  # noqa: F401
    except ImportError:
        errors.append(
            "pyghidra not installed. Install from the bundled Ghidra wheel: "
            "pip3 install <GHIDRA_INSTALL_DIR>/Ghidra/Features/PyGhidra/pypkg/dist/pyghidra"
        )
    try:
        from src.logic.config import cfg
        cfg.binary_path  # triggers RuntimeError if binary missing
    except RuntimeError as e:
        errors.append(str(e))
    try:
        from src.logic.config import cfg
        if not cfg.system_libs_skip:
            cfg.system_libs_dir  # triggers RuntimeError if missing
    except RuntimeError as e:
        errors.append(str(e))
    if errors:
        print("")
        print("=" * 60)
        print("ERROR: Missing dependencies or required files")
        print("=" * 60)
        for err in errors:
            print(f"  - {err}")
        print("")
        print("Install requirements: pip3 install -r requirements.txt")
        print("=" * 60)
        print("")
        sys.exit(1)


def cmd_start():
    """Start the server in background (if not already running)."""
    _check_python_deps()
    from src.ui.server.client import _ensure_server, is_server_running

    if is_server_running():
        print("[*] Server is already running.")
        return

    # Start it. The client will show progress during init.
    _ensure_server()
    print("[+] Server started (or already running).")


def cmd_stop():
    """Gracefully shut down the server."""
    from src.ui.server.client import shutdown, is_server_running

    if not is_server_running():
        print("[*] Server is not running.")
        return

    print("[*] Shutting down server...")
    shutdown()
    # Wait for the port to be fully released (belt-and-suspenders).
    from src.ui.server.client import _http_get
    for _ in range(10):
        time.sleep(0.5)
        if not _http_get("/health"):
            break
    print("[+] Server stopped.")


def cmd_restart():
    """Gracefully restart the server (stop then start)."""
    _check_python_deps()
    from src.ui.server.client import shutdown, is_server_running

    if is_server_running():
        print("[*] Stopping server...")
        shutdown()
        # Wait for port to be fully released.
        from src.ui.server.client import _http_get
        for _ in range(10):
            time.sleep(0.5)
            if not _http_get("/health"):
                break
        print("[+] Server stopped.")
    else:
        print("[*] Server is not running.")

    # Clear old log file on restart for a clean slate.
    log_path = _get_log_path()
    if log_path.exists():
        log_path.write_text("")

    print("[*] Starting server...")
    from src.ui.server.client import _ensure_server
    _ensure_server()
    print("[+] Server started (or already running).")


def cmd_logs(n: int = 20):
    """Show the last N lines of the server log file."""
    log_path = _get_log_path()
    if not log_path.exists():
        print(f"[*] Log file not found: {log_path}")
        return

    lines = log_path.read_text().splitlines()
    tail = lines[-n:]
    for line in tail:
        print(line)


def cmd_wait():
    """Wait for the server to finish initializing and become ready."""
    from src.ui.server.client import _wait_for_server, _wait_for_init

    if not _wait_for_server(30):
        print("[!] Server did not start within 30s.")
        return

    _wait_for_init()


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    command = args[0]

    if command == "status":
        cmd_status()
    elif command == "start":
        cmd_start()
    elif command == "stop":
        cmd_stop()
    elif command == "logs":
        n = int(args[1]) if len(args) > 1 else 20
        cmd_logs(n)
    elif command == "restart":
        cmd_restart()
    elif command == "wait":
        cmd_wait()
    else:
        print(f"[ERROR] Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
