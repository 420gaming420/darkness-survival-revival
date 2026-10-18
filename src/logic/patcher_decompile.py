"""Decompilation wrappers for the patcher tool.

Provides ``decompile_function_text()`` and ``decompile_function_asm()`` —
thin wrappers around the decompiler that return annotated C code or
interleaved assembly+C for use in --show mode.
"""

from __future__ import annotations


def decompile_function_text(session, query: str | int, textdata: dict[int, str]) -> str | None:
    """Decompile a function and return annotated C code as a string.

    Accepts either a hex address (int or hex string like "0x3e5d00"),
    a mangled name (_ZN...), or a demangled name (substring match).

    Args:
        session: Open GhidraSession or object with .fpa attribute.
        query: Function identifier — hex address, mangled name, or demangled name.
        textdata: Loaded textdata dictionary for annotation.

    Returns:
        Annotated decompiled C code string, or None if decompilation failed.
    """
    fpa = session.fpa

    from src.logic.function_resolver import find_function
    from src.logic.decompiler import decompile_function as _decompile

    try:
        func = find_function(fpa, str(query))
    except ValueError:
        return None

    if func is None:
        return None

    try:
        code, _ = _decompile(fpa, func, textdata)
        return code
    except RuntimeError:
        return None


def decompile_function_asm(session, query: str | int, textdata: dict[int, str]) -> str | None:
    """Decompile a function and return interleaved assembly + C code as a string.

    Uses the same --asm mode as decompile.py to show each instruction with its
    corresponding decompiled C line, so addresses are always correct.

    Args:
        session: Open GhidraSession or object with .fpa attribute.
        query: Function identifier — hex address, mangled name, or demangled name.
        textdata: Loaded textdata dictionary for annotation (unused but kept for API compat).

    Returns:
        Interleaved assembly + C code string, or None if decompilation failed.
    """
    fpa = session.fpa

    from src.logic.function_resolver import find_function
    from src.logic.addr_c_map import build_addr_c_code
    from src.logic.decompiler_setup import create_decompiler
    from src.logic.disassembly import get_instructions, format_asm_with_c

    try:
        func = find_function(fpa, str(query))
    except ValueError:
        return None

    if func is None:
        return None

    di = create_decompiler(fpa)
    dec_result = di.decompileFunction(func, 60, None)
    if dec_result and dec_result.isValid():
        addr_c_code = build_addr_c_code(dec_result)
        all_instrs = get_instructions(fpa, func)
        asm_text = format_asm_with_c(all_instrs, addr_c_code)
        di.flushCache()
        di.dispose()
        return asm_text
    else:
        di.dispose()
        return None
