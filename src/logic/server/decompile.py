"""Decompile handler for RPC requests.

Wraps find_function + decompile_function from src.logic.decompiler.
"""

from __future__ import annotations

from src.logic.server.state_lifecycle import get_fpa, get_program


def handle_decompile(params: dict) -> dict:
    """Handle 'decompile' RPC method. Params: {query, cfg?, ref?, asm?}

    Args:
        params: Request params with 'query' (required) and optional flags.

    Returns:
        Dict with name, address, c_code, gettext_count, and optionally cfg/refs/asm.
    """
    from src.logic.decompiler import find_function, decompile_function, build_addr_c_code
    from src.logic.cfg import get_cfg_blocks
    from src.logic.cfg_format import format_cfg_output
    from src.logic.callgraph import get_call_refs
    from src.logic.callgraph_format import format_full_refs
    from src.logic.disassembly import get_instructions, format_asm_with_c

    fpa = get_fpa()
    query = params["query"]
    show_cfg = params.get("cfg", False)
    show_ref = params.get("ref", False)
    show_asm = params.get("asm", False)

    try:
        func = find_function(fpa, query)
    except ValueError as e:
        return {"name": None, "address": None, "c_code": "", "gettext_count": 0, "error": str(e)}

    entry_addr = int(str(func.entryPoint), 16)
    result = {"name": func.name, "address": hex(entry_addr)}

    textdata = _load_textdata()
    ccode, found_count = decompile_function(fpa, func, textdata)
    result["c_code"] = ccode
    result["gettext_count"] = found_count

    if show_cfg:
        blocks, cond_branches = get_cfg_blocks(fpa, func)
        result["cfg"] = format_cfg_output(func.name, entry_addr, blocks, cond_branches)

    if show_ref:
        call_refs_to, call_refs_from = get_call_refs(fpa, func)
        result["refs"] = format_full_refs(func.name, entry_addr, call_refs_to, call_refs_from, fpa)

    if show_asm:
        from src.logic.decompiler import create_decompiler
        di_asm = create_decompiler(fpa)
        dec_result = di_asm.decompileFunction(func, 60, None)
        if dec_result and dec_result.isValid():
            addr_c_code = build_addr_c_code(dec_result)
            all_instrs = get_instructions(fpa, func)
            result["asm"] = format_asm_with_c(all_instrs, addr_c_code)
        di_asm.flushCache()
        di_asm.dispose()

    return result


def _load_textdata():
    """Load and cache textdata_en.dat."""
    from src.logic.paths import textdata_en_path
    from src.logic.strings import load_textdata as _load_td

    if not hasattr(_load_textdata, "_cache"):
        _load_textdata._cache = _load_td(textdata_en_path())
    return _load_textdata._cache
