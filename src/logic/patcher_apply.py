"""Patch application logic: in-memory apply, disk write, and function overlap detection.

Provides:
- ``apply_patches_to_memory()`` — write bytes to bytearray (in-memory only)
- ``apply_patches()`` — write to disk + re-import via check_and_reimport
- ``find_affected_functions()`` — find all functions overlapping patch ranges
"""

from __future__ import annotations

from pathlib import Path

from src.logic.patcher.core import Patch


def apply_patches_to_memory(data: bytearray, patches: list[Patch]) -> None:
    """Apply patches to a bytearray in memory (does NOT write to disk).

    Each patch writes its bytes at the specified offset. Patches are applied
    in order; overlapping patches write sequentially.

    Args:
        data: Mutable bytearray of the binary.
        patches: List of Patch objects to apply.
    """
    for patch in patches:
        offset = patch.offset
        new_bytes = list(patch.bytes)
        for i, b in enumerate(new_bytes):
            data[offset + i] = b & 0xff


def find_affected_functions(fpa, patches: list[Patch]) -> list[tuple[int, str]]:
    """Find all functions that overlap with any patch range.

    Args:
        fpa: FlatProgramAPI from an open session (post-patch).
        patches: List of Patch objects (already applied to disk).

    Returns:
        List of (entry_addr_int, func_name) tuples for affected functions.
    """
    prog = fpa.currentProgram
    affected = []
    seen = set()

    for patch in patches:
        patch_start = patch.offset
        patch_end = patch.offset + len(patch.bytes)

        for func in prog.functionManager.getFunctions(True):
            func_start = int(str(func.entryPoint), 16)
            func_end = int(str(func.body.maxAddress), 16)

            # Check if function overlaps with patch range
            if func_start < patch_end and func_end > patch_start:
                if func_start not in seen:
                    seen.add(func_start)
                    affected.append((func_start, func.name))

    affected.sort(key=lambda x: x[0])
    return affected


def apply_patches(
    patches: list[Patch],
    binary: Path | None = None,
    ghidra_project_dir_path: Path | None = None,
    project_name: str = "ds_offline",
    verbose: bool = False,
) -> list[tuple[int, str]]:
    """Apply patches to the binary on disk and re-import into Ghidra.

    Pipeline:
    1. Read binary from disk
    2. Apply all patches to bytearray in memory
    3. Write back to disk (no .bak file)
    4. Check SHA256 and re-import + analyze if changed
    5. Find all functions affected by the patches

    Args:
        patches: List of Patch objects to apply.
        binary: Path to the binary file (default: project's libcocos2dcpp.so).
        ghidra_project_dir_path: Path to Ghidra project dir.
        project_name: Name of the Ghidra project.
        verbose: If True, show import/analysis logs.

    Returns:
        List of (entry_addr_int, func_name) tuples for all affected functions.
    """
    from src.logic.paths import binary_path, ghidra_project_dir
    from src.logic.importer import check_and_reimport

    bin_path = binary or binary_path()
    ghidra_dir = ghidra_project_dir_path or ghidra_project_dir()

    # Read current binary
    data = bytearray(bin_path.read_bytes())

    # Apply patches in memory
    apply_patches_to_memory(data, patches)

    # Write back to disk
    bin_path.write_bytes(bytes(data))

    # Check if binary changed and re-import + analyze if needed
    check_and_reimport(bin_path, ghidra_dir, project_name, verbose=verbose)

    return []
