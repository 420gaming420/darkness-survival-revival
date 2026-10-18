"""Complete binary analysis via headless analyzer.

Runs full analysis on an already-imported binary in the Ghidra project.
This is a one-time operation per binary — once analyzed, results are cached.
"""

from __future__ import annotations

from pathlib import Path


def run_full_analysis(binary: Path, ghidra_project_dir: Path, project_name: str = "ds_offline") -> None:
    """Run complete analysis on the binary within the Ghidra project.

    Uses the pyghidra API to call FlatProgramAPI.analyzeAll() which runs all
    analyzer plugins (matching GUI "complete analyze").

    Args:
        binary: Path to the binary file.
        ghidra_project_dir: Path to the parent directory of the Ghidra project.
        project_name: Name of the Ghidra project.
    """
    from pyghidra import start as _start
    from pyghidra.core import _setup_project

    _start()

    from ghidra.program.flatapi import FlatProgramAPI
    from ghidra.program.util import GhidraProgramUtilities
    from ghidra.app.script import GhidraScriptUtil

    project, program = _setup_project(
        str(binary),
        project_location=str(ghidra_project_dir),
        project_name=project_name,
        nested_project_location=False,
    )

    should_ask = GhidraProgramUtilities.shouldAskToAnalyze(program)
    if should_ask:
        print("  [analyze] Analyzing...", flush=True)
        api = FlatProgramAPI(program)
        GhidraScriptUtil.acquireBundleHostReference()
        try:
            api.analyzeAll(program)
            GhidraProgramUtilities.markProgramAnalyzed(program)
        finally:
            GhidraScriptUtil.releaseBundleHostReference()
        print("  [analyze] Analysis complete.", flush=True)
    else:
        print("  [analyze] Already analyzed, skipping.", flush=True)

    project.save(program)
    project.close()
