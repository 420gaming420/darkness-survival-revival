#!/usr/bin/env python3
"""Interactive JVM inspector — sends Python code to the running Ghidra server
and prints the result. No need to stop/start the server.

Usage:
    python3 jvm.py                    # interactive REPL
    python3 jvm.py "code here"        # run single expression
    python3 jvm.py --exec "print('hi')"  # run and exit

The code runs inside the JVM session with access to:
  - fpa       : FlatProgramAPI
  - prog      : ProgramDB
  - mem       : Memory
  - listing   : CodeUnitListing
  - func_mgr  : FunctionManager
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))


def run_code(code: str) -> None:
    """Send code to the server and print the result."""
    from src.logic.config import cfg
    cfg.binary_path  # validates binary exists before proceeding

    from src.ui.server.client import rpc

    result = rpc("execute", {"code": code})
    if "error" in result:
        print(f"[ERROR] {result['error']}")
    else:
        output = result["result"]
        # Don't print empty completion messages
        if output not in ("(exec completed)", "(exec completed, no output)"):
            print(output)


def main():
    if len(sys.argv) > 1:
        # Check for --exec flag
        if sys.argv[1] == "--exec":
            if len(sys.argv) < 3:
                print("Usage: jvm.py --exec 'code'")
                sys.exit(1)
            code = " ".join(sys.argv[2:])
        else:
            # Single expression mode
            code = " ".join(sys.argv[1:])
        run_code(code)
        return

    # Interactive REPL mode
    from src.logic.config import cfg
    cfg.binary_path  # validates binary exists before proceeding

    from src.ui.server.client import rpc

    print("[*] Connected to JVM session")
    print("[*] Available: fpa, prog, mem, listing, func_mgr")
    print("[*] Auto-imported: TaskMonitor, AddressSet, SimpleBlockModel, DecompInterface, DecompileOptions")
    print("[*] Type 'help()' or 'dir(fpa)' for info")
    print("[*] Enter code and press Enter. Use 'exit' or Ctrl+D to quit.\n")

    import builtins

    # Build a namespace with convenient shortcuts
    namespace = {}

    while True:
        try:
            user_input = input("jvm> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input.strip():
            continue

        if user_input.strip().lower() in ("exit", "quit", "q"):
            break

        # Try as expression first
        try:
            result = rpc("execute", {"code": user_input})
            if "error" in result:
                print(f"[ERROR] {result['error']}")
                # Show traceback for debugging
                if "Traceback" in result['error']:
                    print("(See full traceback above)")
            else:
                output = result["result"]
                # Don't print empty completion messages
                if output not in ("(exec completed)", "(exec completed, no output)"):
                    print(output)
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
