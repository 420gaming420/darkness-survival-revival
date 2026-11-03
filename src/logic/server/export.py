"""Export handlers for RPC requests.

Wraps export_single_function and run_export from src.logic.exporter.
Uses build_func_entries_with_depth from src.logic.server.export_depth.
"""

from __future__ import annotations

from pathlib import Path


def _get_versioned_decompiled_dir(fpa) -> Path:
    """Get the versioned decompiled directory for the current binary SHA256.

    If no SHA256 is set in state, compute it from the program memory.
    Creates the folder if it doesn't exist.

    Args:
        fpa: FlatProgramAPI from the open session.

    Returns:
        Path to the versioned subfolder.
    """
    from src.logic.server.state_lifecycle import (
        compute_program_sha256,
        get_binary_sha256,
        get_versioned_decompiled_dir as _gvd,
    )

    sha = get_binary_sha256()
    if not sha:
        # Compute SHA256 from current program memory.
        sha = compute_program_sha256(fpa)
        from src.logic.server.state_lifecycle import set_binary_sha256
        set_binary_sha256(sha)
    return _gvd(sha)


def handle_export_single(params: dict) -> dict:
    """Handle 'export_single' RPC method. Params: {query}

    Args:
        params: Request params with 'query'.

    Returns:
        Dict with name, address, depth, exported status, elapsed time.
    """
    from src.logic.decompiler import find_function
    from src.logic.exporter import export_single_function
    from src.logic.paths import decompiled_dir as _flat_decompiled

    from src.logic.server.state_lifecycle import get_fpa, get_program
    from src.logic.server.export_depth import build_func_entries_with_depth, _get_category

    fpa = get_fpa()
    prog = get_program()
    query = params["query"]
    func = find_function(fpa, query)
    entry_addr = int(str(func.entryPoint), 16)

    from src.logic.paths import textdata_en_path
    from src.logic.strings import load_textdata as _load_td
    textdata = _load_td(textdata_en_path())

    from src.logic.decompiler import create_decompiler
    di = create_decompiler(fpa)

    # Use versioned folder for this binary's SHA256.
    versioned_dir = _get_versioned_decompiled_dir(fpa)

    category = _get_category(func)
    # Build O(1) symbol cache so make_filename uses mangled Label names.
    symbol_cache = _build_symbol_cache(fpa, prog)
    success, elapsed, err_msg, timings = export_single_function(
        fpa=fpa, prog=prog, di=di, textdata=textdata,
        entry_addr=entry_addr, func_name=func.name,
        depth=0, category=category, decompiled_dir=versioned_dir,
        symbol_cache=symbol_cache,
    )

    return {
        "name": func.name, "address": hex(entry_addr),
        "depth": 0, "category": category, "exported": success,
        "elapsed": round(elapsed, 3), "error": err_msg if not success else None,
    }


_exporting = False
_export_status = None


def _do_export_all(mode: str, fpa, prog, textdata):
    """Run the full export loop (called from a background thread)."""
    global _exporting, _export_status
    from src.logic.exporter import run_export
    from src.logic.server.state import set_queue_status

    _exporting = True
    try:
        func_entries = __import__("src.logic.server.export_depth", fromlist=["build_func_entries_with_depth"]).build_func_entries_with_depth(mode)
        if not func_entries:
            _export_status = {"total": 0, "exported": 0, "skipped": 0, "errors": 0}
            set_queue_status("idle")
            return _export_status

        # Set queue status before starting.
        total_funcs = len(func_entries)
        set_queue_status("Running --all export", 0.0)

        versioned_dir = _get_versioned_decompiled_dir(fpa)
        from src.logic.decompiler import create_decompiler
        di = create_decompiler(fpa)

        # Build O(1) symbol lookup cache once (avoids 329K iteration per function).
        symbol_cache = _build_symbol_cache(fpa, prog)

        try:
            def _progress_cb(idx, total):
                pct = idx / total if total > 0 else 1.0
                set_queue_status("Running --all export", min(pct, 1.0))

            result = run_export(
                func_entries=func_entries, fpa=fpa, prog=prog, di=di,
                textdata=textdata, decompiled_dir=versioned_dir,
                progress_callback=_progress_cb,
                symbol_cache=symbol_cache,
            )

            _export_status = result
            return result
        finally:
            di.dispose()
    finally:
        set_queue_status("idle")
        _exporting = False


def _build_symbol_cache(fpa, prog) -> dict[int, str]:
    """Build O(1) address→mangled-name cache from the symbol table.

    Called once before the export loop. Returns a dict mapping int
    address to the mangled Label name (preferred) or demangled name.
    """
    from src.logic.export_filename import build_symbol_cache as _bsc
    return _bsc(fpa, prog)


def handle_export_benchmark(params: dict) -> dict:
    """Handle 'export_benchmark' RPC method.

    Exports a sample of N functions with full per-step timing.
    Writes files to a temp subdirectory under the versioned SHA dir.

    Args:
        params: Request params with 'count' (int) and optional 'mode' (str).

    Returns:
        Dict with 'count', 'mode', 'results' (list of per-function timing dicts).
    """
    import shutil

    from src.logic.exporter import export_single_function
    from src.logic.paths import textdata_en_path
    from src.logic.strings import load_textdata as _load_td
    from src.logic.server.export_depth import build_func_entries_with_depth, _get_category
    from src.logic.server.state_lifecycle import get_fpa, get_program
    from src.logic.decompiler import create_decompiler

    count = params.get("count", 10)
    mode = params.get("mode", "all")

    fpa = get_fpa()
    prog = get_program()
    textdata = _load_td(textdata_en_path())
    di = create_decompiler(fpa)
    versioned_dir = _get_versioned_decompiled_dir(fpa)

    # Build O(1) symbol lookup cache once (avoids 329K iteration per function).
    symbol_cache = _build_symbol_cache(fpa, prog)

    # Create a temp subdirectory so benchmark files don't pollute the real export.
    tmp_dir = versioned_dir / "_benchmark_tmp"
    tmp_dir.mkdir(exist_ok=True)

    func_entries = build_func_entries_with_depth(mode)
    sample = func_entries[:count]

    results = []
    for entry_addr_str, func_name, depth, category in sample:
        try:
            entry_addr = int(entry_addr_str, 16)
        except ValueError:
            continue

        cat = _get_category(fpa.getFunctionAt(fpa.toAddr(hex(entry_addr))))
        success, elapsed, err_msg, timings = export_single_function(
            fpa=fpa, prog=prog, di=di, textdata=textdata,
            entry_addr=entry_addr, func_name=func_name,
            depth=depth, category=cat, decompiled_dir=tmp_dir,
            benchmark=True,
            symbol_cache=symbol_cache,
        )
        results.append({
            "name": func_name,
            "address": hex(entry_addr),
            "category": cat,
            "success": success,
            "error": err_msg if err_msg else None,
            "timings": timings if timings else {},
        })

    shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "count": len(results),
        "mode": mode,
        "results": results,
    }


def handle_export_all(params: dict) -> dict:
    """Handle 'export_all' / 'export_reachable' / 'export_stale') RPC methods.

    Fires the export in a background thread and returns immediately so the
    HTTP endpoint stays free for other requests (health, interrupt, etc.).

    Args:
        params: Request params with 'mode' (all/reachable/stale).

    Returns:
        Dict with status 'accepted' or 'busy'.
    """
    from src.logic.server.state_lifecycle import get_fpa, get_program

    if _exporting:
        return {"status": "busy", "message": "Export already in progress"}

    fpa = get_fpa()
    prog = get_program()
    mode = params.get("mode", "all")

    from src.logic.paths import textdata_en_path
    from src.logic.strings import load_textdata as _load_td

    textdata = _load_td(textdata_en_path())

    import threading
    t = threading.Thread(
        target=_do_export_all,
        args=(mode, fpa, prog, textdata),
        daemon=True,
    )
    t.start()
    return {"status": "accepted", "message": "Export started"}
