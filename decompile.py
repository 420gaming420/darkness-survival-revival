#!/usr/bin/env python3
"""Thin entry point for function decompilation.

Pure RPC wrapper — all work done by the background server.
Zero pyghidra/JVM code in this file.

Usage:
    python3 decompile.py _ZN7UILayer10networkingEv
    python3 decompile.py 0x4ea584
    python3 decompile.py networking --cfg
    python3 decompile.py dispatchCustomEvent --ref --asm
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))


def main():
    from src.logic.config import cfg
    cfg.binary_path  # validates binary exists before proceeding

    from src.ui.cli import parse_decompile_args

    args = parse_decompile_args()

    if args.debug:
        print(f"[DEBUG] Query: {args.query}")
        print(f"[DEBUG] Modes: cfg={args.cfg} ref={args.ref} asm={args.asm}")

    # All work goes through the server — zero pyghidra in this file.
    # The server handles init, analysis, and auto-export automatically.
    from src.ui.server.client import rpc as server_rpc

    result = server_rpc("decompile", {
        "query": args.query,
        "cfg": args.cfg,
        "ref": args.ref,
        "asm": args.asm,
    })
    if result.get("error"):
        print(f"[ERROR] {result['error']}")
        sys.exit(1)
    print(f"[*] Found: {result['name']} @ {result['address']}")
    print(result["c_code"])
    count = result.get("gettext_count", 0)
    if count and isinstance(count, int) and count > 0:
        print(f"\n// Annotated {count} getText() call(s)")
    if "cfg" in result:
        print(result["cfg"])
    if "refs" in result:
        print(result["refs"])
    if "asm" in result:
        from src.ui.cli import print_header
        print_header("INTERLEAVED ASSEMBLY + DECOMPILED CODE")
        print(result["asm"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted — sending interrupt to server...")
        from src.ui.server.client import shutdown
        shutdown()
        print("[*] Server interrupted. Exiting.")
