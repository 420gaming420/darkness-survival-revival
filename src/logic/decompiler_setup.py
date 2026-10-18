"""Decompiler setup with full options matching GUI "complete analyze".

Creates and configures a ``DecompInterface`` instance with all boolean
options set for maximum resolution. Returns the configured interface.
"""

from __future__ import annotations


def create_decompiler(fpa) :
    """Create and configure a DecompInterface with full options.

    All boolean options are set to their maximum for best type inference,
    matching the GUI "complete analyze" behavior.

    Args:
        fpa: FlatProgramAPI from an open session.

    Returns:
        Configured DecompInterface instance (not yet opened).
    """
    from ghidra.app.decompiler import DecompInterface, DecompileOptions

    prog = fpa.currentProgram

    opts = DecompileOptions()
    opts.grabFromProgram(prog)
    opts.setAnalyzeForLoops(True)
    opts.setBitfieldAccess(True)
    opts.setConventionPrint(True)
    opts.setDisplayLineNumbers(True)
    opts.setEOLCommentIncluded(True)
    opts.setEliminateUnreachable(True)
    opts.setHeadCommentIncluded(True)
    opts.setIgnoreUnimplemented(True)
    opts.setInferConstantPointers(True)
    opts.setInplaceTokens(True)
    opts.setNoCastPrint(False)
    opts.setNullToken(True)
    opts.setPLATECommentIncluded(True)
    opts.setPOSTCommentIncluded(True)
    opts.setPRECommentIncluded(True)
    opts.setPredicate(True)
    opts.setRespectReadOnly(True)
    opts.setSimplifyDoublePrecision(True)
    opts.setSplitArrays(True)
    opts.setSplitPointers(True)
    opts.setSplitStructures(True)
    opts.setWARNCommentIncluded(True)

    di = DecompInterface()
    di.setOptions(opts)
    di.openProgram(prog)
    di.toggleJumpLoads(True)  # critical for switch/jumptable functions

    return di
