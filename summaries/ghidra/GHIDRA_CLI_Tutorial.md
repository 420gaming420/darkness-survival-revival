# How to Setup a New Ghidra Project in the CLI

This tutorial walks you through creating a new Ghidra project and importing a binary file using the headless (CLI-only) analyzer. No GUI is required.

---

## Prerequisites

- Ghidra is installed and the `support/analyzeHeadless` script is available
- Java 21+ is installed and on your `PATH`
- The binary you want to analyze is accessible from the filesystem

---

## Step 1 — Set the Ghidra Installation Path

```bash
export GHIDRA_INSTALL_DIR="/path/to/ghidra"
```

This environment variable tells the headless analyzer where to find the Ghidra installation. Without it, the script won't know where to look for jars, processors, and scripts.

---

## Step 2 — Create a Project Directory

```bash
mkdir -p /path/to/ghidra/projects
```

Ghidra stores each project in its own folder under this directory. You can have multiple projects within the same parent directory.

---

## Step 3 — Run `analyzeHeadless` to Create the Project and Import a Binary

The core command is:

```bash
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" \
    "/path/to/ghidra/projects" \
    MyProjectName \
    -import /path/to/binary.bin \
    -processor "ARM:LE:32:v5t" \
    -cspec apcs \
    -noanalysis \
    -overwrite
```

### Parameter Breakdown

| Parameter | Description |
|---|---|
| `/path/to/ghidra/projects` | **Project location** — the parent directory where the project will be created |
| `MyProjectName` | **Project name** — a folder named after this will be created inside the project location |
| `-import /path/to/binary.bin` | Path to the binary file (or directory of binaries) to import |
| `-processor "ARM:LE:32:v5t"` | Target processor and language ID. See Step 4 for how to find these |
| `-cspec apcs` | Compiler specification ID. See Step 4 for how to find these |
| `-noanalysis` | Skip auto-analysis (optional — remove this flag if you want full analysis) |
| `-overwrite` | Overwrite the file if it already exists in an existing project |

### Real Example Used in This Repository

```bash
export GHIDRA_INSTALL_DIR="~/GIT/Tools/ghidra"

"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" \
    "~/GIT/Tools/ghidra/project" \
    ds_offline \
    -import "~/GIT/Tools/ghidra/libcocos2dcpp.so" \
    -processor "ARM:LE:32:v5t" \
    -cspec apcs \
    -noanalysis \
    -overwrite
```

This creates a project called `ds_offline` in `./project/` and imports `libcocos2dcpp.so` as an ARM 32-bit little-endian binary using the APCS compiler spec.

---

## Step 4 — Finding the Correct Processor and Compiler Spec IDs

The `-processor` and `-cspec` flags require exact language IDs from Ghidra's processor definition files (`.ldefs`). Here's how to find them:

### Find Available Processors

```bash
find "$GHIDRA_INSTALL_DIR/Ghidra/Processors" -name "*.ldefs"
```

Each processor has a `data/languages/*.ldefs` file. For ARM, it's at:

```
$GHIDRA_INSTALL_DIR/Ghidra/Processors/ARM/data/languages/ARM.ldefs
```

### Extract Language IDs

```bash
grep 'id=' "$GHIDRA_INSTALL_DIR/Ghidra/Processors/ARM/data/languages/ARM.ldefs"
```

Each `<language>` element has an `id` attribute — that's your `-processor` value:

```xml
<language processor="arm"
    endian="little"
    size="32"
    variant="v5t"
    slafile="arm.sla"
    id="ARM:LE:32:v5t">
```

Each `<compiler>` element has an `id` attribute — that's your `-cspec` value:

```xml
<compiler name="APCS" spec="ARM_apcs.cspec" id="apcs"/>
```

### Common Language IDs

| Architecture | Processor ID | Compiler Spec ID |
|---|---|---|
| ARM 32-bit LE v5t | `ARM:LE:32:v5t` | `apcs`, `default` |
| ARM 32-bit BE v7 | `ARM:BE:32:v7` | `apcs`, `default` |
| x86 32-bit | `x86:LE:32:default` | `gcc`, `windows`, `default` |
| x86 64-bit | `x86:LE:64:default` | `gcc`, `windows`, `default` |

---

## Step 5 — Verify the Project Was Created

After running the command, check that the project files exist:

```bash
ls /path/to/ghidra/projects/MyProjectName*
```

You should see:
- `MyProjectName.gpr` — the project reference file
- `MyProjectName.rep/` — the repository directory containing the imported binary and metadata

---

## Step 6 — Re-run Analysis on an Existing Project (Optional)

If you imported with `-noanalysis` and want to run analysis later:

```bash
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" \
    "/path/to/ghidra/projects" \
    MyProjectName \
    -process '*' \
    -recursive
```

This runs full analysis on all binaries in the project.

---

## Step 7 — Decompile a Function with PyGhidra

PyGhidra is the Python API for Ghidra. You can use it to open a project, find a function by its mangled or demangled name, and decompile it — all from the command line via a shell heredoc.

### The Command

```bash
export GHIDRA_INSTALL_DIR="/path/to/ghidra"

python3 -c "
import sys
sys.path.insert(0, '\$GHIDRA_INSTALL_DIR/Ghidra/Features/PyGhidra/pypkg/src')
from pyghidra import start, open_project, consume_program

# 1. Start the JVM and initialize Ghidra headlessly
start()

# 2. Open the existing project (created in Step 3)
project = open_project('/path/to/ghidra/projects', 'MyProjectName')

# 3. Load the program from the project
#    The path starts with '/' — this is the project-internal path, not a filesystem path
prog, consumer = consume_program(project, '/your_binary.so')

# 4. Find the function by iterating all symbols
TARGET = '_ZN7UILayer10networkingEv'   # mangled C++ name (or use demangled name)
for s in prog.symbolTable.getAllSymbols(True):
    if TARGET in str(s.name):
        addr = s.address
        func = prog.functionManager.getFunctionAt(addr)
        print(f'Found: {func.name} at {func.entryPoint}')

        # 5. Configure the decompiler with full options (matches GUI "complete analyze")
        from ghidra.app.decompiler import DecompInterface, DecompileOptions
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
        opts.setNoCastPrint(False)       # show casts for clarity
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

        # 6. Run the decompiler
        di = DecompInterface()
        di.setOptions(opts)
        di.openProgram(prog)
        di.toggleJumpLoads(True)       # resolve switch/jumptable functions

        result = di.decompileFunction(func, 60, None)
        if not result or not result.isValid():
            err = result.getErrorString() if result else 'no result'
            print(f'[ERROR] Decompilation failed: {err}')
            di.dispose()
            prog.release(consumer)
            project.close()
            sys.exit(1)

        # 7. Print the decompiled C code
        ccode = result.getCCodeMarkup()
        print('=== DECOMPILED C CODE ===')
        for line in str(ccode).splitlines():
            print(line)

        di.flushCache()   # required after each decompileFunction call
        di.dispose()
        break              # stop after finding the first match

# 8. Cleanup
prog.release(consumer)
project.close()
" 2>&1
```

### Finding the Right Symbol Name

If you don't know the exact mangled or demangled name, list all symbols first:

```bash
python3 -c "
import sys
sys.path.insert(0, '/path/to/ghidra/Ghidra/Features/PyGhidra/pypkg/src')
from pyghidra import start, open_project, consume_program
start()
project = open_project('/path/to/project', 'MyProjectName')
prog, consumer = consume_program(project, '/your_binary.so')

# Search for any symbol containing 'UILayer' or 'networking'
for s in prog.symbolTable.getAllSymbols(True):
    name = str(s.name)
    if 'UILayer' in name or 'networking' in name:
        print(f'{s.address} {name}')

prog.release(consumer)
project.close()
" 2>&1
```

### Key Points

- The project path in `consume_program` is **not** a filesystem path — it's the path inside the Ghidra project, always starting with `/` (e.g., `/libcocos2dcpp.so`)
- `getAllSymbols(True)` includes forward-declared symbols; use `(False)` for only primary symbols if you want fewer results
- Always call `di.flushCache()` after each `decompileFunction` and before the next one
- The 60-second timeout in `decompileFunction(func, 60, None)` is generous — reduce it for small functions or increase for large/complex ones

---

## Step 8 — Refresh a Stale Binary in the Project

If the binary on disk changes (e.g., you hex-patch it, rebuild it, or revert a modification), the version stored inside the Ghidra project becomes stale. Running PyGhidra will still decompile the old version unless you re-import.

### The Problem

```bash
# Original SHA256: cbade1953d3cf3ed0e78d5e9f3a76fdac041bd0622d748add8e8f8fb6627b462
# You hex-patch the binary and save it back to the same path.

# Now run PyGhidra — it still shows the stale decompiled output, not the new one.
```

### The Solution: Re-import with `-overwrite`

Run `analyzeHeadless` again with the same parameters but using `-overwrite`. Ghidra will delete the old program file from the project and replace it with the current version on disk:

```bash
export GHIDRA_INSTALL_DIR="/path/to/ghidra"

"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" \
    "/path/to/ghidra/projects" \
    MyProjectName \
    -import /path/to/binary.bin \
    -processor "ARM:LE:32:v5t" \
    -cspec apcs \
    -noanalysis \
    -overwrite
```

### Real Example

```bash
export GHIDRA_INSTALL_DIR="~/GIT/Tools/ghidra"

# After reverting libcocos2dcpp.so back to its original version:
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" \
    "~/GIT/Tools/ghidra/project" \
    ds_offline \
    -import "~/GIT/Tools/ghidra/libcocos2dcpp.so" \
    -processor "ARM:LE:32:v5t" \
    -cspec apcs \
    -noanalysis \
    -overwrite
```

The output confirms the old file was replaced:

```
INFO  /libcocos2dcpp.so: file deleted (admin) (LocalFileSystem)
WARN  REPORT: Removed conflicting program file from project: /libcocos2dcpp.so (HeadlessAnalyzer)
INFO  /libcocos2dcpp.so: file created (admin) (LocalFileSystem)
INFO  REPORT: Save succeeded for: /libcocos2dcpp.so (ds_offline:/libcocos2dcpp.so
```

### Verify the Re-import Worked

Run your PyGhidra decompilation again — it will now show the updated logic:

```bash
# The SHA256 should match the current file on disk:
sha256sum /path/to/binary.bin

# Then re-run the PyGhidra script from Step 7 to confirm fresh output.
```

### Why This Happens

Ghidra stores a **copy** of each imported file inside its `.rep` directory. The headless analyzer does not automatically detect that the original file on disk has changed between sessions. The `-overwrite` flag tells it to delete the stale copy in the project and write the current version from disk.

---

## Useful Flags Reference

| Flag | Description |
|---|---|
| `-noanalysis` | Skip auto-analysis (faster import) |
| `-overwrite` | Overwrite existing files in the project |
| `-recursive` | Recurse into directories for both `-import` and `-process` |
| `-log /path/to/log.txt` | Write analysis log to a file instead of default location |
| `-analysisTimeoutPerFile 300` | Timeout each file's analysis at 300 seconds |
| `-loader ElfLoader` | Force a specific loader (e.g., `ElfLoader`, `PeLoader`, `BinaryLoader`) |
| `-deleteProject` | Delete the project after processing completes |
| `-readOnly` | Don't save changes to the project |

---

## Troubleshooting

### "Headless analyzer may not run if project is already open in Ghidra"

Close any running Ghidra GUI instances before running headless commands.

### "Unknown language" error

Double-check your `-processor` and `-cspec` values against the `.ldefs` files. They are case-sensitive and must match exactly.

### Java not found / wrong version

Ensure Java 21+ is on your `PATH`:
```bash
java -version
```

### Slow import

Add `-max-cpu 4` (or your core count) to use multiple CPU cores during analysis.

---

## Summary

1. Set `GHIDRA_INSTALL_DIR`
2. Create a project directory with `mkdir -p`
3. Run `analyzeHeadless` with `-import`, `-processor`, and `-cspec`
4. Verify the `.gpr` and `.rep` files were created
5. Optionally re-run analysis or run scripts
6. Use PyGhidra to find and decompile any function by symbol name
7. Re-import with `-overwrite` when the binary on disk changes

That's all you need to create Ghidra projects, decompile functions, and keep them in sync from the command line.
