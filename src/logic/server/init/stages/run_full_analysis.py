"""Full analysis logic.

Runs FlatProgramAPI.analyzeAll() + markProgramAnalyzed via pyghidra.
All Ghidra imports are deferred inside the function body.
"""

from __future__ import annotations

import time
from pathlib import Path


def run_full_analysis(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str,
) -> float:
    """Run full Ghidra analysis on all programs in the project.

    Args:
        binary: Path to libcocos2dcpp.so.
        ghidra_project_dir: Path to the Ghidra project directory.
        project_name: Name of the Ghidra project.

    Returns:
        Elapsed time in seconds.
    """
    from pyghidra import start as _start
    from pyghidra.core import _setup_project
    from ghidra.program.flatapi import FlatProgramAPI
    from ghidra.program.util import GhidraProgramUtilities

    from src.logic.server.init.stages.import_main_binary import reimport_main_binary

    _start()
    reimport_main_binary(binary, ghidra_project_dir, project_name)

    project, program = _setup_project(
        str(binary),
        project_location=str(ghidra_project_dir),
        project_name=project_name,
        nested_project_location=False,
    )

    should_ask = GhidraProgramUtilities.shouldAskToAnalyze(program)
    if not should_ask:
        print("  [analysis] Already analyzed, skipping.")
        project.save(program)
        project.close()
        return 0.0

    t0 = time.time()
    api = FlatProgramAPI(program)
    api.analyzeAll(program)
    elapsed = time.time() - t0
    print(f"  [analysis] Full analysis complete. ({elapsed:.1f}s)")

    GhidraProgramUtilities.markProgramAnalyzed(program)
    project.save(program)
    project.close()
    return elapsed
