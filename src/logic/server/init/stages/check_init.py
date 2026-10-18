"""Project existence checker.

Determines if a fresh init or re-analysis is needed.
"""

from __future__ import annotations

from pathlib import Path


def needs_full_init(ghidra_project_dir: Path, project_name: str, binary_path: Path | None = None) -> bool:
    """Check if the Ghidra project needs a full initialization.

    Args:
        ghidra_project_dir: Path to the Ghidra project directory.
        project_name: Name of the Ghidra project.

    Returns:
        True if full init is needed, False if project already has programs.
    """
    from pyghidra import start as _start

    _start()

    gpr_path = Path(ghidra_project_dir) / f"{project_name}.gpr"
    if not gpr_path.exists():
        return True

    try:
        from ghidra.base.project import GhidraProject

        gp = GhidraProject.openProject(
            str(ghidra_project_dir), project_name, True
        )
        try:
            files = list(gp.getRootFolder().getFiles())
            # Check if the main binary is present in the project
            binary_name = binary_path.name if binary_path else "libcocos2dcpp.so"
            has_binary = any(f.getName() == binary_name for f in files)
            return len(files) == 0 or not has_binary
        finally:
            gp.close()
    except Exception:
        return True
