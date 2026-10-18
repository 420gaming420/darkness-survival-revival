"""ARM32 Android system library prelinking for Ghidra.

Imports all ARM32 Android .so files into the Ghidra project before the main
binary so that their symbols resolve correctly during analysis. Each .so is
imported via ``analyzeHeadless -import -noanalysis``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# ARM32 Android system shared libraries that must be imported into the Ghidra
# project before the main binary so their symbols resolve correctly.
SYSTEM_LIBS = [
    "libandroid.so",
    "libc.so",
    "libdl.so",
    "libEGL.so",
    "libGLESv1_CM.so",
    "libGLESv2.so",
    "libjnigraphics.so",
    "liblog.so",
    "libm.so",
    "libOpenSLES.so",
    "libstdc++.so",
    "libthread_db.so",
    "libz.so",
]


def programs_in_project(ghidra_project_dir: Path, project_name: str) -> set[str]:
    """Return the set of program names currently in the Ghidra project.

    Each imported .so appears as a file named "/<so_name>" in the project root.
    Uses pyghidra's GhidraProject API to list them without spawning analyzeHeadless.

    Args:
        ghidra_project_dir: Path to the parent directory of the Ghidra project.
        project_name: Name of the Ghidra project (e.g. 'ds_offline').

    Returns:
        Set of program names (e.g. {'libc.so', 'liblog.so', ...}).
    """
    from pyghidra import start as _start
    _start()
    from ghidra.base.project import GhidraProject

    proj = GhidraProject.openProject(
        str(ghidra_project_dir), project_name, True
    )
    try:
        names = set()
        for f in proj.getRootFolder().getFiles():
            names.add(f.getName())
        return names
    finally:
        proj.close()


def prelink_system_libs(
    ghidra_project_dir: Path,
    project_name: str = "ds_offline",
    verbose: bool = False,
) -> list[str]:
    """Import all ARM32 system .so files into the Ghidra project before the main binary.

    Each .so is imported via ``analyzeHeadless -import -noanalysis`` so that their
    symbols are available when the main binary is imported and analyzed.

    Before each import, checks whether the program already exists in the project
    (each imported .so appears as a file named "/<lib>.so" in the project root).
    Skips libs that are already present to avoid redundant JVM spawns.

    Args:
        ghidra_project_dir: Path to the Ghidra project directory.
        project_name: Name of the Ghidra project.
        verbose: If True, print each import; if False, suppress output.

    Returns:
        List of library names that were successfully imported (excludes skipped).
    """
    from .find_ghidra import find_ghidra_install, sources_lib_dir
    from .checksum import compute_sha256  # noqa: F401 — used by callers for validation

    sys_libs_dir = sources_lib_dir()
    ghidra_install = find_ghidra_install()
    analyze_headless = ghidra_install / "support" / "analyzeHeadless"

    existing = programs_in_project(ghidra_project_dir, project_name)

    linked: list[str] = []
    capture = None if verbose else subprocess.DEVNULL

    for so_name in SYSTEM_LIBS:
        if so_name in existing:
            continue

        so_path = sys_libs_dir / so_name
        if not so_path.exists():
            print(f"  [prelink] WARNING: {so_name} not found at {so_path}, skipping")
            continue

        cmd = [
            str(analyze_headless),
            str(ghidra_project_dir),
            project_name,
            "-import", str(so_path),
            "-noanalysis",
        ]
        result = subprocess.run(
            cmd,
            stdout=capture,
            stderr=capture,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            linked.append(so_name)
            print(f"  [prelink] Imported: {so_name}")
        else:
            print(f"  [prelink] FAILED to import {so_name} (rc={result.returncode})")

    return linked
