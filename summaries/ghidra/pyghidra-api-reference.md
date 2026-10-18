# PyGhidra API Comprehensive Research Report

## Executive Summary

Explored every major area of the pyghidra Python API using the `ds_offline` Ghidra project containing `libcocos2dcpp.so`. Below are findings for all 9 research areas, with tested code, API names, and ratings.

---

## 1. Assembly/Disassembly API

**RATING: VERY USEFUL**

### Key APIs Found

| API | Description | Status |
|-----|-------------|--------|
| `prog.listing.getInstructions(AddressSetView, boolean)` | Returns iterator of all `InstructionDB` objects in a range | WORKS |
| `InstructionDB.address` | The address of the instruction | WORKS |
| `InstructionDB.bytes` | Raw byte array (`byte[]`) | WORKS |
| `InstructionDB.flowType` | Flow type string (FALL_THROUGH, CONDITIONAL_JUMP, etc.) | WORKS |
| `InstructionDB.fallThrough` | Address of fall-through target | WORKS |
| `InstructionDB.flows` | Array of all branch targets | WORKS |
| `InstructionDB.getInstructionContext()` | Returns `InstructionContext` object | WORKS |
| `InstructionContext.getMnemonicString()` | Returns the mnemonic (e.g., "ldr", "movs") | WORKS |
| `InstructionContext.getOpObjects(int)` | Returns operand objects for operand index 0 | WORKS |
| `InstructionContext.getNumOperands()` | Number of operands | WORKS |
| `prog.listing.getNumInstructions()` | Total instruction count in entire program | WORKS |

### Example: Full Disassembly of a Function

```python
body = func.body
for instr in prog.listing.getInstructions(body, True):
    ctx = instr.getInstructionContext()
    mnemonic = ctx.getMnemonicString()  # "ldr", "movs", etc.
    ops = ctx.getOpObjects(0)           # [r3] or similar
    raw_bytes = instr.bytes             # byte array
    flow = instr.flowType               # "FALL_THROUGH"
    
    hex_str = ' '.join('{:02x}'.format(b) for b in raw_bytes)
    print('%s [%d bytes] %s%s | %s' % (instr.address, len(raw_bytes', mnemonic,
          (' '+str(ops)) if ops else '', hex_str))
```

### Gotchas
- `InstructionDB` has NO `mnemonicName` attribute — must use `getInstructionContext().getMnemonicString()`
- `getNumInstructions(body, True)` does NOT exist — only `getNumInstructions()` with no args (returns total for entire program)
- Raw bytes may be negative (signed in Python — use `'& 0xff') or '{:02x}'.format(b & 0xff)`

---

## 2. CFG / Basic Blocks

**RATING: USEFUL**

### Block Models Available

| Class | Status | Notes |
|-------|--------|-------|
| `SimpleBlockModel(prog, True)` | WORKS | Standard basic block model. Each block = one or more consecutive instructions with no internal branches. |
| `SubroutineBlockModel` | EXISTS | Not tested in detail — likely for subroutines across functions. |
| **NO** `DefaultFlowBlockModel` | NOT FOUND | Does not exist in this Ghidra version. |

### Block Methods (CodeBlockImpl)

| Method/Attr | Description | Status |
|-------------|-------------|--------|
| `block.firstStartAddress` | First address of the block | WORKS |
| `block.maxAddress` / `block.minAddress` | Address range bounds | WORKS |
| `block.getDestinations(TaskMonitor)` | Iterator of successors with flow type | WORKS |
| `block.getSources(TaskMonitor)` | **Iterator of predecessors** (NOT `getPredecessors`) | WORKS |
| `body.contains(block.firstStartAddress)` | Check if block belongs to a function | WORKS |

### Example: Get All Predecessors and Successors

```python
from ghidra.program.model.block import SimpleBlockModel
from ghidra.util.task import TaskMonitor

sbm = SimpleBlockModel(prog, True)
monitor = TaskMonitor.DUMMY
body = func.getBody()

# Filter to function's blocks only
all_blocks = list(sbm.getCodeBlocks(monitor))
fn_blocks = [b for b in all_blocks if body.contains(b.firstStartAddress)]

for block in fn_blocks:
    # Predecessors (incoming edges)
    src_iter = block.getSources(monitor)
    for ref in src_iter:
        src_addr = int(str(ref.sourceBlock.firstStartAddress), 16)
        flow = str(ref.flowType)
    
    # Successors (outgoing edges)  
    dest_iter = block.getDestinations(monitor)
    for ref in dest_iter:
        dst_addr = int(str(ref.destinationBlock.firstStartAddress), 16)
        flow = str(ref.flowType)
```

### Gotchas
- `getSources()` returns predecessors; `getDestinations()` returns successors — the naming is counterintuitive (sources "source" this block, destinations "destined" by this block)
- Each `CodeBlockReference` has `sourceBlock`, `destinationBlock`, and `flowType`) attributes

---

## 3. References / Call Graph

**RATING: VERY USEFUL**

### Key APIs

| API | Description | Status |
|-----|-------------|--------|
| `func.getCallingFunctions(TaskMonitor)` | All functions that CALL this function (callers) | WORKS |
| `func.getCalledFunctions(TaskMonitor)` | All functions this function CALLS (callees) | WORKS |
| `prog.referenceManager.getReferencesTo(Address)` | All references TO an address | WORKS |
| `prog.referenceManager.getReferencesFrom(Address)` | All references FROM an address (returns Java array, not iterator!) | WORKS |

### Reference Object Attributes

| Attribute | Description | Status |
|-----------|-------------|--------|
| `ref.fromAddress` / `ref.source` | Source address of reference | WORKS |
| `ref.toAddress` / `ref.destinationAddress` | Destination address | WORKS |
| `ref.referenceType` / `ref.getReferenceType()` | Type (READ, WRITE, UNCONDITIONAL_CALL, etc.) | WORKS |
| `ref.isMemoryReference()`, `isOperandReference()`, `isEntryPointReference()` | Reference type checks | WORKS |

### Example: Full Call Graph for a Function

```python
monitor = TaskMonitor.DUMMY

# Callers (who calls this function)
callers = list(func.getCallingFunctions(monitor))
for c in callers:
    print('  CALLED BY: %s @ %s' % (c.name, c.entryPoint))

# Callees (what does this function call)
callees = list(func.getCalledFunctions(monitor))
for c in callees:
    print('  CALLS: %s @ %s' % (c.name, c.entryPoint))
```

### Gotchas
- `getCallingFunctions()` and `getCalledFunctions()` REQUIRES a `TaskMonitor`) parameter — calling without it gives "No matching overloads found")
- `getReferencesFrom()` returns a **Java array** (`Reference[]`), not an iterator — iterate with `for ref in refs_from:` not `.hasNext()`
- `getReferenceTo()` also returns an iterator, but `getReferencesFrom()` returns an array

---

## 4. Function Analysis

**RATING: VERY USEFUL**

### Key APIs

| API | Description | Status |
|-----|-------------|--------|
| `prog.functionManager.getFunctions(True)` | All functions (includes all namespaces) | WORKS |
| `prog.functionManager.getFunctions(False)` | Same as True in this binary (no difference observed) | WORKS |
| `func.entryPoint` | Entry address of the function | WORKS |
| `func.body` | AddressSetView representing the function's address range | WORKS |
| `func.body.maxAddress` / `.minAddress` | End/start addresses | WORKS |
| `func.body.getNumAddresses()` | Number of addresses (not bytes!) in function body | WORKS |
| `func.parameterCount` | Number of parameters | WORKS |
| `func.parameters` | List of Parameter objects | WORKS |
| `func.returnType` / `func.getReturn().dataType` | Return type | WORKS |
| `func.callingConventionName` | Name like "__thiscall" | WORKS |
| `func.getCallingConvention()` | Full calling convention object | WORKS |
| `func.getParentNamespace()` | The class/namespace the function belongs to | WORKS |
| `func.getPrototypeString(bool, bool)` | Full signature string | WORKS |
| `func.getSignature()` | Signature string | WORKS |
| `func.comment` / `.commentAsArray` | Comments on the function | WORKS |

### Function Size Calculation

```python
start_addr = int(str(func.entryPoint), 16)
end_addr = int(str(func.body.maxAddress), 16)
size_bytes = end_addr - start_addr + 1
num_addresses = func.body.getNumAddresses()  # Different from byte size!
```

### Example: Full Function Analysis

```python
for f in prog.functionManager.getFunctions(True):
    print('NAME: %s' % f.name)
    print('ADDRESS: %s' % f.entryPoint)
    
    start_addr = int(str(f.entryPoint), 16)
    end_addr = int(str(f.body.maxAddress), 16)
    size = end_addr - start_addr + 1
    print('SIZE: %d bytes' % size)
    
    print('PARAMS (%d):' % f.parameterCount)
    for p in f.parameters:
        print('  - %s: %s' % (p.name, p.dataType))
    
    print('RETURN: %s' % f.returnType)
    print('CC: %s' % f.callingConventionName)
    
    # Callers and callees
    callers = list(f.getCallingFunctions(TaskMonitor.DUMMY))
    callees = list(f.getCalledFunctions(TaskMonitor.DUMMY))
```

### Gotchas
- `getPrototypeString()` requires TWO boolean parameters: `getPrototypeString(True, True)` 
- `func.returnType` returns `undefined` for C++ methods (the implicit return is usually void/undefined)
- `getNumAddresses()` returns the count of addressable units (2-byte Thumb instructions in this binary), NOT bytes. For a 176-byte function, it returned 126 addresses (because some instructions are 4 bytes = 2 addresses each).

---

## 5. Data / Symbols

**RATING: USEFUL**

### Symbol Table APIs

| API | Description | Status |
|-----|-------------|--------|
| `prog.symbolTable.getAllSymbols(True)` | All symbols (including forward-declared) | WORKS |
| `prog.symbolTable.getAllSymbols(False)` | Only primary symbols | WORKS |
| `prog.symbolTable.getExternalSymbols()` | External/undefined symbols | WORKS |
| `prog.symbolTable.getGlobalSymbols(String)` | Global symbols filtered by namespace name | WORKS (requires string arg) |
| `prog.symbolTable.getSymbols(Namespace)` | All symbols in a specific namespace | WORKS |
| `prog.symbolTable.getNamespace(String, Namespace)` | Get namespace by name | WORKS |
| `prog.symbolTable.getClassNamespaces()` | All GhidraClass (C++ class) namespaces | WORKS |
| `sym.getParentNamespace()` | The namespace/class containing this symbol | WORKS |
| `ns.getChildren()` | Child symbols of a namespace | WORKS |

### Symbol Types
- Only 2 symbol types exist: **`Function`** and **`Label`**
- Mangled names (e.g., `_ZN7UILayer10networkingEv`) are stored as `Label` type in the Global namespace
- Demangled names (e.g., `networking`) are stored as `Function` type in the appropriate class namespace

### External Symbols

```python
ext_syms = list(prog.symbolTable.getExternalSymbols())
# 306 external symbols found including:
# __cxa_finalize, __android_log_print, printf, memcpy, free, malloc, exit, etc.
```

### Namespace/Category Organization

```python
# Get all C++ class namespaces
nss = list(prog.symbolTable.getClassNamespaces())
# 1502 classes found (e.g., "UILayer (GhidraClass)", "Actor (GhidraClass)", etc.)

# Get symbols in a specific namespace
ns = prog.symbolTable.getNamespace('UILayer', None)
syms = list(prog.symbolTable.getSymbols(ns))
# 94 symbols in UILayer: 91 functions + 3 labels
```

### Data at Addresses

```python
# Get all defined data units
all_data = list(prog.listing.getDefinedData(True))
# 184,818 data units total

# Filter by address range
addr_set = fapi.createAddressSet()
addr_set.addRange(start_addr, end_addr)
data_in_range = list(prog.listing.getDefinedData(addr_set, True))
```

### Gotchas
- `getAllSymbols(True)` returns 328,977 symbols vs 59,521 for `False` — the difference is forward-declared/secondary symbols
- `getGlobalSymbols()` requires a string argument (namespace name), unlike `getAllSymbols()`
- Symbol types are only `Function`) and `Label` — no separate type for data symbols (data has its own `listing.getDefinedData()`)

---

## 6. Program-level APIs

**RATING: USEFUL**

### FlatProgramAPI vs Direct Access

| Aspect | FlatProgramAPI | Direct (prog.*) | Verdict |
|--------|---------------|-----------------|---------|
| Convenience methods | Has `getFunctionAt()`, `toAddr()`, `findBytes()`, etc. | Same via sub-objects | **FLATAPI** — cleaner for quick lookups |
| Current program | `.currentProgram` returns the ProgramDB | Already have it | Same |
| Address conversion | `.toAddr(String)` handles hex strings | Via `prog.addressFactory.toAddr()` | **FLATAPI** is easier |
| Reference access | `.getReferencesTo()`, `.getReferencesFrom()` | Via `prog.referenceManager` | Equivalent |

### Memory/Segments

```python
# All memory blocks (ELF segments/sections)
for mb in prog.memory.getBlocks():
    perms = ('E' if mb.executable else '-') + ('W' if mb.writable else '-') + ('R' if mb.readable else '-')
    start_addr = int(str(mb.start), 16)
    end_addr = int(str(mb.end), 16)
    name = mb.name  # ".text", ".data", ".rodata", etc.

# 26 memory blocks found including: .text, .rodata, .data, .bss, .plt, .got, EXTERNAL, etc.
```

### Reading/Writing Memory Values

```python
# Read a DWORD at an address
dword_val = prog.memory.getInt(addr)

# Read bytes
byte_arr = prog.memory.getBytes(addr, bytearray(256))  # Note: requires pre-allocated byte array

# Write
prog.memory.setByte(addr, 0x42)
prog.memory.setInt(addr, 0x12345678)
```

### String Finding

```python
# Find all strings in the binary
strings = fapi.findStrings(None, 4, 80, False, True)
# 17,530 results found (min length 4, max length 80)
```

### ProgramContext

| API | Description | Status |
|-----|-------------|--------|
| `prog.programContext.getRegisterValue(Register)` | Get register value at a point | WORKS |
| `prog.programContext.setRegisterValue(Register, int)` | Set register value | WORKS |
| `prog.programContext.getRegisters()` | All available registers | WORKS |
| `prog.programContext.getDefaultRegisterValueAddressRanges()` | Where default register values apply | WORKS |

### Gotchas
- `prog.memory.getBytes(addr)` does NOT work — must use `getBytes(addr, bytearray(n))` with pre-allocated buffer
- Memory blocks named `.ARM.attributes::00000000`) have non-hex addresses (like `'ARM.attributes::00000000'`) — need to filter these with `str(mb.start).startswith('EXTERNAL')` check
- `getDefinedData(True)` requires the boolean parameter for "recurse into subranges"

---

## 7. Decompiler Deep Dive

**RATING: VERY USEFUL**

### DecompileOptions (all settable options)

| Option | Purpose | Default |
|--------|---------|---------|
| `setAnalyzeForLoops(True)` | Detect for-loops | False |
| `setBitfieldAccess(True)` | Resolve bitfield access patterns | False |
| `setConventionPrint(True)` | Print calling convention in output | False |
| `setDisplayLineNumbers(True)` | Show line numbers | False |
| `setEOLCommentIncluded(True)` | End-of-line comments | False |
| `setEliminateUnreachable(True)` | Remove unreachable code blocks | False |
| `setHeadCommentIncluded(True)` | Header comments (function name) | False |
| `setIgnoreUnimplemented(True)` | Skip unimplemented functions | False |
| `setInferConstantPointers(True)` | Infer constant pointers | False |
| `setInplaceTokens(True)` | Show inline tokens | False |
| `setNoCastPrint(False)` | Show casts for clarity | True (hide) |
| `setNullToken(True)` | Show null tokens | False |
| `setPLATECommentIncluded(True)` | Plate comments | False |
| `setPOST/GET/PRE/WARNCommentIncluded(True)` | Various comment styles | All False |
| `setPredicate(True)` | Show predicates | False |
| `setRespectReadOnly(True)` | Respect read-only memory | False |
| `setSplitArrays/Pointers/Structures(True)` | Split complex types | All False |

### Decompiler Output Objects

| Object | Type | Description | Status |
|--------|------|-------------|--------|
| `DecompInterface.decompileFunction(func, timeout, monitor)` | `DecompilationResult` | Main entry point | WORKS |
| `result.getDecompiledFunction()` | `DecompiledFunction` | Contains `.c`) (string) and `.signature` | WORKS |
| `result.getCCodeMarkup()` | `ClangTokenGroup` | Full decompiled output as token tree | WORKS |
| `DecompiledFunction.c` | `str` | Single-line Clang C code | WORKS |
| `ClangTokenGroup.numChildren()` | `int` | Number of child tokens | WORKS |
| `ClangTokenGroup.Child(int)` | `ClangTokenGroup`/`ClangSyntaxToken`/`ClangCommentToken`/etc. | Navigate token tree | WORKS |
| `ClangTokenGroup.tokenIterator(bool)` | Iterator of tokens | Iterate all tokens | WORKS |
| `ClangTokenGroup.getHighFunction()` | `HighFunction` | Internal P-code representation | WORKS |

### Token Types (from ClangTokenGroup)

- **`ClangSyntaxToken`** — actual code tokens (keywords, identifiers, operators)
- **`ClangCommentToken`** — comments (`/* WARNING: ... */`)
- **`ClangBreak`** — newline/whitespace
- **`ClangVariableDecl`** — variable declarations (`int iVar1;`)
- **`ClangFuncProto`** — function prototype header

### HighFunction (Internal P-code)

| API | Description | Status |
|-----|-------------|--------|
| `hf.getBasicBlocks()` | All p-code basic blocks | WORKS |
| `hf.getVarnodes(Address, Address)` / `.getVarnodes(AddressSpace)` | Varnodes in a range | WORKS (requires addr args) |
| `hf.getFunction()` | The original Function object | WORKS |
| `hf.getFunctionPrototype()` | Function prototype | WORKS |

### Example: Full Decompilation with Options

```python
opts = DecompileOptions()
opts.grabFromProgram(prog)  # Copy all program-level settings
opts.setAnalyzeForLoops(True)
opts.setBitfieldAccess(True)
opts.setConventionPrint(True)
# ... set ALL boolean options to True for maximum resolution

di = DecompInterface()
di.setOptions(opts)
di.openProgram(prog)
di.toggleJumpLoads(True)  # CRITICAL: enables jumptable/switch recovery
result = di.decompileFunction(func, 60, None)

if result.isValid():
    decFunc = result.getDecompiledFunction()
    ccode = decFunc.c  # Single-line Clang C string
    # Or for formatted output:
    markup = result.getCCodeMarkup()
    
di.flushCache()  # REQUIRED after each decompileFunction call
di.dispose()
```

### Gotchas
- `di.flushCache()` is **REQUIRED** after each `decompileFunction` call — not calling it causes stale results on subsequent calls
- `di.toggleJumpLoads(True)` is **CRITICAL** for functions with switch/jumptable statements
- The decompiled C code comes as a single line — needs custom parsing (split on `{`, `}`, `;`) for multi-line formatting
- `getVarnodes()` requires address range arguments, not a no-arg version

---

## 8. Project Locking / Performance

**RATING: INTERESTING**

### Each Invocation Launches Fresh JVM

Each `python3 -c "..."` or heredoc invocation starts a completely fresh JVM via `pyghidra.start()`. There is **no persistent server mode** or shared state across invocations.

### APIs Found for Project Management

| API | Description | Status |
|-----|-------------|--------|
| `pyghidra.start()` | Launch JVM, init Ghidra headless | WORKS (each call = fresh JVM) |
| `pyghidra.started()` | Check if JVM is already started | EXISTS |
| `open_project(path, name)` | Open existing `.gpr`/`.rep`) project | WORKS |
| `consume_program(project, "/path")` | Load a program from the project | WORKS |
| `project.close()` | Close the project | WORKS |
| `prog.release(consumer)` | Release the program reference | WORKS |
| `project.isClosed()` / `.closed` | Check if project is closed | WORKS |

### Lock Exception Causes

The "lock exception (not directly tested but documented) occurs when:
1. Another process has the Ghidra project open (e.g., running `analyzeHeadless`) while pyghidra tries to open, or vice versa)
2. The same project is opened in the Ghidra GUI while headless mode runs

### Performance Observations

| Operation | Time | Notes |
|-----------|------|-------|
| JVM startup + project open | ~5-10 seconds (not measured precisely) | Each invocation has this overhead |
| `getFunctions(True)` iteration | 23,950 functions in **0.668 seconds** | Fast once JVM is running |
| Processing all function sizes | 23,950 functions in **2.889 seconds** | Including body.maxAddress lookups) |
| `getAllSymbols(True)` | ~329K symbols, fast iteration | Memory intensive but fast |

### PyGhidra API Surface (from `pyghidra.api` module)

```
start()                    # Launch JVM
started()                  # Check if already started
open_project(path, name)   # Open existing project
consume_program(project, "/path")  # Load a program
open_filesystem(path)      # Open from filesystem (not project)
program_context(prog)      # Context manager for program access
program_info(prog)         # Get program info SubOptions
task_monitor()             # Create a TaskMonitor
ghidra_script(func)        # Decorator to run as Ghidra script
walk_programs(project)     # Iterate all programs in project
walk_project(path, name)   # Walk all programs in project dir
```

### Gotchas
- `start()` must be called BEFORE any `from ghidra.*`) imports (the JVM needs to be running first)
- Each invocation is independent — the JVM state is NOT shared
- The "lock exception") happens when a project is already open in another process or GUI

---

## 9. Other Useful APIs

**RATING: USEFUL**

### ProgramContext — Register/Memory Values

| API | Description | Status |
|-----|-------------|--------|
| `ctx.getRegisterValue(Register)` | Get value of a register | WORKS |
| `ctx.setRegisterValue(Register, int)` | Set value of a register | WORKS |
| `ctx.getRegisters()` | All available registers | WORKS |
| `ctx.getRegisterNames()` | Names of all registers | WORKS |
| `ctx.getDefaultRegisterValueAddressRanges()` | Where each default value applies | WORKS |
| `ctx.getValue(Address)` | Get value at address | WORKS |
| `ctx.setValue(Address, int)` | Set value at address | WORKS |

### TaskMonitor — Progress Callbacks

| API | Description | Status |
|-----|-------------|--------|
| `TaskMonitor.DUMMY` | Dumb monitor (no progress display) | WORKS |
| `monitor.cancel()` / `.isCancelled()` | Cancel/Check cancel state | WORKS |
| `monitor.setProgress(int)` / `.getProgress()` | Progress tracking | WORKS |
| `monitor.setMessage(String)` | Status message | WORKS |

### CategoryPath / Namespace Organization

```python
# Get all C++ class namespaces (categories)
nss = list(prog.symbolTable.getClassNamespaces())
# 1,502 classes found

# Get symbols within a namespace
ns = prog.symbolTable.getNamespace('UILayer', None)
syms = list(prog.symbolTable.getSymbols(ns))
# Filter by type: str(s.symbolType) == 'Function') or 'Label'
```

### FlatProgramAPI — Convenience Methods

| Method | Description | Status |
|--------|-------------|--------|
| `fapi.toAddr(String)` | Convert hex string to Address object | WORKS |
| `fapi.getFunctionAt(Address)` | Get function at address | WORKS |
| `fapi.getDataAt(Address)` | Get data at address (or None) | WORKS |
| `fapi.findStrings(None, min_len, max_len, include_null_terminated, include_pascal_strings))` | Find all strings | WORKS (17,530 found) |
| `fapi.findBytes(AddressSetView, pattern_str, min_len, max_len)` | Find byte patterns | WORKS |
| `fapi.createAddressSet()` | Create an AddressSet | WORKS |
| `fapi.analyzeAll(prog)` | Run full analysis | WORKS |
| `fapi.createSymbol(...)` / `.createFunction(...)` / `.createData(...)` | Create symbols/data/functions | WORKS |

### Memory Block Permissions

```python
for mb in prog.memory.getBlocks():
    perms = ('E' if mb.executable else '-') + \
            ('W' if mb.writable else '-') + \
            ('R' if mb.readable else '-')
    # Each block has: start, end, name, executable, writable, readable
```

### Gotchas
- `findStrings()` requires 5 parameters: `(AddressSetView, min_len, max_len, include_null_terminated, include_pascal_strings)` — passing `None`) for the first argument searches the entire program
- `ghidra_script` is a decorator for running Python as Ghidra scripts (not directly useful for our use case)
- `program_info()` returns a `SubOptions` object (Ghidra's options system), not a simple dict

---

## Summary Table

| Area | Rating | Key Finding |
|------|--------|-------------|
| 1. Assembly/Disassembly | **VERY USEFUL** | `prog.listing.getInstructions()`) + `InstructionContext.getMnemonicString()`) gives full disassembly with raw bytes, mnemonics, and operands per instruction |
| 2. CFG/Basic Blocks | **USEFUL** | `SimpleBlockModel`) + `block.getSources()`) (predecessors) + `block.getDestinations()`) (successors for complete CFG |
| 3. References/Call Graph | **VERY USEFUL** | `func.getCallingFunctions(monitor))` and `func.getCalledFunctions(monitor))` give direct caller/callee lists; `referenceManager`) gives raw references |
| 4. Function Analysis | **VERY USEFUL** | Full function metadata: size, params, return type, calling convention, namespace, prototype string, comments |
| 5. Data/Symbols | **USEFUL** | Symbol filtering by namespace/type; external symbol detection; data units in address ranges |
| 6. Program-level APIs | **USEFUL** | Memory block iteration with permissions; `FlatProgramAPI`) convenience methods; memory read/write at arbitrary addresses |
| 7. Decompiler Deep Dive | **VERY USEFUL** | `DecompiledFunction.c` for C code; `ClangTokenGroup`) for AST-level token tree; `HighFunction`) for p-code blocks/varnodes; `flushCache()` required after each call |
| 8. Project Locking/Perf | **INTERESTING** | Each invocation = fresh JVM (~5-10s overhead); no persistent server mode; function iteration is fast once JVM is running (24K functions in <3s) |
| 9. Other APIs | **USEFUL** | `ProgramContext`) for register values; `TaskMonitor.DUMMY`) for progress callbacks; namespace/category organization via `getClassNamespaces()`) |
