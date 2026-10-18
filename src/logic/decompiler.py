"""Function decompilation with getText() annotation.

Orchestrates the full decompile pipeline: find function → decompile → format →
annotate. Re-exports all sub-module symbols for backwards compatibility with
existing imports (e.g. ``from src.logic.decompiler import find_function``).

Public API:
- ``find_function()`` — 5-tier search by hex/name/symbol/substring
- ``create_decompiler()`` — configure DecompInterface with full options
- ``decompile_function()`` — full pipeline: decompile → format → annotate
- ``build_addr_c_code()`` — address→C-code mapping for assembly interleaving
- ``annotate_lines()`` / ``format_c_code()`` / ``build_var_ids()`` — annotation helpers
"""

from __future__ import annotations

# Re-export all symbols from sub-modules for backwards compatibility
from src.logic.function_resolver import find_function, find_similar  # noqa: F401
from src.logic.decompiler_setup import create_decompiler  # noqa: F401
from src.logic.c_code_format import format_c_code  # noqa: F401
from src.logic.annotation import (  # noqa: F401
    annotate_line,
    annotate_lines,
    build_var_ids,
)
from src.logic.addr_c_map import build_addr_c_code  # noqa: F401


def decompile_function(fpa, func, textdata: dict[int, str]):
    """Full decompile pipeline: decompile → format → annotate.

    Args:
        fpa: FlatProgramAPI from an open session.
        func: The Ghidra Function object to decompile.
        textdata: Loaded textdata dictionary.

    Returns:
        Tuple of (formatted_annotated_code_string, found_count).
    """
    from .decompiler_setup import create_decompiler as _create_decompiler
    from .annotation import annotate_lines as _annotate_lines

    di = _create_decompiler(fpa)

    result = di.decompileFunction(func, 60, None)
    if not result or not result.isValid():
        err = result.getErrorMessage() if result else "no result"
        di.dispose()
        raise RuntimeError(f"Decompilation failed: {err}")

    ccode = result.getDecompiledFunction().c  # already multi-line formatted with proper indentation
    di.flushCache()  # required after each decompileFunction call
    di.dispose()

    lines = ccode.split('\n')
    annotated, found_count = _annotate_lines(lines, textdata)

    return "\n".join(annotated), found_count
