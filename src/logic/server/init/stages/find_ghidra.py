"""Ghidra installation finder.

Locates the Ghidra install directory from env var or known paths.
"""

from __future__ import annotations

import os
from pathlib import Path


def find_ghidra_install(project_root: Path) -> Path:
    """Find the Ghidra installation directory.

    Args:
        project_root: Project root path.

    Returns:
        Path to Ghidra installation.

    Raises:
        RuntimeError: If Ghidra is not found.
    """
    env_val = os.environ.get("GHIDRA_INSTALL_DIR")
    if env_val and Path(env_val).exists():
        return Path(env_val)

    # Also check the config value (loaded from .env).
    try:
        from src.logic.config import cfg as _cfg
        if _cfg.ghidra_install_dir.exists():
            return _cfg.ghidra_install_dir
    except Exception:
        pass

    candidates = [
        project_root / "tools" / "ghidra",
    ]
    for c in candidates:
        if (c / "support" / "analyzeHeadless").exists():
            return c

    raise RuntimeError(
        "Could not find Ghidra installation. Set GHIDRA_INSTALL_DIR env var "
        "or place it at tools/ghidra/ relative to project root."
    )
