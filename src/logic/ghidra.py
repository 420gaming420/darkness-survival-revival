"""Ghidra project lifecycle management.

Handles JVM startup, project opening/closing, program consume/release,
and FlatProgramAPI wrapper for function/data lookups.

Each Python invocation launches a fresh JVM — no shared state across calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Must call start() before any ghidra.* imports
from pyghidra import open_project, consume_program


def _ensure_jvm():
    """Start the JVM if not already running. Called lazily by open_project."""
    from pyghidra import start as _start
    _start()


class GhidraSession:
    """Context manager for a single Ghidra project session.

    Usage:
        with GhidraSession(project_dir, project_name) as session:
            prog = session.program  # ProgramDB object
            fpa = session.fpa       # FlatProgramAPI wrapper
            func = fpa.get_function_at(addr)
    """

    def __init__(self, project_dir: Path | str, project_name: str):
        self._project_dir = Path(project_dir)
        self._project_name = project_name
        self._project = None
        self._prog = None
        self._consumer = None
        self._fpa = None

    def __enter__(self):
        _ensure_jvm()
        self._project = open_project(str(self._project_dir), self._project_name)
        self._prog, self._consumer = consume_program(self._project, "/libcocos2dcpp.so")
        from ghidra.program.flatapi import FlatProgramAPI

        self._fpa = FlatProgramAPI(self._prog)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # don't suppress exceptions

    @property
    def program(self):
        """The Ghidra ProgramDB object."""
        return self._prog

    @property
    def fpa(self):
        """FlatProgramAPI for convenient lookups."""
        return self._fpa

    @property
    def project(self):
        """The open Ghidra project."""
        return self._project

    def close(self):
        """Release program and close project."""
        if self._consumer is not None and self._prog is not None:
            try:
                self._prog.release(self._consumer)
            except Exception:
                pass
            self._consumer = None
        if self._project is not None:
            try:
                self._project.close()
            except Exception:
                pass
            self._project = None
        self._fpa = None
        self._prog = None


def open_session(project_dir: Path | str, project_name: str) -> GhidraSession:
    """Open a new Ghidra session (not a context manager).

    Caller is responsible for calling session.close() when done.
    For context manager usage, use GhidraSession directly.
    """
    return GhidraSession(project_dir, project_name)
