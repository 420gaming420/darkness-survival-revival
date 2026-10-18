"""CLI argument parsing shared across all tools.

Provides a unified argument parser with --debug support and common options
that both decompile.py and export_func.py inherit from.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def make_parser(description: str) -> argparse.ArgumentParser:
    """Create a base argument parser with common options.

    All tools should start from this parser and add their own specific args.

    Args:
        description: Tool-specific description for --help.

    Returns:
        Configured ArgumentParser with --debug and common flags.
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable verbose DEBUG: output (JVM and tool internals)",
    )
    return parser


def parse_decompile_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse arguments for the decompile tool.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with query, cfg, ref, asm, binary fields.
    """
    parser = make_parser("Decompile a function from the cached Ghidra project.")
    parser.add_argument(
        "query",
        help="Function address (0x...), mangled name (_ZN...), or demangled name",
    )
    parser.add_argument(
        "--cfg",
        action="store_true",
        default=False,
        help="Include control flow graph in output",
    )
    parser.add_argument(
        "--ref",
        action="store_true",
        default=False,
        help="Include call graph references (callers/callees)",
    )
    parser.add_argument(
        "--asm",
        action="store_true",
        default=False,
        help="Show interleaved assembly + decompiled code",
    )
    parser.add_argument(
        "--binary",
        type=Path,
        default=None,
        help="Use a custom binary path instead of the default",
    )

    return parser.parse_args(argv or sys.argv[1:])


def parse_export_args(argv: list[str | None] = None) -> argparse.Namespace:
    """Parse arguments for the export tool.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with all export-related fields.
    """
    parser = make_parser(
        "Export decompiled + disassembly + CFG + refs for functions in libcocos2dcpp.so."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Single function: address (0x...), mangled name (_ZN...), or demangled name",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Export ALL functions in the binary",
    )
    parser.add_argument(
        "--reachable",
        action="store_true",
        default=False,
        help="Export only functions reachable from mainLoop (0x4e6a9c)",
    )
    parser.add_argument(
        "--stale",
        action="store_true",
        default=False,
        help="Re-export stale functions listed in export_stale.csv",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=None,
        help="Only export functions at this BFS depth level",
    )
    parser.add_argument(
        "--benchmark",
        type=int,
        nargs="?",
        const=100,
        default=0,
        help="Sample N functions to estimate full export time (default: 100)",
    )

    return parser.parse_args(argv or sys.argv[1:])


def print_header(title: str) -> None:
    """Print a formatted section header.

    Args:
        title: Header text.
    """
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_footer(exported: int, total: int, skipped: int = 0, errors: int = 0) -> None:
    """Print a summary footer after export completion.

    Args:
        exported: Number of functions successfully exported.
        total: Total number of functions requested.
        skipped: Number of functions skipped (e.g., depth limit).
        errors: Number of functions that failed.
    """
    print()
    print("=" * 72)
    print("  EXPORT COMPLETE")
    print("=" * 72)
    print(f"  Total functions:  {total}")
    print(f"  Exported:         {exported}")
    if skipped > 0:
        print(f"  Skipped (depth):  {skipped}")
    if errors > 0:
        print(f"  Errors:           {errors}")
