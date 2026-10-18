"""System library import logic.

Imports ARM32 Android .so files into the Ghidra project via analyzeHeadless.
Each lib is imported with -noanalysis; skips libs already present in the project.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


_SYSTEM_LIBS = [
    "libandroid.so",
    "libc.so",
    "libdl.so",
    "libEGL.so",
    "libGLESv1_CM.so",
    "libGLESv2.so",
    "liblog.so",
    "libm.so",
    "libOpenSLES.so",
    "libstdc++.so",
]


def _get_existing_programs(ghidra_project_dir: Path, project_name: str) -> set[str]:
    """Get set of program names already in the Ghidra project.

    Args:
        ghidra_project_dir: Path to Ghidra project parent directory.
        project_name: Name of the Ghidra project.

    Returns:
        Set of program names (e.g. {'libc.so', 'liblog.so'}).
    """
    from pyghidra import start as _start
    from ghidra.base.project import GhidraProject

    _start()
    gpr_path = Path(ghidra_project_dir) / f"{project_name}.gpr"
    if not gpr_path.exists():
        return set()
    proj = GhidraProject.openProject(
        str(ghidra_project_dir), project_name, True
    )
    try:
        return {f.getName() for f in proj.getRootFolder().getFiles()}
    finally:
        proj.close()


def import_system_libs(
    ghidra_project_dir: Path,
    project_name: str,
    system_libs_dir: Path,
    verbose: bool = False,
) -> list[str]:
    """Import ARM32 system .so files into the Ghidra project.

    Args:
        ghidra_project_dir: Path to the Ghidra project directory.
        project_name: Name of the Ghidra project (e.g. 'ds_offline').
        system_libs_dir: Directory containing ARM32 .so files.
        verbose: If True, print each import; if False, suppress output.

    Returns:
        List of library names that were successfully imported.
    """
    from src.logic.server.init.stages.find_ghidra import find_ghidra_install

    project_root = Path(ghidra_project_dir).parent.parent.parent
    ghidra_install = find_ghidra_install(project_root)
    analyze_headless = ghidra_install / "support" / "analyzeHeadless"

    existing = _get_existing_programs(ghidra_project_dir, project_name)

    linked: list[str] = []
    capture = None if verbose else subprocess.DEVNULL

    for so_name in sorted(_SYSTEM_LIBS):
        if so_name in existing:
            continue

        so_path = system_libs_dir / so_name
        if not so_path.exists():
            print(f"  [import] WARNING: {so_name} not found at {so_path}, skipping")
            continue

        cmd = [
            str(analyze_headless),
            str(ghidra_project_dir),
            project_name,
            "-import", str(so_path),
            "-noanalysis",
        ]
        result = subprocess.run(cmd, stdout=capture, stderr=capture, timeout=120)
        if result.returncode == 0:
            linked.append(so_name)
            print(f"  [import] Imported: {so_name}")
        else:
            print(f"  [import] FAILED to import {so_name} (rc={result.returncode})")

    return linked
