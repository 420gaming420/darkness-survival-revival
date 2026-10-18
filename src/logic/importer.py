"""Binary re-import and full analysis into Ghidra project.

Orchestrates the pipeline:
1. SHA256 checksum comparison (``checksum`` module)
2. Pre-link ARM32 system libs (``system_libs`` module)
3. Re-import main binary via ``analyzeHeadless -import -noanalysis -overwrite``
4. Run full or incremental analysis (``analysis`` module)
5. Save new checksum so subsequent runs skip re-import

This ensures the Ghidra project always has the latest binary with full
analysis, so decompilation is accurate and jumptables are resolved.

Public API: ``check_and_reimport()`` — the main entry point called by all tool
entry points (decompile.py, export.py, patcher.py) before each RPC call.
"""

from __future__ import annotations

import time as _time
from pathlib import Path

# Module-level imports for use by reimport_binary and _reimport_binary.
# These are imported lazily inside check_and_reimport too, but need to be
# available at module level for the other functions that call them.
_prelink = None
_run_full = None
_run_incr = None


def _ensure_imports():
    """Lazy-import all dependencies on first use."""
    global _prelink, _run_full, _run_incr
    if _prelink is not None:
        return
    from .system_libs import prelink_system_libs as _pl
    from .analysis import run_full_analysis as _rf, run_incremental_analysis as _ri
    _prelink = _pl
    _run_full = _rf
    _run_incr = _ri


def check_and_reimport(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str = "ds_offline",
    verbose: bool = False,
) -> bool:
    """Check if the binary has changed and re-import + analyze if needed.

    Pipeline:
    1. Compute SHA256 of current binary on disk
    2. Compare against stored checksum (if exists)
    3. On mismatch or missing checksum:
       a. Pre-import all ARM32 system libs from sources/lib/
       b. Import the main binary via analyzeHeadless
       c. Run full or incremental analysis via pyghidra
       d. Save new checksum to .sha256 file
    4. On match: skip everything

    Args:
        binary: Path to the binary file (libcocos2dcpp.so).
        ghidra_project_dir: Path to the parent directory of the Ghidra project.
        project_name: Name of the Ghidra project (e.g. 'ds_offline').
        verbose: If True, show all import/analysis logs; if False, only
                 show [*] status lines and the WARNING banner.

    Returns:
        True if re-import + analysis was performed, False if already up to date.
    """
    from .checksum import compute_sha256 as _compute_sha256
    from .checksum import read_stored_checksum as _read_stored
    from .checksum import write_stored_checksum as _write_stored
    from .system_libs import prelink_system_libs as _prelink
    from .analysis import run_full_analysis as _run_full, run_incremental_analysis as _run_incr
    from src.logic.server.init.stages.find_ghidra import find_ghidra_install as _find_ghidra

    checksum_file = Path(str(binary) + ".sha256")
    current_sha = _compute_sha256(binary)
    stored_sha = _read_stored(checksum_file)

    if stored_sha == current_sha:
        return False

    if stored_sha is None:
        print(f"[*] No checksum file found ({checksum_file})")
    else:
        print(f"[*] Binary checksum mismatch:")
        print(f"    on-disk:  {current_sha}")
        print(f"    stored:   {stored_sha}")
    print("[*] Re-importing into Ghidra project...")

    _reimport_binary(binary, ghidra_project_dir, project_name, verbose=verbose)

    # Use incremental analysis if we already have a stored checksum (meaning the
    # project was fully analyzed before). The previous run left the project
    # fully analyzed on disk; after -noanalysis import only changed bytes need
    # re-analysis.
    use_incremental = stored_sha is not None

    print()
    if use_incremental:
        print("  [analysis] Mode: incremental (stale functions only)")
        print("  [analysis] This should be fast — only changed code will be re-analyzed.")
    else:
        print("=" * 68)
        print("  NOTE: Full Ghidra analysis is about to run (first time or cold start).")
        print("  This can take several minutes. Set the shell tool call")
        print("  timeout to at least 10 minutes to allow the analysis to")
        print("  complete without interruption.")
        print("=" * 68)
    print()

    t0 = _time.time()
    if use_incremental:
        _run_incr(binary, ghidra_project_dir, project_name)
    else:
        _run_full(binary, ghidra_project_dir, project_name)
    analysis_elapsed = _time.time() - t0

    _write_stored(checksum_file, current_sha)
    print(f"[*] Checksum saved to {checksum_file}")
    print(f"[*] Re-import + analysis complete. ({round(analysis_elapsed, 1)}s)")
    return True


def reimport_binary(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str = "ds_offline",
    verbose: bool = False,
) -> bool:
    """Re-import binary into Ghidra project via analyzeHeadless.

    Uses the analyzeHeadless headless tool with -noanalysis flag to refresh
    the binary in the project without running the full analyzer.

    BEFORE importing the main binary, imports all ARM32 system libs from
    sources/lib/ so their symbols resolve correctly during analysis.

    Args:
        binary: Path to the binary file (libcocos2dcpp.so).
        ghidra_project_dir: Path to the parent directory of the Ghidra project.
        project_name: Name of the Ghidra project (e.g. 'ds_offline').
        verbose: If True, print all import logs; if False, suppress them.

    Returns:
        True if re-import was performed successfully.
    """
    _ensure_imports()
    print("[*] Pre-linking ARM32 system libraries from sources/lib/...")
    linked = _prelink(ghidra_project_dir, project_name, verbose=verbose)
    if linked:
        print(f"[*] Pre-linked {len(linked)} system library(ies): {', '.join(linked)}")
    else:
        print("[*] System libs already present or all skipped.")

    _do_main_import(binary, ghidra_project_dir, project_name, verbose=verbose)
    return True


# ── Private helpers (not exported publicly) ────────────────────────────────────


def _reimport_binary(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str = "ds_offline",
    verbose: bool = False,
) -> None:
    """Internal: run prelink + main import (used by check_and_reimport)."""
    _ensure_imports()
    _prelink(ghidra_project_dir, project_name, verbose=verbose)
    _do_main_import(binary, ghidra_project_dir, project_name, verbose=verbose)


def _do_main_import(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str = "ds_offline",
    verbose: bool = False,
) -> None:
    """Internal: run analyzeHeadless -import -noanalysis -overwrite for main binary."""
    import subprocess

    from src.logic.server.init.stages.find_ghidra import find_ghidra_install as _find_ghidra

    project_root = Path(ghidra_project_dir).parent.parent.parent
    ghidra_install = _find_ghidra(project_root)
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

    capture = None if verbose else subprocess.DEVNULL

    result = subprocess.run(
        cmd,
        stdout=capture,
        stderr=capture,
        text=True,
        timeout=120,
    )

    if verbose:
        for line in (result.stdout or "").splitlines():
            print(f"  [import] {line}")
        if result.stderr:
            for line in result.stderr.splitlines():
                print(f"  [import] STDERR: {line}", __import__("sys").stderr)
