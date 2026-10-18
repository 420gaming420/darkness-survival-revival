"""Patcher handlers for RPC requests.

Wraps decompile_function_asm, preview_patches, and apply_patches_to_memory.
Split into two files: show/preview (patcher_show.py) and apply (patcher_apply.py).
"""

from __future__ import annotations


def handle_patcher_show(params: dict) -> dict:
    """Handle 'patcher_show' RPC method. Params: {query}

    Shows the current state of a function with interleaved assembly+C code.
    If patches have been applied, also shows before/after comparison.

    Args:
        params: Request params with 'query'.

    Returns:
        Dict with name, address, asm (interleaved assembly+C code), and optionally
        before_code / after_code for diff comparison.
    """
    from src.logic.patcher_decompile import decompile_function_asm
    from src.logic.paths import textdata_en_path
    from src.logic.strings import load_textdata as _load_td
    from src.logic.server.state_lifecycle import (
        get_binary_sha256,
        get_before_sha256,
        get_fpa,
        get_program,
    )

    fpa = get_fpa()
    prog = get_program()
    query = params["query"]
    textdata = _load_td(textdata_en_path())

    class _Session:
        pass
    _Session.fpa = fpa
    _Session.program = prog

    from src.logic.function_resolver import find_similar as _find_similar, find_function as _find_func
    similar = _find_similar(fpa, query)

    # Resolve the function object to get name/address.
    func_obj = None
    try:
        func_obj = _find_func(fpa, query)
    except ValueError:
        pass

    code = decompile_function_asm(_Session(), query, textdata)
    if code is None:
        error_msg = f"Function '{query}' not found"
        if similar:
            suggestions = ', '.join(sorted(set(n for _, n in similar)[:10]))
            error_msg += f". Did you mean: {suggestions}?"
        return {"name": None, "address": None, "asm": None, "error": error_msg}

    # Derive name/address from the function object.
    name = func_obj.name if func_obj else None
    addr = hex(int(str(func_obj.entryPoint), 16)) if func_obj else None

    result = {"name": name, "address": addr, "asm": code}

    # Add before/after comparison if patches have been applied.
    # Use the stored binary SHA256 (from *.sha256 file) as the versioned folder key.
    # This is the pre-patch state — the .c files in decompiled/<sha8>/ were exported
    # from that exact binary during init (or a previous --export).
    before_sha = get_binary_sha256()
    has_patches = get_before_sha256() != "" and get_before_sha256() != before_sha
    if has_patches:
        try:
            from src.logic.server.patcher_compare import (
                get_before_codelines,
                get_after_codelines,
            )
            from src.logic.paths import decompiled_dir as _get_decompiled

            func_obj = None
            for f in prog.functionManager.getFunctions(True):
                entry = int(str(f.entryPoint), 16)
                if hex(entry) == addr or f.name == name:
                    func_obj = f
                    break
            if func_obj is not None:
                before_codelines = get_before_codelines(before_sha, name or "", _get_decompiled())
                after_codelines = get_after_codelines(func_obj, textdata)
                if before_codelines is not None and after_codelines is not None:
                    result["before_codelines"] = before_codelines
                    result["after_codelines"] = after_codelines
        except Exception:
            pass  # Comparison is optional; ignore errors.

    return result


def handle_patcher_preview(params: dict) -> dict:
    """Handle 'patcher_preview' RPC method. Params: {patches: [{offset, bytes, name?}]}

    Args:
        params: Request params with 'patches` list.

    Returns:
        Dict with preview string showing hex bytes before/after each patch.
    """
    from src.logic.patcher.core import Patch, preview_patches
    from src.logic.paths import binary_path

    patch_objs = [Patch(**p) for p in params["patches"]]
    text = preview_patches(patch_objs, binary_path())
    return {"preview": text}
