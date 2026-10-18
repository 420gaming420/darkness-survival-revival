"""Centralized configuration via dotenv.

Loads settings from .env (or .env.local) in the project root, falling back to
environment variables. All paths and settings are defined here so that no other
module needs to know about dotenv directly.

Usage:
    from src.logic.config import cfg
    print(cfg.binary_path)
    print(cfg.project_name)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[assignment]


def _load_env() -> None:
    """Try to load .env files from the project root."""
    if load_dotenv is None:
        return
    # Project root is grandparent of this file's parent (src/logic/ → src/ → project root)
    _project_root = Path(__file__).resolve().parent.parent.parent
    # Try .env first, then .env.local (for overrides)
    for env_file in (_project_root / ".env", _project_root / ".env.local"):
        if env_file.exists():
            load_dotenv(str(env_file), override=True)


_load_env()


class _Config:
    """Configuration namespace loaded from .env / environment variables."""

    # ── Project Root ─────────────────────────────────────────────────────────
    @property
    def project_root(self) -> Path:
        """Project root directory (parent of src/)."""
        return Path(__file__).resolve().parent.parent.parent

    # ── Ghidra Installation ──────────────────────────────────────────────────
    @property
    def ghidra_install_dir(self) -> Path:
        """Path to Ghidra installation directory."""
        val = os.environ.get("GHIDRA_INSTALL_DIR", "")
        if val:
            return Path(val)
        # Fallback: tools/ghidra relative to project root
        fallback = self.project_root / "tools" / "ghidra"
        if fallback.exists():
            return fallback
        raise RuntimeError(
            "Ghidra installation not found. "
            "Set GHIDRA_INSTALL_DIR in .env or place it at tools/ghidra/."
        )

    # ── Binary ───────────────────────────────────────────────────────────────
    @property
    def binary_path(self) -> Path:
        """Path to the main binary file to analyze.

        Raises:
            RuntimeError: If the binary file does not exist. The APK must be
                extracted first by running: ./1-import.sh
        """
        val = os.environ.get("BINARY_PATH", "").strip()
        if val:
            p = Path(val)
        else:
            # Game default
            p = self.project_root / "project" / "lib" / "armeabi" / "libcocos2dcpp.so"

        if not p.exists():
            raise RuntimeError(
                f"Binary not found: {p}\n"
                f"Run ./1-import.sh to extract the binary from the game's APK.\n"
                f"Or set BINARY_PATH in .env to point to an existing binary."
            )
        return p

    # ── Text Data (game-specific) ────────────────────────────────────────────
    @property
    def textdata_en_path(self) -> Path:
        """Path to textdata_en.dat for i18n string resolution."""
        val = os.environ.get("TEXTDATA_EN_PATH", "").strip()
        if val:
            return Path(val)
        # Game default
        return self.project_root / "project" / "assets" / "textdata_en.dat"

    # ── Ghidra Project ───────────────────────────────────────────────────────
    @property
    def ghidra_project_dir(self) -> Path:
        """Parent directory where Ghidra projects are stored."""
        val = os.environ.get("GHIDRA_PROJECT_DIR", "").strip()
        if val:
            return Path(val)
        # Fallback: tools/ghidra/project relative to project root
        fallback = self.project_root / "tools" / "ghidra" / "project"
        if fallback.exists():
            return fallback
        return self.project_root / "tools" / "ghidra" / "project"

    @property
    def project_name(self) -> str:
        """Name of the Ghidra project."""
        return os.environ.get("GHIDRA_PROJECT_NAME", "ds_offline").strip()

    # ── Processor & Compiler ─────────────────────────────────────────────────
    @property
    def processor_id(self) -> str:
        """Ghidra processor language ID (e.g. 'ARM:LE:32:v5t')."""
        return os.environ.get("GHIDRA_PROCESSOR_ID", "ARM:LE:32:v5t").strip()

    @property
    def compiler_spec(self) -> str:
        """Compiler specification ID (e.g. 'gcc', 'apcs')."""
        return os.environ.get("GHIDRA_COMPILER_SPEC", "default").strip()

    # ── System Libraries (required for proper decompile) ─────────────────────
    @property
    def system_libs_skip(self) -> bool:
        """Whether to skip system library validation.

        Set SYSTEM_LIBS_SKIP=1 in .env to bypass the requirement.
        Without system libs, ~1200 functions will remain as unresolved FUN_ stubs.
        """
        return os.environ.get("SYSTEM_LIBS_SKIP", "0") in ("1", "true", "yes")

    @property
    def system_libs_dir(self) -> Optional[Path]:
        """Directory containing system .so files.

        Returns None if SYSTEM_LIBS_SKIP is set.

        Raises:
            RuntimeError: If the directory does not exist or any required lib is missing.
                The system libs must be built from the Cocos2d-x engine separately.
        """
        if self.system_libs_skip:
            return None
        val = os.environ.get("SYSTEM_LIBS_DIR", "").strip()
        if not val:
            raise RuntimeError(
                "SYSTEM_LIBS_DIR not set.\n"
                "Set SYSTEM_LIBS_DIR in .env to point to the directory containing\n"
                "ARM32 Android system .so files.\n"
                "These must be built from the Cocos2d-x engine separately.\n"
                "Or set SYSTEM_LIBS_SKIP=1 to bypass this requirement\n"
                "(~1200 functions will remain as unresolved FUN_ stubs)."
            )
        p = Path(val)
        if not p.exists():
            raise RuntimeError(
                f"SYSTEM_LIBS_DIR does not exist: {p}\n"
                f"The system libs must be built from the Cocos2d-x engine separately.\n"
                f"Or set SYSTEM_LIBS_SKIP=1 to bypass this requirement\n"
                f"(~1200 functions will remain as unresolved FUN_ stubs)."
            )
        missing = [lib for lib in self.system_libs if not (p / lib).exists()]
        if missing:
            lines = "\n".join(f"  - {lib}" for lib in missing)
            raise RuntimeError(
                f"Missing system libraries in {p}:\n{lines}\n"
                f"These must be built from the Cocos2d-x engine separately.\n"
                f"Or set SYSTEM_LIBS_SKIP=1 to bypass this requirement\n"
                f"(~1200 functions will remain as unresolved FUN_ stubs)."
            )
        return p

    @property
    def system_libs(self) -> list[str]:
        """List of system library filenames to pre-import into the Ghidra project."""
        val = os.environ.get("SYSTEM_LIBS", "").strip()
        if not val:
            # Game defaults — the 10 libs the binary actually imports
            return [
                "libandroid.so", "libc.so", "libdl.so", "libEGL.so",
                "libGLESv1_CM.so", "libGLESv2.so", "liblog.so",
                "libm.so", "libOpenSLES.so", "libstdc++.so",
            ]
        return [s.strip() for s in val.split(",") if s.strip()]

    # ── Server ───────────────────────────────────────────────────────────────
    @property
    def server_port(self) -> int:
        """Port for the JSON-RPC HTTP server."""
        return int(os.environ.get("GHIDRA_SERVER_PORT", "18960"))

    @property
    def inactivity_timeout(self) -> int:
        """Inactivity timeout in seconds (0 = disabled)."""
        return int(os.environ.get("GHIDRA_INACTIVITY_TIMEOUT", "5400"))

    @property
    def debug(self) -> bool:
        """Whether DEBUG mode is enabled."""
        return os.environ.get("GHIDRA_SERVER_DEBUG", "0") in ("1", "true", "yes")

    # ── Output ───────────────────────────────────────────────────────────────
    @property
    def decompiled_dir(self) -> Path:
        """Directory where decompiled function exports are written."""
        val = os.environ.get("DECOMPILED_DIR", "").strip()
        if val:
            return Path(val)
        # Fallback: decompiled/ relative to project root
        return self.project_root / "decompiled"

    # ── Binary image base ────────────────────────────────────────────────────
    @property
    def ghidra_image_base(self) -> int:
        """Ghidra image base for stripped ELF binaries (typically 0x10000)."""
        try:
            return int(os.environ.get("GHIDRA_IMAGE_BASE", "0x10000"), 0)
        except ValueError:
            return 0x10000

    # ── MainLoop address (optional, for --reachable export mode) ─────────────
    @property
    def mainloop_addr(self) -> Optional[int]:
        """Entry address of the mainLoop function for BFS depth computation.

        Set to empty or omit to disable --reachable mode (will fall back to
        scanning all functions).
        """
        val = os.environ.get("MAINLOOP_ADDR", "").strip()
        if not val:
            return None
        try:
            return int(val, 16)
        except ValueError:
            print(f"[config] WARNING: Invalid MAINLOOP_ADDR '{val}', --reachable will be disabled")
            return None


cfg = _Config()
