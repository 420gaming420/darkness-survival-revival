"""Main binary import logic.

Re-imports libcocos2dcpp.so into the Ghidra project via analyzeHeadless.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.logic.server.init.stages.find_ghidra import find_ghidra_install


def reimport_main_binary(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str,
) -> None:
    """Re-import the main binary into the Ghidra project.

    Args:
        binary: Path to libcocos2dcpp.so.
        ghidra_project_dir: Path to the Ghidra project directory.
        project_name: Name of the Ghidra project.
    """
    project_root = Path(ghidra_project_dir).parent.parent.parent
    ghidra_install = find_ghidra_install(project_root)
    analyze_headless = ghidra_install / "support" / "analyzeHeadless"

    cmd = [
        str(analyze_headless),
        str(ghidra_project_dir),
        project_name,
        "-import", str(binary),
        "-processor", "ARM:LE:32:v5t",
        "-cspec", "apcs",
        "-noanalysis",
        "-overwrite",
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
