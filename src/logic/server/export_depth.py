"""Function entry builder with BFS depth from mainLoop.

Computes BFS depth from mainLoop (0x4e6a9c) for every function in the binary,
then returns filtered lists based on mode ('all', 'reachable', 'stale').

This is a server-side concern — it's only used by the export RPC handlers.
"""

from __future__ import annotations

from collections import deque


def build_func_entries_with_depth(mode: str) -> list[tuple[str, str, int]]:
    """Build function entries with BFS depth from mainLoop.

    Args:
        mode: 'all', 'reachable', or 'stale'.

    Returns:
        List of (hex_addr, func_name, depth) tuples.
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
        return [(hex(e), func_map[e].name, depth_map.get(e, 0)) for e in sorted(visited) if e in func_map]
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
                        result.append((hex(entry), func_obj.name, 0))
            except Exception:
                pass
        return result
    else:
        return [(hex(e), func_map[e].name, depth_map.get(e, -1)) for e in sorted(func_map.keys())]
