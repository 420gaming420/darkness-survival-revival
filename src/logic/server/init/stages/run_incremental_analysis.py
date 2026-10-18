"""Incremental analysis logic.

Runs analyzeChanges (stale-only) with fallback to full analysis if no prior state exists.
All Ghidra imports are deferred inside the function body.
"""

from __future__ import annotations

import time
from pathlib import Path


def run_incremental_analysis(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str,
) -> float:
    """Run incremental (stale-only) analysis on the project.

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

    _start()

    project, program = _setup_project(
        str(binary),
        project_location=str(ghidra_project_dir),
        project_name=project_name,
        nested_project_location=False,
    )

    should_ask = GhidraProgramUtilities.shouldAskToAnalyze(program)
    if not should_ask:
        print("  [analysis] Already analyzed, skipping.")
        project.close()
        return 0.0

    t0 = time.time()
    api = FlatProgramAPI(program)
    try:
        print("  [analysis] Running incremental analysis...")
        api.analyzeChanges(program)
    except Exception as e:
        print(f"  [analysis] Incremental failed ({e}), falling back to full...")
        api.analyzeAll(program)
    elapsed = time.time() - t0
    print(f"  [analysis] Analysis complete. ({elapsed:.1f}s)")

    GhidraProgramUtilities.markProgramAnalyzed(program)
    project.save(program)
    project.close()
    return elapsed
