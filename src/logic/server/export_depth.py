"""Function entry builder with BFS depth and category from mainLoop.

Computes BFS depth from mainLoop (0x4e6a9c) and classifies each function
into a category folder based on Ghidra namespace/thunk/external info,
then returns filtered lists based on mode ('all', 'reachable', 'stale').

Entry tuple: (hex_addr, func_name, depth, category)
"""

from __future__ import annotations

from collections import deque


# Special-category prefixes — these get underscore-prefixed folder names
_SPECIAL_PREFIXES = [
    ("__cxa_", "_cxa"),
    ("__android_", "_android"),
    ("FT_", "_freetype"),
    ("Java_", "_jni"),
    ("JNI_", "_jni"),
]

# Library namespaces that get underscore-prefixed
_LIBRARY_NS = {
    "libc.so", "libm.so", "libdl.so", "liblog.so",
    "libGLESv2.so", "libEGL.so", "libandroid.so",
    "libOpenSLES.so",
}

_SPECIAL_NS = {
    "<EXTERNAL>",
    "GLOBAL",
    "Global",
    "",
}


# Functory name patterns — compiler-generated closures/lambdas
_FUNCTOR_PATTERNS = (
    "_Base_manager<std::",
    "_Function_handler<",
    "function<",
)


def _get_category(func) -> str:
    """Determine the output category for a function.

    Walks the full namespace hierarchy to produce paths like
    ``cocos2d/Layer`` instead of just ``Layer``.
    Functor/closure symbols (e.g. _Base_manager, function<...>) go to
    ``_functors``.  Thunks, special prefixes, and library namespaces
    are handled first.

    Args:
        func: Ghidra Function object.

    Returns:
        Category string used as subdirectory name.
    """
    name = func.name

    # Thunks first
    if func.isThunk():
        return "_thunk"

    # Special name prefixes
    for prefix, cat in _SPECIAL_PREFIXES:
        if name.startswith(prefix):
            return cat

    # Build full namespace path by walking up the hierarchy
    ns = func.getParentNamespace()
    parts = []
    while ns is not None:
        ns_name = ns.getName()
        if ns_name in _SPECIAL_NS:
            break
        parts.append(ns_name)
        try:
            ns = ns.getParentNamespace()
        except Exception:
            break
    parts.reverse()  # deepest class first → top-level package first

    # Library namespaces (top-level part only)
    if parts and parts[-1] in _LIBRARY_NS:
        return "_" + parts[-1]

    # Empty path or only special-ns entries → check for functors
    if not parts:
        for pattern in _FUNCTOR_PATTERNS:
            if name.startswith(pattern):
                return "_functors"
        return "_global"

    # Functor check: if the function name starts with a functor pattern,
    # or if any namespace component contains a functor pattern,
    # route to _functors
    for pattern in _FUNCTOR_PATTERNS:
        if name.startswith(pattern):
            return "_functors"
    for part in parts:
        for pattern in _FUNCTOR_PATTERNS:
            if pattern in part:
                return "_functors"

    # Truncate extremely long namespace paths to fit filesystem limits.
    full = "/".join(parts)
    if len(full) > 100:
        import hashlib
        short = hashlib.sha256(full.encode()).hexdigest()[:8]
        return full[:70] + "-" + short
    return full


def build_func_entries_with_depth(mode: str) -> list[tuple[str, str, int, str]]:
    """Build function entries with BFS depth and category.

    Args:
        mode: 'all', 'reachable', or 'stale'.

    Returns:
        List of (hex_addr, func_name, depth, category) tuples.
    """
    from src.logic.server.state_lifecycle import get_fpa, get_program
    from ghidra.util.task import TaskMonitor

    fpa = get_fpa()
    prog = get_program()
    monitor = TaskMonitor.DUMMY
    all_funcs = list(prog.functionManager.getFunctions(True))
    func_map: dict[int, object] = {}
    for f in all_funcs:
        entry = int(str(f.entryPoint), 16)
        func_map[entry] = f

    calls: dict[int, set[int]] = {}
    for f in all_funcs:
        entry = int(str(f.entryPoint), 16)
        if entry not in calls:
            calls[entry] = set()
        for callee in f.getCalledFunctions(monitor):
            c_entry = int(str(callee.entryPoint), 16)
            calls[entry].add(c_entry)

    MAINLOOP = 0x4e6a9c
    depth_map: dict[int, int] = {}
    visited = set()
    queue = deque([(MAINLOOP, 0)])
    visited.add(MAINLOOP)
    depth_map[MAINLOOP] = 0
    while queue:
        current, d = queue.popleft()
        for callee in calls.get(current, set()):
            if callee not in visited:
                visited.add(callee)
                depth_map[callee] = d + 1
                queue.append((callee, d + 1))

    if mode == "reachable":
        return [
            (hex(e), func_map[e].name, depth_map.get(e, 0), _get_category(func_map[e]))
            for e in sorted(visited) if e in func_map
        ]
    elif mode == "stale":
        from src.logic.paths import project_root
        stale_csv = project_root() / "tools" / "export_stale.csv"
        if not stale_csv.exists():
            return []
        seen = set()
        result = []
        for line in stale_csv.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            addr_str = parts[0].strip()
            if not addr_str or addr_str.startswith("#"):
                continue
            try:
                addr = fpa.toAddr(addr_str)
                func_obj = fpa.getFunctionAt(addr)
                if func_obj:
                    entry = int(str(func_obj.entryPoint), 16)
                    key = (hex(entry), func_obj.name)
                    if key not in seen:
                        seen.add(key)
                        result.append((hex(entry), func_obj.name, 0, _get_category(func_obj)))
            except Exception:
                pass
        return result
    else:
        return [
            (hex(e), func_map[e].name, depth_map.get(e, -1), _get_category(func_map[e]))
            for e in sorted(func_map.keys())
        ]
