"""Pipeline orchestrator for project initialization.

Coordinates the full init or re-analysis pipeline by calling stage functions.
Provides both a synchronous `initialize_project` and an async `run_initialization`
that runs in a background thread, reporting progress via state.set_analysis_status().

After analysis completes, automatically exports all decompiled functions to a
versioned subfolder inside decompiled/ (e.g. decompiled/22eb7a0b/).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from src.logic.server.init.stages.check_init import needs_full_init
from src.logic.server.init.stages.checksum import save_checksum
from src.logic.server.init.stages.import_system_libs import import_system_libs
from src.logic.server.init.stages.run_full_analysis import run_full_analysis
from src.logic.server.init.stages.run_incremental_analysis import run_incremental_analysis
from src.logic.server.state import AnalysisStatus, set_analysis_status

# Flag set by init thread to signal that auto-export is needed after JVM session opens.
# Uses a list so it's mutable from the background thread.
_auto_export_pending: list[bool] = [False]


def check_and_clear_auto_export_pending() -> bool:
    """Check if auto-export is pending, return and clear the flag.

    Returns:
        True if auto-export was pending (and flag cleared), False otherwise.
    """
    if _auto_export_pending[0]:
        _auto_export_pending[0] = False
        return True
    return False


def _auto_export_after_init(binary: Path, ghidra_project_dir: Path, project_name: str) -> None:
    """Queue auto-export after init completes.

    The actual export is triggered by the RPC handler after the JVM session is
    opened (which happens after analysis finishes). This function sets a flag
    that the handler checks to decide whether to auto-export.

    Args:
        binary: Path to libcocos2dcpp.so.
        ghidra_project_dir: Path to the Ghidra project directory.
        project_name: Name of the Ghidra project.
    """
    # Signal that auto-export is pending — the RPC handler will do it after
    # opening the JVM session (get_fpa() needs the session to be open).
    _auto_export_pending[0] = True
    print("[server] Auto-export queued — will run after JVM session opens")


def initialize_project(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str,
    system_libs_dir: Path,
    verbose: bool = False,
) -> dict:
    """Full project initialization pipeline (runs in caller's thread).

    Args:
        binary: Path to libcocos2dcpp.so.
        ghidra_project_dir: Path to the Ghidra project directory.
        project_name: Name of the Ghidra project (e.g. 'ds_offline').
        system_libs_dir: Directory containing ARM32 .so files (sources/lib/).
        verbose: If True, print each import; if False, suppress output.

    Returns:
        Dict with keys: initialized (bool), reanalyzed (bool), elapsed (float).
    """
    from src.logic.server.init.stages.checksum import compute_sha256
    from src.logic.server.init.stages.import_main_binary import reimport_main_binary

    result = {"initialized": False, "reanalyzed": False, "elapsed": 0.0}

    full_init_needed = needs_full_init(ghidra_project_dir, project_name, binary)

    if full_init_needed:
        print("[server] Full initialization needed — importing system libraries...")
        set_analysis_status(AnalysisStatus.IMPORTING_LIBS, "Importing system libraries...")
        linked = import_system_libs(ghidra_project_dir, project_name, system_libs_dir, verbose=verbose)
        if linked:
            print(f"[server] Imported {len(linked)} system library(ies): {', '.join(linked)}")
        else:
            print("[server] System libs already present or all skipped.")

        print("[server] Importing main binary (libcocos2dcpp.so)...")
        set_analysis_status(AnalysisStatus.IMPORTING_BINARY, "Importing main binary...")
        reimport_main_binary(binary, ghidra_project_dir, project_name)

        print("[server] Running full analysis (this may take 15-45 minutes)...")
        set_analysis_status(AnalysisStatus.RUNNING_FULL_ANALYSIS, "Running full analysis...")
        t0 = time.time()
        run_full_analysis(binary, ghidra_project_dir, project_name)
        result["elapsed"] = time.time() - t0
        result["initialized"] = True
    else:
        current_sha = compute_sha256(binary)
        try:
            stored_file = Path(str(binary) + ".sha256")
            stored_sha = stored_file.read_text().strip()
            if current_sha != stored_sha:
                print("[server] Binary changed, running incremental analysis...")
                set_analysis_status(AnalysisStatus.RUNNING_INCREMENTAL, "Running incremental analysis...")
                t0 = time.time()
                run_incremental_analysis(binary, ghidra_project_dir, project_name)
                result["elapsed"] = time.time() - t0
                result["reanalyzed"] = True
            else:
                print("[server] Binary unchanged, skipping analysis.")
        except FileNotFoundError:
            print("[server] No stored checksum, running full analysis...")
            set_analysis_status(AnalysisStatus.RUNNING_FULL_ANALYSIS, "Running full analysis...")
            t0 = time.time()
            run_full_analysis(binary, ghidra_project_dir, project_name)
            result["elapsed"] = time.time() - t0
            result["initialized"] = True

    current_sha = compute_sha256(binary)
    save_checksum(binary, current_sha)
    set_analysis_status(AnalysisStatus.DONE, "Analysis complete.")
    print(f"[server] Initialization complete. ({result['elapsed']:.1f}s)")

    # Auto-export only if the versioned directory for this SHA256 doesn't exist yet.
    from src.logic.paths import decompiled_dir as _get_decompiled
    versioned_dir = _get_decompiled() / current_sha[:8]
    if not versioned_dir.exists():
        print(f"[server] Versioned decompiled/ folder missing ({versioned_dir}) — queuing auto-export...")
        _auto_export_after_init(binary, ghidra_project_dir, project_name)
    else:
        print(f"[server] Versioned decompiled/ folder already exists ({versioned_dir}) — skipping auto-export.")

    return result


def run_initialization(
    binary: Path,
    ghidra_project_dir: Path,
    project_name: str,
    system_libs_dir: Path,
) -> None:
    """Run initialization in a background thread (thread entry point).

    Calls initialize_project() which updates state.set_analysis_status() at each stage.
    This is the function passed to threading.Thread(target=...).
    """
    try:
        initialize_project(
            binary=binary,
            ghidra_project_dir=ghidra_project_dir,
            project_name=project_name,
            system_libs_dir=system_libs_dir,
        )
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[server] INITIALIZATION FAILED:\n{tb}")
        set_analysis_status(AnalysisStatus.DONE, f"Init failed: {e}")
