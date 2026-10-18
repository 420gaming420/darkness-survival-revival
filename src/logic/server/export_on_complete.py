"""Auto-export decompiled functions after init or on SHA256 change.

When the server finishes initialization, or when the binary changes (patches
applied in-memory), this module exports all functions to versioned subfolders
inside `decompiled/`. Each unique binary SHA256 gets its own immutable snapshot:

    decompiled/
    ├── 22eb7a0b/          ← first run, unpatched binary
    │   ├── _ZN...c.c
    │   └── ...
    └── a1f3c89d/          ← after patches exported to disk

This ensures decompiled/ is always up-to-date and versioned by binary hash.
"""

from __future__ import annotations

import os
from pathlib import Path


def get_versioned_decompiled_dir(sha256_hex: str, decompiled_base: Path) -> Path:
    """Return the versioned decompiled directory for a given SHA256.

    Creates the subfolder if it doesn't exist yet.

    Args:
        sha256_hex: Full SHA256 hex digest of the binary.
        decompiled_base: The decompiled/ directory path.

    Returns:
        Path to the versioned subfolder (e.g. decompiled/22eb7a0b/).
    """
    short = sha256_hex[:8]
    versioned = decompiled_base / short
    versioned.mkdir(parents=True, exist_ok=True)
    return versioned


def export_all_to_versioned(
    func_entries: list[tuple[str, str, int]],
    fpa,
    prog,
    di,
    textdata: dict[int, str],
    decompiled_base: Path,
    sha256_hex: str,
) -> dict:
    """Export all functions to a versioned subfolder.

    Each function gets 4 files (.c, .asm.txt, .cfg.txt, .ref.txt).
    Skips functions already exported in this version (idempotent).

    Args:
        func_entries: List of (hex_addr, func_name, depth) tuples.
        fpa: FlatProgramAPI from the open session.
        prog: ProgramDB instance.
        di: Decompiler interface.
        textdata: Loaded textdata dictionary for annotation.
        decompiled_base: The decompiled/ directory path.
        sha256_hex: Full SHA256 hex digest of the binary.

    Returns:
        Dict with total, exported, skipped counts.
    """
    from src.logic.exporter import run_export

    versioned = get_versioned_decompiled_dir(sha256_hex, decompiled_base)

    # Check which functions are already exported in this version.
    already_exist = set()
    if versioned.exists():
        for f in versioned.iterdir():
            if f.suffix == ".c":
                base = f.stem  # e.g. _ZN7UILayer10networkingEv
                already_exist.add(base)

    # Filter out already-exported functions.
    to_export = []
    skipped = 0
    for addr_str, name, depth in func_entries:
        if name in already_exist:
            skipped += 1
        else:
            to_export.append((addr_str, name, depth))

    if not to_export and not already_exist:
        return {"total": len(func_entries), "exported": 0, "skipped": len(func_entries)}

    # Build entries with actual function objects for run_export.
    from src.logic.server.export_depth import build_func_entries_with_depth

    all_funcs = list(prog.functionManager.getFunctions(True))
    func_map: dict[int, object] = {}
    for f in all_funcs:
        entry = int(str(f.entryPoint), 16)
        func_map[entry] = f

    # Convert to the format run_export expects (addr_str, func_name_string, depth).
    export_entries = []
    for addr_str, name, depth in to_export:
        try:
            addr = fpa.toAddr(addr_str)
            func_obj = fpa.getFunctionAt(addr)
            if func_obj:
                entry_addr = int(str(func_obj.entryPoint), 16)
                export_entries.append((addr_str, func_obj.name, depth))
        except Exception:
            continue

    # Use run_export with a custom decompiled_dir pointing to the versioned folder.
    result = run_export(
        func_entries=export_entries,
        fpa=fpa,
        prog=prog,
        di=di,
        textdata=textdata,
        decompiled_dir=versioned,
    )

    # Merge counts.
    result["total"] = len(func_entries)
    result["skipped"] = skipped + result.get("skipped", 0)
    return result


def export_all_on_complete(
    mode: str = "all",
    decompiled_base: Path | None = None,
) -> dict:
    """Export all functions to a versioned subfolder based on current binary SHA256.

    This is the main entry point called after init completes or after each
    patch export. It gets the current binary SHA256 from state_lifecycle,
    determines the versioned directory, and exports all functions there.

    Args:
        mode: Export mode ('all', 'reachable', etc.) — only 'all' is used here.
        decompiled_base: Override for the decompiled/ directory path.

    Returns:
        Dict with total, exported, skipped counts.
    """
    from src.logic.decompiler import create_decompiler
    from src.logic.paths import decompiled_dir as _get_decompiled, textdata_en_path
    from src.logic.server.export_depth import build_func_entries_with_depth
    from src.logic.server.state_lifecycle import get_binary_sha256, get_fpa, get_program
    from src.logic.strings import load_textdata

    fpa = get_fpa()
    prog = get_program()
    sha256_hex = get_binary_sha256()

    if not sha256_hex:
        # Compute SHA256 from current program memory.
        from src.logic.server.state_lifecycle import compute_program_sha256, set_binary_sha256
        sha256_hex = compute_program_sha256(fpa)
        set_binary_sha256(sha256_hex)

    base = decompiled_base or _get_decompiled()
    entries = build_func_entries_with_depth(mode)
    if not entries:
        return {"total": 0, "exported": 0, "skipped": 0}

    textdata = load_textdata(textdata_en_path())
    di = create_decompiler(fpa)

    try:
        result = export_all_to_versioned(
            func_entries=entries,
            fpa=fpa,
            prog=prog,
            di=di,
            textdata=textdata,
            decompiled_base=base,
            sha256_hex=sha256_hex,
        )
        return result
    finally:
        di.dispose()
