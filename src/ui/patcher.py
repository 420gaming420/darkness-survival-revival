"""CLI argument parsing for the patcher tool.

Provides argument parser with --debug, --preview, and patch specification
(-r offset hex_bytes). Each -r flag adds one patch.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_hex_bytes(hex_str: str) -> list[int]:
    """Parse a hex string like '02 20 70 47' or '02207047' into list of ints.

    Accepts two formats:
    - Space-separated hex bytes: '02 20 70 47'
    - Continuous hex: '02207047' (parsed as pairs)

    Args:
        hex_str: Hex byte string.

    Returns:
        List of int values (0-255).

    Raises:
        ValueError: If the hex string is invalid.
    """
    # Try space-separated first
    parts = hex_str.split()
    if len(parts) > 1:
        return [int(p, 16) for p in parts]
    
    # Continuous hex string — parse as byte pairs
    h = hex_str.replace("0x", "").replace(" ", "")
    if len(h) % 2 != 0:
        raise ValueError(f"Hex string must have even length (got {len(h)} chars): '{hex_str}'")
    
    return [int(h[i:i+2], 16) for i in range(0, len(h), 2)]


def parse_patcher_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse arguments for the patcher tool.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with fields: debug, preview, show, patches, query, binary.
    """
    parser = argparse.ArgumentParser(
        description="Patch libcocos2dcpp.so and compare decompiled output before/after.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 patcher.py -r 0x3d5d00 02 20 70 47              # single patch\n"
            "  python3 patcher.py -r 0x3d5d00 02207047 --preview        # preview only\n"
            "  python3 patcher.py -r 0x3d5d00 02 20 70 47 -r 0x3d5e98 01 20 70 47 c0 46\n"
            "  python3 patcher.py --show _ZN7UILayer10networkingEv       # show current state\n"
        ),
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable verbose DEBUG: output",
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        default=False,
        help="Preview patches without writing to disk (dry run)",
    )

    parser.add_argument(
        "--show",
        nargs="?",
        const="",
        default=None,
        help="Show current decompiled state of a function. "
             "Accepts address (0x...), mangled name (_ZN...), or demangled name. "
             "If no argument given, also requires --query.",
    )

    parser.add_argument(
        "--binary",
        type=Path,
        default=None,
        help="Use a custom binary path instead of the default",
    )

    # Patch specification: -r offset hex_bytes (can be repeated)
    parser.add_argument(
        "-r",
        "--replace",
        action="append",
        nargs=2,
        metavar=("OFFSET", "HEX_BYTES"),
        help="Patch: write HEX_BYTES at OFFSET. Can be specified multiple times. "
             "HEX_BYTES can be space-separated (02 20 70 47) or continuous (02207047).",
    )

    # Assembly-based patch: -a assembly_string (can be repeated with --at for address)
    parser.add_argument(
        "-a",
        "--patch-asm",
        action="append",
        nargs=2,
        metavar=("AT_OFFSET", "ASSEMBLY_STRING"),
        help="Patch: assemble ASSEMBLY_STRING at OFFSET. Can be specified multiple times. "
             "Example: -a 0x3ac828 \"movs r1, #0xff\" — the assembler converts the string to bytes.",
    )

    # Query for --show mode
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Function query for --show mode (address, mangled name, or demangled name)",
    )

    parser.add_argument(
        "--export",
        action="store_true",
        default=False,
        help="Export patched binary to disk and re-export decompiled/ functions",
    )

    parser.add_argument(
        "--undo",
        type=int,
        nargs="?",
        const=1,
        default=0,
        help="Undo the last N patches (default: 1). Reverts in-memory changes.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        default=False,
        help="Show current patch state: SHA256s, history count, recent patches",
    )

    args = parser.parse_args(argv or sys.argv[1:])

    # Parse patches from -r arguments
    patches = []
    if args.replace:
        for pair in args.replace:
            if len(pair) != 2:
                print(f"[ERROR] Each -r requires exactly 2 arguments: OFFSET HEX_BYTES", file=sys.stderr)
                sys.exit(1)
            try:
                offset = int(pair[0], 16)
            except ValueError:
                print(f"[ERROR] Invalid offset '{pair[0]}': must be hex (e.g., 0x3d5d00)", file=sys.stderr)
                sys.exit(1)
            
            try:
                byte_list = _parse_hex_bytes(pair[1])
            except ValueError as e:
                print(f"[ERROR] Invalid hex bytes '{pair[1]}': {e}", file=sys.stderr)
                sys.exit(1)

            patches.append({
                "offset": offset,
                "bytes": byte_list,
                "name": f"patch@{hex(offset)}",
            })

    args.patches = patches

    # Parse --patch-asm arguments and convert assembly strings to bytes
    asm_patches = []
    if args.patch_asm:
        for pair in args.patch_asm:
            if len(pair) != 2:
                print(f"[ERROR] Each -a requires exactly 2 arguments: OFFSET ASSEMBLY_STRING", file=sys.stderr)
                sys.exit(1)
            try:
                offset = int(pair[0], 16)
            except ValueError:
                print(f"[ERROR] Invalid offset '{pair[0]}': must be hex (e.g., 0x3ac828)", file=sys.stderr)
                sys.exit(1)

            asm_patches.append({
                "offset": offset,
                "asm_string": pair[1],
                "name": f"asm@{hex(offset)}",
            })

    args.asm_patches = asm_patches

    # Handle --show mode
    if args.show is not None:
        query = args.show if args.show else (args.query or "")
        if not query:
            print("[ERROR] --show requires a function address, mangled name, or demangled name", file=sys.stderr)
            print("       Use --show <address_or_name> or --show --query <name>", file=sys.stderr)
            sys.exit(1)
        args.show_query = query
    else:
        args.show_query = None

    return args
