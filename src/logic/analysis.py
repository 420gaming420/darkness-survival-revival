"""Full and incremental binary analysis for Ghidra project.

Runs ``FlatProgramAPI.analyzeAll()`` (full, slow) or ``analyzeChanges()``
(incremental, fast) via pyghidra to re-analyze the imported binary.
The incremental mode requires the project to have been fully analyzed at
least once before; otherwise falls back to full analysis.
"""

from __future__ import annotations

import time
from pathlib import Path


def run_full_analysis(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str,
) -> float:
    """Run full Ghidra analysis on the imported binary.

    Uses pyghidra to call ``FlatProgramAPI.analyzeAll()`` +
    ``GhidraProgramUtilities.markProgramAnalyzed()``.

    Args:
        binary: Path to the binary file.
        ghidra_project_dir: Path to the parent directory of the Ghidra project.
        project_name: Name of the Ghidra project (e.g. 'ds_offline').

    Returns:
        Elapsed time in seconds.
    """
    from pyghidra import start as _start  # noqa: F811
    from pyghidra.core import _setup_project  # noqa: F811

    _start()

    from ghidra.program.flatapi import FlatProgramAPI  # noqa: F811
    from ghidra.program.util import GhidraProgramUtilities  # noqa: F811

    project, program = _setup_project(
        str(binary),
        project_location=str(ghidra_project_dir),
        project_name=project_name,
        nested_project_location=False,
    )

    should_ask = GhidraProgramUtilities.shouldAskToAnalyze(program)
    if not should_ask:
        print("  [analysis] Already analyzed, skipping.", flush=True)
        project.save(program)
        project.close()
        return 0.0

    api = FlatProgramAPI(program)

    t0 = time.time()
    api.analyzeAll(program)
    elapsed = time.time() - t0
    print(f"  [analysis] Full analysis complete. ({round(elapsed, 1)}s)", flush=True)

    GhidraProgramUtilities.markProgramAnalyzed(program)
    project.save(program)
    project.close()
    return elapsed


def run_incremental_analysis(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str,
) -> float:
    """Run incremental (stale-only) Ghidra analysis with full fallback.

    Tries ``analyzeChanges()`` first (fast — only re-processes stale code
    units). If the project has no prior state and incremental fails, falls
    back to ``analyzeAll()`` (full, slow).

    Args:
        binary: Path to the binary file.
        ghidra_project_dir: Path to the parent directory of the Ghidra project.
        project_name: Name of the Ghidra project (e.g. 'ds_offline').

    Returns:
        Elapsed time in seconds.
    """
    from pyghidra import start as _start  # noqa: F811
    from pyghidra.core import _setup_project  # noqa: F811

    _start()

    from ghidra.program.flatapi import FlatProgramAPI  # noqa: F811
    from ghidra.program.util import GhidraProgramUtilities  # noqa: F811

    project, program = _setup_project(
        str(binary),
        project_location=str(ghidra_project_dir),
        project_name=project_name,
        nested_project_location=False,
    )

    should_ask = GhidraProgramUtilities.shouldAskToAnalyze(program)
    if not should_ask:
        print("  [analysis] Already analyzed, skipping.", flush=True)
        project.save(program)
        project.close()
        return 0.0

    api = FlatProgramAPI(program)

    t0 = time.time()
    try:
        print("  [analysis] Running incremental analysis...", flush=True)
        api.analyzeChanges(program)
        elapsed = time.time() - t0
        print(f"  [analysis] Incremental analysis complete. ({round(elapsed, 1)}s)", flush=True)
    except Exception as e:
        print(
            f"  [analysis] Incremental failed ({str(e)[:80]}), falling back to full...",
            flush=True,
        )
        api.analyzeAll(program)
        elapsed = time.time() - t0
        print(f"  [analysis] Full analysis complete. ({round(elapsed, 1)}s)", flush=True)

    GhidraProgramUtilities.markProgramAnalyzed(program)
    project.save(program)
    project.close()
    return elapsed


def has_prior_analysis(ghidra_project_dir: Path, project_name: str) -> bool:
    """Check whether the Ghidra project already has a full analysis saved to disk.

    Opens the project in a lightweight pyghidra session and checks if the program
    metadata indicates it was analyzed (``Analyzed = true``) and has at least some
    instructions.  This is used to decide whether to use incremental ``analyzeChanges``
    (fast, seconds) or full ``analyzeAll`` (slow, minutes).

    Args:
        ghidra_project_dir: Path to the parent directory of the Ghidra project.
        project_name: Name of the Ghidra project (e.g. 'ds_offline').

    Returns:
        True if the project has a prior complete analysis on disk.
    """
    from pyghidra import start as _start  # noqa: F811
    from pyghidra.core import _setup_project  # noqa: F811

    _start()

    from .paths import binary_path as _binary_path  # noqa: F811

    project, program = _setup_project(
        str(_binary_path()),
        project_location=str(ghidra_project_dir),
        project_name=project_name,
        nested_project_location=False,
    )

    try:
        meta = program.metadata
        analyzed_val = meta.get("Analyzed")
        analyzed = analyzed_val is not None and str(analyzed_val) == "true"
        if not analyzed:
            return False
        all_instrs = list(program.listing.getInstructions(True))
        return len(all_instrs) > 0
    finally:
        project.close()
