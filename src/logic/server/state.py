"""Analysis status tracking for the Ghidra server.

Manages the ``AnalysisStatus`` enum and condition variable used to signal
to all RPC handlers when full/incremental analysis is complete.

JVM/project lifecycle lives in ``src.logic.server.state_lifecycle``.
"""

from __future__ import annotations

import threading
from enum import Enum


class AnalysisStatus(str, Enum):
    """Current state of the initialization/analysis pipeline."""
    IDLE = "idle"
    IMPORTING_LIBS = "importing_system_libs"
    IMPORTING_BINARY = "importing_main_binary"
    RUNNING_FULL_ANALYSIS = "running_full_analysis"
    RUNNING_INCREMENTAL = "running_incremental"
    DONE = "done"


_lock = threading.Lock()
_condition = threading.Condition(_lock)

# ── Operation/queue state ─────────────────────────────────────────────────────
# Tracks in-progress operations (e.g. export, patcher apply) so clients can
# see "queue: idle" or "queue: Running --all export, 40% complete."
_queue_status: str = "idle"
_queue_progress: float = 0.0


def set_queue_status(status: str, progress: float = 0.0) -> None:
    """Set the current queue/operation status.

    Args:
        status: Human-readable status string (e.g. "Running --all export").
        progress: Progress percentage 0.0-1.0, or -1 for unknown.
    """
    global _queue_status, _queue_progress
    with _condition:
        _queue_status = status
        _queue_progress = progress


def get_queue_status() -> tuple[str, float]:
    """Get the current queue/operation status and progress.

    Returns:
        Tuple of (status string, progress float).
    """
    return (_queue_status, _queue_progress)


# ── Analysis state ────────────────────────────────────────────────────────────

_analysis_status: AnalysisStatus = AnalysisStatus.IDLE
_analysis_message: str = ""


def set_analysis_status(status: AnalysisStatus, message: str = "") -> None:
    """Set the current analysis status and wake all waiting threads.

    Args:
        status: New analysis state.
        message: Optional human-readable message about progress.
    """
    global _analysis_status, _analysis_message
    with _condition:
        _analysis_status = status
        _analysis_message = message
        _condition.notify_all()


def get_analysis_status() -> tuple[AnalysisStatus, str]:
    """Get the current analysis status and message.

    Returns:
        Tuple of (status enum, message string).
    """
    return (_analysis_status, _analysis_message)


def wait_for_analysis_done(timeout: float | None = None) -> bool:
    """Block the calling thread until analysis is complete or timeout.

    Used by the request handler to stall incoming RPC calls while
    full/incremental analysis runs in a background thread.

    Args:
        timeout: Maximum seconds to wait. None means wait forever.

    Returns:
        True if analysis finished, False if timed out.
    """
    with _condition:
        while _analysis_status not in (AnalysisStatus.IDLE, AnalysisStatus.DONE):
            if not _condition.wait(timeout=timeout):
                return False
        return True


def lock() -> threading.Lock:
    """Get the state lock for thread-safe access.

    Returns:
        The threading.Lock instance.
    """
    return _lock
