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
    from src.logic.server.export_depth import build_func_entries_with_depth

    fpa = get_fpa()
    prog = get_program()
    query = params["query"]
    func = find_function(fpa, query)
    entry_addr = int(str(func.entryPoint), 16)

    entries = build_func_entries_with_depth("all")
    depth = 0
    for addr_str, name, d in entries:
        if hex(entry_addr) == addr_str:
            depth = d
            break

    from src.logic.paths import textdata_en_path
    from src.logic.strings import load_textdata as _load_td
    textdata = _load_td(textdata_en_path())

    from src.logic.decompiler import create_decompiler
    di = create_decompiler(fpa)

    # Use versioned folder for this binary's SHA256.
    versioned_dir = _get_versioned_decompiled_dir(fpa)

    success, elapsed, err_msg, timings = export_single_function(
        fpa=fpa, prog=prog, di=di, textdata=textdata,
        entry_addr=entry_addr, func_name=func.name,
        depth=depth, decompiled_dir=versioned_dir,
    )

    return {
        "name": func.name, "address": hex(entry_addr),
        "depth": depth, "exported": success,
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
        try:
            def _progress_cb(idx, total):
                pct = idx / total if total > 0 else 1.0
                set_queue_status("Running --all export", min(pct, 1.0))

            result = run_export(
                func_entries=func_entries, fpa=fpa, prog=prog, di=di,
                textdata=textdata, decompiled_dir=versioned_dir,
                progress_callback=_progress_cb,
            )

            _export_status = result
            return result
        finally:
            di.dispose()
    finally:
        set_queue_status("idle")
        _exporting = False


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
