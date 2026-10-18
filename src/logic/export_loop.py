"""Bulk function export loop for decompiled output files.

Processes a list of (address_hex, func_name, depth) tuples in a single JVM
session, exporting each function as 4 files (.c, .asm.txt, .cfg.txt, .ref.txt).
"""

from __future__ import annotations

import time
from pathlib import Path


def run_export(
    func_entries: list[tuple[str, str, int]],
    fpa,
    prog,
    di,
    textdata: dict[int, str],
    decompiled_dir: Path,
    max_depth: int | None = None,
    benchmark: bool = False,
    progress_callback=None,
) -> dict:
    """Run the full export loop for a list of functions.

    Single JVM session — all functions processed in one pass with shared
    DecompInterface instance. No progress output (client handles that).

    Args:
        func_entries: List of (entry_addr_hex_str, func_name, depth) tuples.
        fpa: FlatProgramAPI from open session.
        prog: ProgramDB from open session.
        di: DecompInterface (configured, flushed after each call).
        textdata: Loaded textdata dictionary for annotation.
        decompiled_dir: Root output directory path.
        max_depth: Optional depth limit — skip functions deeper than this.
        benchmark: If True, collect per-function timing breakdowns.
        progress_callback: Optional callable(idx, total) for progress updates.

    Returns:
        Dict with keys: total, exported, skipped, errors.
    """
    from src.logic.export_single import export_single_function

    total_funcs = len(func_entries)
    exported = 0
    skipped = 0
    errors = 0
    t0 = time.time()

    for idx, (entry_addr_str, func_name, depth) in enumerate(func_entries):
        if max_depth is not None and depth > max_depth:
            skipped += 1
            continue

        try:
            entry_addr = int(entry_addr_str, 16)
        except ValueError:
            errors += 1
            elapsed = time.time() - t0
            print(f"[  ERR] Invalid address '{entry_addr_str}' for '{func_name}' ({exported}/{total_funcs} done, {elapsed:.0f}s)")
            continue

        success, elapsed_single, err_msg, func_timings = export_single_function(
            fpa=fpa,
            prog=prog,
            di=di,
            textdata=textdata,
            entry_addr=entry_addr,
            func_name=func_name,
            depth=depth,
            decompiled_dir=decompiled_dir,
            benchmark=benchmark,
        )

        if success:
            exported += 1
        else:
            errors += 1
            print(f"[  ERR] {func_name} @ {entry_addr_str}: {err_msg}")

        # Notify progress callback periodically (every 100 functions).
        if progress_callback is not None and idx % 100 == 0:
            try:
                progress_callback(idx, total_funcs)
            except Exception:
                pass

    total_elapsed = time.time() - t0
    rate = (exported / total_elapsed) if total_elapsed > 0 else 0
    print(f"Export complete: {exported}/{total_funcs} exported, {errors} errors, {total_elapsed:.0f}s ({rate:.1f}/s)")

    return {"total": total_funcs, "exported": exported, "skipped": skipped, "errors": errors}
