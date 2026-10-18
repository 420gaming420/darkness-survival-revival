"""Ghidra server logic package.

Exposes public API for project initialization, state management,
and RPC handlers (decompile, export, patcher).

State is split into two modules:
- ``state``: Analysis status enum + condition variable
- ``state_lifecycle``: JVM lifecycle + project open/close + accessors
"""

from src.logic.server.init import initialize_project  # noqa: F401
from src.logic.server.state import (  # noqa: F401
    AnalysisStatus,
    get_analysis_status,
    lock,
    wait_for_analysis_done,
)
from src.logic.server.state_lifecycle import (  # noqa: F401
    close_project,
    ensure_jvm,
    get_before_sha256,
    get_binary_sha256,
    get_fpa,
    get_program,
    is_initialized,
    open_project,
    patch_in_memory,
    set_binary_sha256,
    set_before_sha256,
    set_initialized,
)
from src.logic.server.decompile import handle_decompile  # noqa: F401
from src.logic.server.export import handle_export_all, handle_export_single  # noqa: F401
from src.logic.server.patcher_show import handle_patcher_preview, handle_patcher_show  # noqa: F401
from src.logic.server.patcher_apply import handle_patcher_apply  # noqa: F401
from src.logic.server.rpc import DISPATCH  # noqa: F401
