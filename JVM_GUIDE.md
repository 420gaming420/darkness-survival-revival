# JVM Guide — Interactive Ghidra API Reference

## Overview

`jvm.py` provides interactive access to the Ghidra decompiler API through a persistent JVM session. Unlike standalone PyGhidra scripts that restart the JVM for every command, jvm.py maintains a single long-lived session for instant responses.

**What works:**
- ✅ Full Ghidra API access (symbols, functions, memory, decompiler, CFG, etc.)
- ✅ Interactive REPL with command history
- ✅ Batch execution with `--exec`
- ✅ Print statement capture
- ✅ Auto-imported common classes

**What doesn't work:**
- ❌ Some Java iterator methods (e.g., `__len__` on iterators)
- ❌ Large result sets may need pagination
- ❌ Certain decompiler initialization sequences

---

## Quick Start

### Check Server Status
```bash
python3 server.py status
```

### Start REPL Mode
```bash
python3 jvm.py
```

### Execute Single Command
```bash
python3 jvm.py "fpa.getFunctionAt(fpa.toAddr('0x3d04c0')).name"
```

### Execute Multi-line Script
```bash
python3 jvm.py --exec "
func = fpa.getFunctionAt(fpa.toAddr('0x3d04c0'))
print(f'Function: {func.name}')
print(f'Params: {func.parameterCount}')
"
```

---

## Available Objects

The following objects are automatically injected into every command:

| Object | Type | Description |
|--------|------|-------------|
| `fpa` | `FlatProgramAPI` | Main API for program operations |
| `prog` | `ProgramDB` | The loaded Ghidra program |
| `mem` | `Memory` | Program memory access |
| `listing` | `CodeUnitListing` | Instruction/data listing |
| `func_mgr` | `FunctionManager` | Function enumeration |

Auto-imported classes (no import needed):
- `TaskMonitor` — Progress tracking
- `AddressSet` — Address range operations
- `SimpleBlockModel` — CFG basic blocks
- `DecompInterface` — Decompiler
- `DecompileOptions` — Decompiler settings

---

## Basic Operations

### 1. Symbol Table

```python
# Get all symbols
all_syms = list(prog.symbolTable.getAllSymbols(True))
print(f'Total: {len(all_syms)}')

# Get primary symbols only
primary = list(prog.symbolTable.getAllSymbols(False))

# Get external symbols
ext = list(prog.symbolTable.getExternalSymbols())

# Get symbols by namespace
ns = prog.symbolTable.getNamespace('UILayer', None)
syms = list(prog.symbolTable.getSymbols(ns))

# Get all C++ classes
classes = list(prog.symbolTable.getClassNamespaces())
```

### 2. Function Manager

```python
# Enumerate functions
funcs = list(func_mgr.getFunctions(True))
print(f'Total functions: {len(funcs)}')

# Get function properties
func = fpa.getFunctionAt(fpa.toAddr('0x3d04c0'))
print(f'Name: {func.name}')
print(f'Address: {func.entryPoint}')
print(f'Params: {func.parameterCount}')
print(f'CC: {func.callingConventionName}')
print(f'Return: {func.returnType}')

# Get prototype string
proto = func.getPrototypeString(True, True)

# Call graph
callers = list(func.getCallingFunctions(TaskMonitor.DUMMY))
callees = list(func.getCalledFunctions(TaskMonitor.DUMMY))
```

### 3. Memory Access

```python
# Convert address string to Address object
addr = fpa.toAddr('0x3d04c0')

# Read different types
val = prog.memory.getInt(addr)
val_short = prog.memory.getShort(addr)
val_byte = prog.memory.getByte(addr)

# Read bytes into buffer
buf = bytearray(16)
prog.memory.getBytes(addr, buf)

# List memory blocks
for block in prog.memory.getBlocks():
    perms = ''
    if block.executable: perms += 'E'
    if block.writable: perms += 'W'
    if block.readable: perms += 'R'
    print(f'{block.name}: {block.start}-{block.end} [{perms}]')
```

### 4. Instructions

```python
# Get instructions in range
addr_set = AddressSet()
addr_set.addRange(fpa.toAddr('0x3d04c0'), fpa.toAddr('0x3d04c7'))
instrs = list(prog.listing.getInstructions(addr_set, True))

# Access instruction details
for instr in instrs:
    ctx = instr.getInstructionContext()
    mnemonic = ctx.getMnemonicString()
    print(f'{instr.address}: {mnemonic}')
```

### 5. Data Units

```python
# Get all defined data
data = list(prog.listing.getDefinedData(True))
print(f'Total data units: {len(data)}')

# Get data in range
addr_set = AddressSet()
addr_set.addRange(fpa.toAddr('0x1000'), fpa.toAddr('0x2000'))
data_in_range = list(prog.listing.getDefinedData(addr_set, True))
```

### 6. Strings

```python
# Find all strings
strings = list(fpa.findStrings(None, 4, 80, False, True))
print(f'Total strings: {len(strings)}')

# Find strings in range
addr_set = AddressSet()
addr_set.addRange(fpa.toAddr('0x1000'), fpa.toAddr('0x10000'))
strings_in_range = list(fpa.findStrings(addr_set, 4, 80, False, True))
```

---

## Control Flow Graph

### Basic Blocks

```python
# Create block model
sbm = SimpleBlockModel(prog, True)

# Get blocks for a function
func = fpa.getFunctionAt(fpa.toAddr('0x3d04c0'))
body = func.body
blocks = [b for b in sbm.getCodeBlocks(TaskMonitor.DUMMY)
          if body.contains(b.firstStartAddress)]

print(f'Basic blocks: {len(blocks)}')

# Iterate blocks
for block in blocks:
    print(f'Block: {block.firstStartAddress}-{block.maxAddress}')
```

### Block References

```python
# Get predecessors (incoming edges)
for block in blocks:
    src_iter = block.getSources(TaskMonitor.DUMMY)
    for ref in src_iter:
        print(f'  Predecessor: {ref.sourceBlock.firstStartAddress}')

# Get successors (outgoing edges)
    dest_iter = block.getDestinations(TaskMonitor.DUMMY)
    for ref in dest_iter:
        print(f'  Successor: {ref.destinationBlock.firstStartAddress}')
        print(f'    Flow: {ref.flowType}')
```

---

## References and Call Graph

### Get References

```python
func = fpa.getFunctionAt(fpa.toAddr('0x3d04c0'))

# References FROM this address
refs_from = prog.referenceManager.getReferencesFrom(func.entryPoint)
print(f'References from: {len(refs_from)}')

# References TO this address
refs_to = prog.referenceManager.getReferencesTo(func.entryPoint)
print(f'References to: {len(refs_to)}')

# Inspect reference
for ref in refs_from:
    print(f'  {ref.fromAddress} -> {ref.toAddress} ({ref.referenceType})')
```

### Call Graph

```python
# Callers (who calls this function)
callers = list(func.getCallingFunctions(TaskMonitor.DUMMY))

# Callees (what this function calls)
callees = list(func.getCalledFunctions(TaskMonitor.DUMMY))

for caller in callers:
    print(f'Called by: {caller.name} @ {caller.entryPoint}')

for callee in callees:
    print(f'Calls: {callee.name} @ {callee.entryPoint}')
```

---

## Decompiler

### Basic Usage

```python
# Create decompiler
di = DecompInterface()
opts = DecompileOptions()
di.setOptions(opts)
di.openProgram(prog)

# Decompile function
func = fpa.getFunctionAt(fpa.toAddr('0x3d04c0'))
result = di.decompileFunction(func, 60, None)

if result.isValid():
    # Get C code
    ccode = result.getCCodeMarkup()
    print(ccode)

    # Or get single-line version
    dec_func = result.getDecompiledFunction()
    print(dec_func.c)
else:
    print(f'Error: {result.getErrorString()}')

# IMPORTANT: Clean up
di.flushCache()
di.dispose()
```

### Advanced Options

```python
opts = DecompileOptions()
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
opts.setSplitArrays(True)
opts.setSplitPointers(True)
opts.setSplitStructures(True)
opts.setWARNCommentIncluded(True)

di.setOptions(opts)
di.toggleJumpLoads(True)  # Critical for switch/jumptable recovery
```

---

## ProgramContext

### Register Access

```python
# Get all registers
regs = list(prog.programContext.getRegisters())
print(f'Available registers: {len(regs)}')

# Get register value at address
addr = fpa.toAddr('0x3d04c0')
val = prog.programContext.getRegisterValue(regs[0], addr)

# Set register value
prog.programContext.setRegisterValue(regs[0], addr, 0x42)
```

---

## Floating-Point Constants

Hex constants in decompiled code are often IEEE 754 floats. Decode them with jvm.py:

```bash
# Decode single value
python3 jvm.py "import struct; struct.unpack('f', struct.pack('I', 0xbf800000))[0]"

# Decode multiple values in one command
python3 jvm.py --exec "
import struct
values = [0xbf800000, 0x3f800000, 0x00000000, 0xbf0ccccd]
for v in values:
    f = struct.unpack('f', struct.pack('I', v))[0]
    print(f'0x{v:08x} = {f}')
"
```

### Common Constants

| Hex | Float | Meaning |
|-----|-------|---------|
| `0xbf800000` | -1.0 | Negative one |
| `0x3f800000` | 1.0 | Positive one |
| `0x00000000` | 0.0 | Zero |
| `0xbf000000` | -0.5 | Negative half |
| `0x3f000000` | 0.5 | Positive half |
| `0xbf333333` | -0.7 | Negative 0.7 |
| `0x3f333333` | 0.7 | Positive 0.7 |
| `0x40000000` | 2.0 | Two |
| `0xbf0ccccd` | -0.55 | Game-specific threshold |

### Decode via jvm.py

```python
import struct

# Decode hex to float
float_val = struct.unpack('f', struct.pack('I', 0xbf800000))[0]
print(f'0xbf800000 = {float_val}')

# Encode float to hex
hex_val = struct.unpack('I', struct.pack('f', -1.0))[0]
print(f'-1.0f = 0x{hex_val:08x}')
```

**One-liner for quick lookup:**
```bash
python3 jvm.py "import struct; struct.unpack('f', struct.pack('I', 0xbf800000))[0]"
```

---

## REPL Tips

### Navigation
- Up/Down arrows: Command history
- Ctrl+C: Cancel current input
- `exit`, `quit`, or `q`: Exit REPL
- Empty line: Skip

### Output Handling
- Expression results: Shown automatically
- Print statements: Captured and displayed
- Multi-line: Use `--exec` mode or enter lines until valid Python

### Error Handling
- Syntax errors: Shown with line number
- Java exceptions: Full traceback displayed
- Missing objects: Check spelling and case

---

## Common Patterns

### Find Function by Name
```python
target = 'networking'
for func in func_mgr.getFunctions(True):
    if target in func.name:
        print(f'{func.name} @ {func.entryPoint}')
```

### Analyze Function
```python
func = fpa.getFunctionAt(fpa.toAddr('0x3d04c0'))

# Basic info
print(f'Name: {func.name}')
print(f'Address: {func.entryPoint}')
print(f'Size: {int(str(func.body.maxAddress), 16) - int(str(func.entryPoint), 16) + 1} bytes')
print(f'Params: {func.parameterCount}')

# Call graph
callers = list(func.getCallingFunctions(TaskMonitor.DUMMY))
callees = list(func.getCalledFunctions(TaskMonitor.DUMMY))
print(f'Callers: {len(callers)}, Callees: {len(callees)}')
```

### Extract Strings
```python
strings = list(fpa.findStrings(None, 4, 100, False, True))
for s in strings[:20]:
    print(f'{s.address}: {s.string}')
```

### Dump Function Disassembly
```python
func = fpa.getFunctionAt(fpa.toAddr('0x3d04c0'))
addr_set = AddressSet()
addr_set.addRange(func.entryPoint, func.body.maxAddress)
instrs = list(prog.listing.getInstructions(addr_set, True))

for instr in instrs:
    ctx = instr.getInstructionContext()
    mnemonic = ctx.getMnemonicString()
    ops = [str(op) for op in ctx.getOpObjects(0)]
    print(f'{instr.address}: {mnemonic} {" ".join(ops)}')
```

---

## Troubleshooting

### "NameError: name 'X' is not defined"
Use auto-imported classes or import explicitly:
```python
from ghidra.util.task import TaskMonitor
```

### Iterator has no `__len__`
Convert to list first:
```python
funcs = list(func_mgr.getFunctions(True))
print(len(funcs))
```

### Decompiler fails with NullPointerException
Ensure proper initialization:
```python
di = DecompInterface()
opts = DecompileOptions()
di.setOptions(opts)
di.openProgram(prog)
# ... decompile ...
di.flushCache()
di.dispose()
```

### Large output truncated
Print in chunks:
```python
for i, func in enumerate(funcs[:100]):
    print(f'{i}: {func.name}')
```

### Server not responding
```bash
python3 server.py status
python3 server.py restart
```

---

## Performance Notes

- **First command**: ~9 seconds (server startup + analysis)
- **Subsequent commands**: <100ms
- **Decompilation**: ~0.005 seconds per function on an NVME SSD


### --benchmark 120 on an NVME SSD
```bash
========================================================================================================================
SUMMARY
------------------------------------------------------------------------------------------------------------------------
Step                 AVG      MIN      MAX      P90      P95
------------------------------------------------------------------------------------------------------------------------
find_function      0.000    0.000    0.000    0.000    0.000
make_filename      0.000    0.000    0.000    0.000    0.000
decompile          0.001    0.001    0.002    0.002    0.002
format_c           0.000    0.000    0.001    0.001    0.001
assembly           0.000    0.000    0.000    0.000    0.000
cfg                0.000    0.000    0.000    0.000    0.000
refs               0.000    0.000    0.001    0.000    0.000
write              0.001    0.000    0.009    0.001    0.003
total              0.003    0.002    0.011    0.003    0.005

========================================================================================================================
PROJECTION (23949 functions)
  Estimated total:  1 min  (0.003s avg × 23949)
  Estimated at p95: 2 min  (0.005s × 23949)
========================================================================================================================
```

- **Full export**: Runs in background thread

The JVM session persists across commands, making iterative exploration fast after initial startup.

---

## Advanced: Custom Analysis Scripts

Save complex analysis as Python scripts:

```python
# analyze.py
import sys
sys.path.insert(0, '/path/to/project')

from src.ui.server.client import rpc

def analyze():
    code = """
    funcs = list(func_mgr.getFunctions(True))
    for func in funcs:
        if 'network' in func.name.lower():
            callers = list(func.getCallingFunctions(TaskMonitor.DUMMY))
            print(f'{func.name}: {len(callers)} callers')
    """
    result = rpc('execute', {'code': code})
    print(result['result'])

if __name__ == '__main__':
    analyze()
```

Run with:
```bash
python3 analyze.py
```

---

## Real-World Examples

### Example 1: Analyzing a Constructor
```bash
python3 jvm.py --exec "
# Find and decompile GameData constructor
func = fpa.getFunctionAt(fpa.toAddr('0x3918b0'))
print(f'Function: {func.name}')
print(f'Address: {func.entryPoint}')

# Decompile with full options
di = DecompInterface()
opts = DecompileOptions()
di.setOptions(opts)
di.openProgram(prog)
result = di.decompileFunction(func, 60, None)

if result.isValid():
    print('\\n=== Decompiled Code ===')
    print(result.getCCodeMarkup())
else:
    print(f'Error: {result.getErrorString()}')

di.flushCache()
di.dispose()
"
```

### Example 2: Analyzing Structure Offsets
```bash
python3 jvm.py --exec "
func = fpa.getFunctionAt(fpa.toAddr('0x3918b0'))

# Analyze the structure being initialized
print('=== Structure Analysis ===')
print('Offset 0x000: vtable pointer')
print('Offset 0x008: integer field')
print('Offset 0x860: array from DAT_00842e18')
print('Offset 0x8f4: integer array (sentinels)')
print('Offset 0xa1c: float array (initialized to -1.0f)')
print('Offset 0xab0: struct array (184 elements)')
print('Offset 0xf60: integer array (sentinels)')
print('Total size: ~0x1030 bytes')
"
```

### Example 3: Identifying Float Constants
```bash
python3 jvm.py --exec "
import struct

# Common float constants in the binary
constants = {
    0xbf800000: '-1.0f',
    0x3f800000: '1.0f',
    0x00000000: '0.0f',
    0xbf0ccccd: '-0.55f',
    0x3f000000: '0.5f',
}

print('=== Float Constant Reference ===')
for hex_val, label in constants.items():
    float_val = struct.unpack('f', struct.pack('I', hex_val))[0]
    print(f'{hex_val:08x} = {float_val:10.6f}  ({label})')
"
```

### Example 4: Reading Data Tables
```bash
python3 jvm.py --exec "
# Read initial values from DAT_00842e18
print('=== Source Data Table (DAT_00842e18) ===')
for i in range(10):
    addr = 0x842e18 + i * 4
    val = prog.memory.getInt(fpa.toAddr(addr))
    print(f'  [{i:2d}] 0x{val:08x} = {val}')
"
```

### Example 5: VTable Analysis
```bash
python3 jvm.py --exec "
# Analyze GameData vtable
vtable_addr = fpa.toAddr('0xb27128')
print('=== VTable at 0xb27128 ===')
for i in range(10):
    addr = fpa.toAddr(0xb27128 + i * 4)
    func_addr = prog.memory.getInt(addr)
    func = fpa.getFunctionAt(fpa.toAddr(func_addr))
    func_name = func.name if func else '<unknown>'
    print(f'  [{i:2d}] 0x{func_addr:08x}: {func_name}')
"
```

---

## Summary

jvm.py provides powerful interactive access to the entire Ghidra API, use it for:
- Interactive reverse engineering
- Batch analysis and reporting
- Custom tool development
- Learning the Ghidra API
- Understanding structure layouts
- Identifying magic constants
