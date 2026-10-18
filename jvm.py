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
        print(result["result"])


def main():
    if len(sys.argv) > 1:
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
            else:
                output = result["result"]
                if output != "(exec completed, no output)":
                    print(output)
        except Exception as e:
            print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()
