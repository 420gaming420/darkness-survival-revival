"""Patcher apply handler for RPC requests.

Applies patches IN-MEMORY (to the Ghidra project's binary copy) using pyghidra's
memory API + Sleigh re-assembly. No disk writes, no re-imports between patches.

Tracks patch history in memory so each patch can be undone by reversing it.

Public API: handle_patcher_apply, handle_patcher_undo, handle_patcher_export
"""

from __future__ import annotations


# Global patch history — each entry is a dict with patch info and original bytes.
# This lives in the server process for the lifetime of the JVM session.
_patch_history: list[dict] = []


def _make_patch_obj(patch_dict: dict) -> dict:
    """Normalize a patch dict to a standard format.

    Args:
        patch_dict: Raw patch dict from RPC params.

    Returns:
        Dict with 'offset' (int), 'bytes' (list[int]), 'name' (str).
    """
    return {
        "offset": int(patch_dict["offset"]),
        "bytes": [b & 0xff for b in patch_dict["bytes"]],
        "name": patch_dict.get("name", ""),
    }


def handle_patcher_apply(params: dict) -> dict:
    """Handle 'patcher_apply' RPC method.

    Applies patches IN-MEMORY to the Ghidra project's binary copy.
    Each patch is written via mem.setByte() and re-parsed by Sleigh.
    The original bytes at each offset are saved to patch history for undo.

    Does NOT write to disk or re-import. Use 'patcher_export' to commit changes.

    Args:
        params: Request params with `patches` list of {offset, bytes, name?}.

    Returns:
        Dict with affected functions, patch_id, and new SHA256 of memory.
    """
    from src.logic.server.state_lifecycle import (
        compute_program_sha256,
        get_before_sha256,
        get_fpa,
        get_program,
        patch_in_memory,
        set_before_sha256,
    )

    patches = [_make_patch_obj(p) for p in params["patches"]]
    fpa = get_fpa()
    prog = get_program()

    # Save current SHA256 as "before" before applying patches.
    old_sha = compute_program_sha256(fpa)
    set_before_sha256(old_sha)

    # Record original bytes for each patch (for undo).
    mem = prog.getMemory()
    # Capture the current "before" SHA so we can restore it after undo.
    prev_before = get_before_sha256()

    history_entry = {
        "patches": [],
        "sha_before": old_sha,
        "sha_after": None,
        "prev_before_sha": prev_before,
    }

    for patch in patches:
        offset = patch["original_offset"] if "original_offset" in patch else patch["offset"]
        length = len(patch["bytes"])
        # Read original bytes from memory.
        orig_bytes = []
        for i in range(length):
            jbyte = mem.getByte(fpa.toAddr(offset + i))
            orig_bytes.append(jbyte if jbyte >= 0 else jbyte + 256)
        history_entry["patches"].append({
            "offset": offset,
            "original_bytes": orig_bytes,
            "new_bytes": patch["bytes"],
            "name": patch.get("name", ""),
        })

    # Apply patches in-memory.
    patch_in_memory(fpa, patches)

    # Find all functions affected by the patches.
    affected = []
    seen = set()
    all_funcs = list(prog.functionManager.getFunctions(True))

    for patch in patches:
        offset = patch["offset"]
        length = len(patch["bytes"])
        start_addr = fpa.toAddr(offset)
        end_addr = fpa.toAddr(offset + length - 1)

        for f in all_funcs:
            func_start = int(str(f.entryPoint), 16)
            func_end = int(str(f.body.maxAddress), 16)
            if func_start <= int(str(end_addr), 16) and func_end >= int(str(start_addr), 16):
                if func_start not in seen:
                    seen.add(func_start)
                    affected.append({"address": hex(func_start), "name": f.name})

    affected.sort(key=lambda x: int(x["address"][2:], 16))

    new_sha = compute_program_sha256(fpa)
    history_entry["sha_after"] = new_sha

    # Append to global patch history.
    _patch_history.append(history_entry)

    return {
        "affected": affected,
        "patch_id": len(_patch_history),
        "new_sha256": new_sha,
        "before_sha256": old_sha,
    }


def handle_patcher_undo(params: dict) -> dict:
    """Handle 'patcher_undo' RPC method.

    Undoes the last N patches (default 1) by restoring original bytes in-memory.
    Each undo is itself recorded in patch history for potential re-undo.

    Args:
        params: Request params with 'count' (int, number of patches to undo). Default 1.

    Returns:
        Dict with undone count, affected functions, and new SHA256.
    """
    from src.logic.server.state_lifecycle import (
        get_fpa,
        get_program,
        set_before_sha256,
        compute_program_sha256,
    )

    count = params.get("count", 1)
    fpa = get_fpa()
    prog = get_program()
    mem = prog.getMemory()

    if not _patch_history:
        return {"undone": 0, "affected": [], "new_sha256": "", "error": "No patch history to undo"}

    undone = []
    affected = []
    seen = set()

    # Pop up to `count` patches from the end of history.
    for _ in range(min(count, len(_patch_history))):
        entry = _patch_history.pop()
        old_sha = compute_program_sha256(fpa)

        for p in entry["patches"]:
            offset = p["offset"]
            orig_bytes = p["original_bytes"]
            length = len(orig_bytes)

            # Write original bytes back to memory.
            for i, b in enumerate(orig_bytes):
                jbyte = b if b < 128 else b - 256
                mem.setByte(fpa.toAddr(offset + i), jbyte)

            undone.append({
                "offset": hex(offset),
                "restored_from": p["new_bytes"],
                "restored_to": orig_bytes,
                "name": p.get("name", ""),
            })

        # Restore the "before" SHA to what it was before this patch was applied.
        prev_before = entry.get("prev_before_sha", "")
        set_before_sha256(prev_before)

        # Find affected functions.
        for p in entry["patches"]:
            offset = p["offset"]
            length = len(p["original_bytes"])
            start_addr = fpa.toAddr(offset)
            end_addr = fpa.toAddr(offset + length - 1)
            for f in prog.functionManager.getFunctions(True):
                func_start = int(str(f.entryPoint), 16)
                func_end = int(str(f.body.maxAddress), 16)
                if func_start <= int(str(end_addr)) and func_end >= int(str(start_addr)):
                    if func_start not in seen:
                        seen.add(func_start)
                        affected.append({"address": hex(func_start), "name": f.name})

    affected.sort(key=lambda x: int(x["address"][2:], 16))
    set_before_sha256(compute_program_sha256(fpa))

    return {
        "undone": len(undone),
        "undo_details": undone,
        "affected": affected,
        "new_sha256": compute_program_sha256(fpa),
    }


def handle_patcher_export(params: dict) -> dict:
    """Handle 'patcher_export' RPC method.

    Writes the patched in-memory binary back to disk (project/lib/armeabi/),
    then re-exports all decompiled functions to a new versioned subfolder.

    This is the ONLY operation that touches disk and triggers analysis.
    Use it when you're done patching and want to commit changes.

    Args:
        params: Empty dict (no parameters needed).

    Returns:
        Dict with written_to, sha256, exported_count.
    """
    import hashlib
    from src.logic.server.state_lifecycle import get_fpa, get_program, read_program_memory_as_bytes
    from src.logic.paths import binary_path, decompiled_dir as _get_decompiled, textdata_en_path
    from src.logic.server.export_on_complete import export_all_on_complete
    from src.logic.server.state import set_analysis_status, AnalysisStatus
    from src.logic.strings import load_textdata
    from src.logic.decompiler import create_decompiler

    fpa = get_fpa()
    prog = get_program()

    # Step 1: Read program memory and write to disk.
    data = read_program_memory_as_bytes(fpa)
    bin_path = binary_path()
    bin_path.write_bytes(data)

    new_sha = hashlib.sha256(data).hexdigest()
    from src.logic.server.state_lifecycle import set_binary_sha256, set_before_sha256
    set_binary_sha256(new_sha)
    set_before_sha256("")  # Reset before SHA after export (disk now matches memory)

    # Step 2: Re-export decompiled functions to new versioned subfolder (skip if exists).
    base = _get_decompiled()
    short_sha = new_sha[:8]
    versioned_dir = base / short_sha

    if not versioned_dir.exists():
        result = export_all_on_complete("all", decompiled_base=base)
        exported_count = result.get("exported", 0)
        total_count = result.get("total", 0)
        skip_reason = None
    else:
        exported_count = 0
        total_count = 0
        skip_reason = f"decompiled/{short_sha}/ already exists (skipping)"

    return {
        "written_to": str(bin_path),
        "sha256": new_sha,
        "exported": exported_count,
        "total": total_count,
        "skip_reason": skip_reason,
    }


def handle_patcher_status(params: dict) -> dict:
    """Handle 'patcher_status' RPC method.

    Returns current patching state: SHA256s, history length, etc.

    Args:
        params: Empty dict.

    Returns:
        Dict with current_sha, before_sha, history_count, history entries (last 10).
    """
    from src.logic.server.state_lifecycle import get_binary_sha256, get_before_sha256

    return {
        "current_sha256": get_binary_sha256(),
        "before_sha256": get_before_sha256(),
        "history_count": len(_patch_history),
        "last_patches": _patch_history[-10:] if _patch_history else [],
    }
