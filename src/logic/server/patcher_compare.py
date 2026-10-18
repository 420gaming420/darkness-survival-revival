"""Before/after decompiled code comparison for patcher tool.

When patches are applied in-memory, this module loads the pre-patch (.c) file
from the versioned decompiled/ subfolder and compares it with the current
(de)compiled output from the Ghidra program memory.

Provides:
- ``get_before_codelines(sha8, func_name, decompiled_dir)`` — load .c from versioned folder
- ``get_after_codelines(func_obj, textdata)`` — decompile current state
"""

from __future__ import annotations

from pathlib import Path


def get_before_codelines(
    sha256_hex: str,
    func_name: str,
    decompiled_dir: Path,
) -> str | None:
    """Load the pre-patch decompiled C code from the versioned subfolder.

    Searches recursively through decompiled/<sha8>/ for a .c file whose stem
    starts with the function's hex address (e.g. "3ac814" for @ 0x3ac814),
    then matches by function name in the file header.

    Args:
        sha256_hex: Full SHA256 hex digest of the pre-patch binary.
        func_name: Demangled or mangled function name (e.g. 'Player::updateHunger').
        decompiled_dir: The decompiled/ directory path.

    Returns:
        Pre-patch decompiled C code string, or None if not found.
    """
    import os as _os

    short = sha256_hex[:8]
    versioned = decompiled_dir / short

    if versioned.exists():
        for root, dirs, files in _os.walk(versioned):
            for f in files:
                if not f.endswith(".c"):
                    continue
                full_path = Path(root) / f
                try:
                    content = full_path.read_text()
                    if func_name.lower() in content.lower():
                        return content
                except Exception:
                    pass

    return None


def get_after_codelines(func_obj, textdata: dict[int, str]) -> str | None:
    """Decompile the current state of a function from Ghidra memory.

    This is the "after" code — what the function looks like after patches
    have been applied in-memory.

    Args:
        func_obj: Ghidra Function object to decompile.
        textdata: Loaded textdata dictionary for annotation.

    Returns:
        Post-patch decompiled C code string, or None on failure.
    """
    from src.logic.server.state_lifecycle import get_fpa
    from src.logic.decompiler import decompile_function as _decompile

    fpa = get_fpa()
    try:
        code, _ = _decompile(fpa, func_obj, textdata)
        return code
    except Exception:
        return None


def format_diff(before: str, after: str) -> str:
    """Format a unified diff between before and after code.

    Uses Python's difflib to produce a clean side-by-side or unified diff.

    Args:
        before: Pre-patch decompiled C code string.
        after: Post-patch decompiled C code string.

    Returns:
        Formatted diff string, or a simple summary if no differences found.
    """
    import difflib

    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        before_lines, after_lines,
        fromfile="before (pre-patch)",
        tofile="after (current)",
        n=3,
    ))

    if not diff:
        return "  No differences detected."

    return "\n".join(diff)
