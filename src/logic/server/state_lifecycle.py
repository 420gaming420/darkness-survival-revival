"""JVM and project lifecycle management for the Ghidra server.

Manages the single persistent JVM session: starting the JVM, opening/closing
the Ghidra project, loading the program, and providing access to FlatProgramAPI
and ProgramDB instances.

Patching is done in-memory via pyghidra's memory API + Sleigh re-assembly —
no disk writes or re-imports between patches. Only when the user calls
``export_binary`` are changes written back to disk.

Analysis status tracking is in ``src.logic.server.state``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


_jvm_started = False
_project = None
_program = None
_consumer = None
_fpa = None
_initialized = False
_binary_sha256: str = ""
_before_sha256: str = ""


def ensure_jvm() -> None:
    """Start the JVM if not already running.

    Must be called before any ghidra.* imports.
    """
    global _jvm_started
    from pyghidra import start as _start
    _start()
    _jvm_started = True


def open_project(
    project_dir: Path,
    project_name: str,
    binary_path_str: str,
) -> None:
    """Open the Ghidra project and load the program.

    Args:
        project_dir: Path to the Ghidra project parent directory.
        project_name: Name of the Ghidra project (e.g. 'ds_offline').
        binary_path_str: Internal path to the binary in the project.
    """
    global _project, _program, _consumer, _fpa

    from pyghidra import start as _start
    from pyghidra import open_project as _open_proj, consume_program
    from ghidra.program.flatapi import FlatProgramAPI

    _start()
    _project = _open_proj(str(project_dir), project_name)
    _program, _consumer = consume_program(_project, binary_path_str)
    _fpa = FlatProgramAPI(_program)


def close_project() -> None:
    """Release program and close the project."""
    global _project, _program, _consumer, _fpa

    if _consumer is not None and _program is not None:
        try:
            _program.release(_consumer)
        except Exception:
            pass
        _consumer = None
    if _project is not None:
        try:
            _project.close()
        except Exception:
            pass
        _project = None
    _fpa = None
    _program = None


def get_fpa():
    """Get the FlatProgramAPI instance.

    Returns:
        FlatProgramAPI from the open session.

    Raises:
        RuntimeError: If project is not initialized.
    """
    if _fpa is None:
        raise RuntimeError("Ghidra project not initialized")
    return _fpa


def get_program():
    """Get the ProgramDB instance.

    Returns:
        ProgramDB from the open session.

    Raises:
        RuntimeError: If project is not initialized.
    """
    if _program is None:
        raise RuntimeError("Ghidra project not initialized")
    return _program


def set_initialized(value: bool) -> None:
    """Set initialization status.

    Args:
        value: True if project is initialized, False otherwise.
    """
    global _initialized
    _initialized = value


def is_initialized() -> bool:
    """Check if the project is initialized.

    Returns:
        True if the project is initialized and ready for requests.
    """
    return _initialized


def set_binary_sha256(sha256_hex: str) -> None:
    """Set the current binary SHA256 hash (what's in Ghidra memory).

    Args:
        sha256_hex: Hex digest of the current binary.
    """
    global _binary_sha256
    _binary_sha256 = sha256_hex


def get_binary_sha256() -> str:
    """Get the current binary SHA256 hash.

    Returns:
        Full hex digest string, or empty string if not set.
    """
    return _binary_sha256


def set_before_sha256(sha256_hex: str) -> None:
    """Set the 'before' (pre-patch) binary SHA256 hash.

    Used for before/after decompiled code comparison. Set after each patch
    so we can look up the pre-patch decompiled output from
    decompiled/<sha8>/ subfolder.

    Args:
        sha256_hex: Hex digest of the pre-patch binary.
    """
    global _before_sha256
    _before_sha256 = sha256_hex


def get_before_sha256() -> str:
    """Get the 'before' (pre-patch) binary SHA256 hash.

    Returns:
        Full hex digest string, or empty string if not set.
    """
    return _before_sha256


def patch_in_memory(fpa, patches: list[dict]) -> None:
    """Apply patches directly to the Ghidra program memory (no disk I/O).

    Each patch is a dict with keys: offset (Ghidra addr), bytes (list of ints 0-255).
    Uses Ghidra's ``patchProgram`` (WildSleighAssembler) which handles:
    - Writing bytes to memory
    - Clearing existing code units in the range
    - Parsing and creating new instructions in the listing
    - Setting up fall-throughs correctly

    This avoids disk writes, re-imports, and full re-analysis between patches.

    Args:
        fpa: FlatProgramAPI from the open session.
        patches: List of patch dicts with 'offset' (int) and 'bytes' (list[int]).
    """
    import jpype
    from jpype import java

    prog = _program

    # Build WildSleighAssembler once (same setup as asm_to_bytes.py).
    JavaAsmSel = java.lang.Class.forName('ghidra.app.plugin.assembler.AssemblySelector')
    selector = JavaAsmSel.getDeclaredConstructors()[0].newInstance()
    JavaWSABuilder = java.lang.Class.forName('ghidra.asm.wild.WildSleighAssemblerBuilder')
    ctor = JavaWSABuilder.getDeclaredConstructors()[0]
    builder = ctor.newInstance(prog.getLanguage())
    asm = builder.getAssembler(selector, prog)

    for patch in patches:
        offset = patch["offset"]
        new_bytes = [b & 0xff for b in patch["bytes"]]
        byte_arr = bytearray(new_bytes)

        tid = int(prog.startTransaction(f"patch {hex(offset)}"))
        try:
            it = asm.patchProgram(byte_arr, fpa.toAddr(offset))
            # Consume the iterator (InstructionRecordIterator).
            while hasattr(it, 'hasNext') and it.hasNext():
                it.next()
            prog.endTransaction(tid, True)
        except Exception:
            try:
                prog.endTransaction(tid, False)
            except Exception:
                pass
            raise


def read_program_memory_as_bytes(fpa) -> bytes:
    """Read the entire program memory as raw bytes using Ghidra's OriginalFileExporter.

    Uses ``ghidra.app.util.exporter.OriginalFileExporter`` (the same exporter used by
    the Ghidra GUI's "Export as Original File Format") to produce a faithful binary
    with all in-memory patches applied. This avoids the manual block-by-block byte
    copying that previously corrupted the exported binary.

    Args:
        fpa: FlatProgramAPI from the open session.

    Returns:
        Bytes object containing all memory content (full binary with patches).
    """
    import jpype
    from ghidra.app.util import exporter
    from ghidra.program.model.address import AddressSet
    from ghidra.util.task import TaskMonitorAdapter
    from java.io import File, FileInputStream

    mem = _program.getMemory()

    # Build an AddressSet covering all non-overlay memory blocks.
    addr_set = AddressSet()
    for block in mem.blocks:
        try:
            s = int(str(block.start), 16)
            e = int(str(block.end), 16)
        except ValueError:
            continue
        if "." in str(block.start):
            continue
        start_addr = fpa.toAddr(s)
        end_addr = fpa.toAddr(e)
        addr_set.addRange(start_addr, end_addr)

    # Export to a temp file via Java.
    tmp_file = File("/tmp/_ghidra_export_temp.so")
    if tmp_file.exists():
        tmp_file.delete()
    exporter_instance = exporter.OriginalFileExporter()
    monitor = TaskMonitorAdapter()
    exporter_instance.export(tmp_file, _program, addr_set, monitor)

    # Read the exported file as a Python bytes object via FileInputStream.
    fis = FileInputStream(tmp_file)
    data = bytearray()
    chunk = jpype.JArray(jpype.JByte)(4096)
    while True:
        n = fis.read(chunk)
        if n <= 0:
            break
        for i in range(n):
            b_val = int(str(chunk[i])) & 0xff
            data.append(b_val)
    fis.close()

    # Clean up temp file.
    tmp_file.delete()

    return bytes(data)


def compute_program_sha256(fpa) -> str:
    """Compute SHA256 of the current program memory contents.

    Args:
        fpa: FlatProgramAPI from the open session.

    Returns:
        Hex digest of the program's memory snapshot.
    """
    data = read_program_memory_as_bytes(fpa)
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def get_versioned_decompiled_dir(sha256_hex: str) -> Path:
    """Get the versioned decompiled directory for a given SHA256.

    Creates the subfolder if it doesn't exist yet. Uses only the first 8
    characters of the SHA256 as the folder name (e.g. decompiled/22eb7a0b/).

    Args:
        sha256_hex: Full SHA256 hex digest of the binary.

    Returns:
        Path to the versioned subfolder.
    """
    from src.logic.paths import decompiled_dir as _get_decompiled

    short = sha256_hex[:8] if len(sha256_hex) >= 8 else sha256_hex
    versioned = _get_decompiled() / short
    versioned.mkdir(parents=True, exist_ok=True)
    return versioned
