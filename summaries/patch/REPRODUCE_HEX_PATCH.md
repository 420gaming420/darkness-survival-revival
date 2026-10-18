# REPRODUCE_HEX_PATCH.md

## Goal

Modify `libcocos2dcpp.so` from the abandoned Android game **Darkness Survival** (package: `com.zeroplusplus.rpg1`) to bypass all connection requirements and reach the main menu. The game is an abandoned Cocos2d-x title whose servers have been offline since ~2021, making it unplayable without a patch.

## What You'll End Up With

Four hex patches applied to the binary that:
1. Force the connection state machine into CONNECTING mode
2. Make network status checks pass
3. Return "success" from the result checker
4. Bypass the error popup and loading screen

The app will boot directly to the main menu without ever connecting to a server.

## Step 1: Understand the Target Binary

### File Location

The binary we're patching:
```
project/lib/armeabi/libcocos2dcpp.so
```

This is a **stripped ARM32 ELF shared object** — the C++ library that contains all the game logic. It's inside an APK at `lib/armeabi/libcocos2dcpp.so`.

### Binary Characteristics

```bash
file project/lib/armeabi/libcocos2dcpp.so
ELF 32-bit LSB shared object, ARM, EABI5 version 1 (SYSV), dynamically linked, interpreter /system/bin/linker, stripped
```

Key facts:
- **32-bit ARM** — each instruction is either 2 bytes (Thumb) or 4 bytes (ARM state)
- **EABI5** — Android's ABI version 5
- **stripped** — no symbol names in the binary; we must find functions by other means
- **dynamically linked** — uses system libraries like libc, libstdc++

### THE CRITICAL DISCOVERY: This is a THUMB Binary

**This is the most important thing to remember.** Even though it's an ARM32 binary, it uses **Thumb (2-byte) instructions**, NOT standard ARM (4-byte) instructions. This affects EVERYTHING — disassembly, patching, and byte ordering.

- Standard ARM: each instruction = 4 bytes
- Thumb: each instruction = 2 bytes
- The Cocos2d-x game engine compiled for Thumb to save space on mobile

**Thumb byte ordering matters:** For a 16-bit Thumb word `0xNNMM`, it's stored in memory as `[0xMM, 0xNN]` (LOW byte first). When writing patches, you must reverse each pair of bytes.

### Symbol Table Comparison with Reference Binary

The game uses Cocos2d-x. There's a reference binary from the Cocos2d-x cpp-tests project that has similar functions with proper symbol names:

```bash
# Extract symbols from target (stripped — mostly empty)
arm-linux-gnueabihf-objdump -t project/lib/armeabi/libcocos2dcpp.so | grep '^[0-9a-f]' | awk '{print $4}' | sort > /tmp/target_symbols.txt

# Extract symbols from reference (has full symbols)
arm-linux-gnueabihf-objdump -t sources/cocos2d-x/tests/cpp-tests/proj.android/obj/local/armeabi/libcocos2dcpp.so | grep '^[0-9a-f]' | awk '{print $4}' | sort > /tmp/test_symbols.txt

# Count common symbols
comm -12 /tmp/target_symbols.txt /tmp/test_symbols.txt | wc -l   # ~23,000+ common
comm -23 /tmp/target_symbols.txt /tmp/test_symbols.txt | wc -l   # Target-only (mostly mangled C++)
```

The target has **~85% common symbols** with the cpp-tests reference. Most are mangled C++ names like `_ZN7UILayer10networkingEv`. The binary is "stripped" in the sense that debug info is removed, but many function symbols survive.

### Finding String IDs in the Binary

The game uses `TextDataManager::getText(int)` for ALL strings. You'll see `getText(2223)`, `getText(2696)`, etc. in decompiled code instead of literal strings. The mapping is in `textdata_en.dat`.

### Key String IDs Found

| ID | Text | Where It Appears |
|----|------|-----------------|
| **2222** | "Connecting to the Server" | Loading screen title |
| **2223** | "Failed to connect to server. Try again later." | Error popup (the one blocking you) |
| **2224** | "Invalid purchase" | In-app purchase errors |
| **2225** | "You don't have enough ancient coins." | Currency check |
| **2226** | "The box could not be found." | Loot box error |
| **2227** | "Box data does not match." | Loot box validation |
| **2696** | "New version has been released..." | Version check error |
| **2700** | "Sorry, we're having a problem connecting..." | Alt connection error |

To look up a specific ID:
```bash
python3 decode_gettext.py 2223
getText(2223) = "Failed to connect to server. Try again later."
```

## Step 2: Address Mapping (CRITICAL)

### The Problem

When Ghidra loads the ELF, it places it at image base **0x10000** (a default for stripped ELFs). But on the actual Android device, the library loads at **VMA base 0xc53d0000**. You need to convert between offset base address spaces:

| Address Space | What It Is | Example |
|---------------|------------|---------|
| **File offset** | Position in the binary file on disk | `0x3d15e4` |
| **Ghidra offset** | Address as Ghidra sees it (file_offset + 0x10000) | `0x3d15e4 + 0x10000 = 0x3eb5e4` |
| **VMA** | Address on the Android device in memory | `0x3d15e4 + 0xc53d0000 = 0xc57a15e4` |

### The Formula

```
Ghidra offset = File offset + 0x10000
VMA           = File offset + 0xc53d0000
File offset   = Ghidra offset - 0x10000
              = VMA - 0xc53d0000
```

### Important: Use FILE OFFSETS with pyghidra

Even though Ghidra loads at 0x10000, when calling `api.getFunctionAt()` and `api.toAddr()`, **use the file offset directly** (NOT file_offset + 0x10000). The pyghidra API resolves it correctly:

```python
# CORRECT — use file offset directly
func = api.getFunctionAt(api.toAddr(0x3d15e4))

# WRONG — don't add 0x10000
func = api.getFunctionAt(api.toAddr(0x3eb5e4))
```

This was discovered through trial and error. The symbol table uses file offsets, so that's what pyghidra expects.

## Step 3: Decompile Key Functions with Ghidra

### The Decompilation Script

Use tools/decompile to get the decompiled code of a function.

## Step 4: Understand the Game's Connection Flow

### The Big Picture

The game uses a **timer-driven state machine** to handle connection status. Here's the high-level flow:

```
App starts up
  → cocos_android_app_init() [JNI entry point]
    → AppDelegate::applicationDidFinishLaunching()
      → Create UILayer
        → openConnectingServer() — shows "Connecting to the Server" loading screen
        → Start timer (fires every ~3 seconds)

Each timer tick:
  TimerTargetSelector::trigger()
    → UILayer::onTimer(3.0f)
      → UILayer::networking() [THE CORE FUNCTION]
        ├── Check connection state
        ├── If disconnected: try connect → show error popup → disconnect → return
        └── If connected: sync time → get progress → dispatch "connect" event → MAIN MENU

The game is STUCK in the disconnected branch because the server never responds.
```

### The Core Function: `UILayer::networking()`

**File offset:** `0x3d15e4`  
**VMA:** `0xc57915e4`  
**Symbol:** `_ZN7UILayer10networkingEv`

This function is called every ~3 seconds by the timer. It handles ALL connection state transitions. Understanding this function is the key to patching the game.

### Why the Game Is Stuck

The flow is:
1. `getGameNetState()` returns 2 (CONNECTING) → OK
2. `getNetworkStatus()` returns -5 (DISCONNECTED, because server is dead)
3. Status == -5 → call `connectGameServer()` → fails silently
4. Show error popup with `getText(2223)`
5. Call `disconnect()` to reset state
6. Call `openConnectingServer()` again → shows loading screen
7. Call `getPacketType()` → **RETURNS** (jumptable)
8. `getResult()` at line ~107 **NEVER EXECUTES** because step 7 already returned

The game is stuck showing the "Connecting to Server" loading screen forever because:
- The error popup shows, you tap retry
- `getPacketType()` returns before reaching `getResult()`
- The function exits without dispatching the "connect" event
- The loading screen never hides (no `closeConnectingServer()` call in the success path)

## Step 5: Disassemble with objdump (THUMB Mode)

### Why `--disassembler=arm` Works for Thumb

Even though this is a Thumb binary, `arm-linux-gnueabihf-objdump -d` disassembles it correctly because the ELF header marks it as ARM EABI5, and the linker placed Thumb code in the `.text` section with the correct flags. objdump automatically detects Thumb instructions based on the address (odd addresses = Thumb state).

### Disassemble `networking()` Around the Patch Points

```bash
arm-linux-gnueabihf-objdump -d --start-address=0x3c15f8 \
  --stop-address=0x3c1624 \
  project/lib/armeabi/libcocos2dcpp.so
```

This shows the first ~30 bytes of `networking()` in disassembly. Each line is:
- **Address**: File offset + section base (the address shown includes the section base)
- **Bytes**: Raw hex bytes in MEMORY order (low byte first for Thumb)
- **Instruction**: Disassembled ARM/Thumb instruction

### Key Instructions to Understand

#### `CMP Rn, #imm` — Compare register with immediate
```asm
2802    cmp r0, #2      @ Compare r0 with value 2
```
Sets condition flags based on `r0 - 2`. Used for branch conditions.

#### `BEQ.n` / `BNE.n` — Branch if Equal / Branch if Not Equal (near)
```asm
d001    beq.n 3c160e    @ Branch if EQUAL to previous CMP result
d101    bne.n 3c1602    @ Branch if NOT EQUAL
```
The `.n` means "near" — the branch target is within ±128 bytes. These are 2-byte Thumb instructions.

#### `LDR r0, [pc, #imm]` — Load word from PC-relative address
```asm
48a3    ldr r0, [pc, #652]   @ Load value at pc+652 into r0
```
The PC points to the CURRENT instruction + 4 bytes (pipeline offset). So the actual address is `current_pc + 4 + imm`. This is how Thumb loads 32-bit constants from `.rodata` or global variables.

#### `BL <address>` — Branch with Link (call function)
```asm
f014 fb7d   bl 3d5d00    @ Call GameNet::getGameNetState()
```
Two 16-bit Thumb words combined into a 32-bit BL instruction. Saves return address in LR register.

#### `MOV Rn, #imm` / `MOVS Rn, #imm` — Move immediate to register
```asm
2002    movs r0, #2      @ Set r0 = 2 (return value)
20ff    movs r0, #255    @ Set r0 = -1 (as unsigned 0xff)
```

#### `BX LR` — Branch to Link Register (return from function)
```asm
4770    bx lr            @ Return to caller
```

### Disassemble Patch Target Functions

**`getGameNetState()` and `getNetworkStatus()`:**
```bash
arm-linux-gnueabihf-objdump -d --start-address=0x3d5cf8 \
  --stop-address=0x3d5d10 \
  project/lib/armeabi/libcocos2dcpp.so
```

**`getResult()`:**
```bash
arm-linux-gnueabihf-objdump -d --start-address=0x3d5e90 \
  --stop-address=0x3d5ea8 \
  project/lib/armeabi/libcocos2dcpp.so
```

## Step 6: The Four Patches — Detailed Explanation

### PATCH A: `networking()` — Change beq.n to bne.n

**Purpose:** When `getGameNetState()` returns 2 (CONNECTING), the original code uses `beq.n` to call `openConnectingServer()`. We change it to `bne.n` so that when state == 2, we SKIP the `openConnectingServer()` call and fall through directly to the network status check.

**File offset:** `0x3c1608–0x3c1609` (2 bytes)

**Before:**
```asm
3c1606: 2802       cmp r0, #2        @ Compare result of getGameNetState() with 2
3c1608: d001       beq.n 3c160e      @ If EQUAL (state == 2), branch to 3c160e
3c160a: f000 ff54    bl 3c24b6         @ If NOT equal, call openConnectingServer()
```

**Hex bytes before:** `[0xd0, 0x01]` → Thumb word `0xd001` = `beq.n`

**After:**
```asm
3c1606: 2802       cmp r0, #2        @ Compare result of getGameNetState() with 2
3c1608: d101       bne.n 3c160e      @ If NOT EQUAL (state != 2), branch to 3c160e
3c160a: f000 ff54    bl 3c24b6         @ If EQUAL, call openConnectingServer()
```

**Hex bytes after:** `[0xd1, 0x01]` → Thumb word `0xd101` = `bne.n`

**What changed:** Bit 8 of the Thumb word changed from `0` to `1`:
- `0xd0` = `1101 0000` — condition field `0000` = EQ (Equal)
- `0xd1` = `1101 0001` — condition field `0001` = NE (Not Equal)

**Correct encoding:** `[0x01, 0xd1]` — The first byte is the LOW byte of the Thumb word `0xd101`. This is because Thumb instructions are 16-bit and stored in little-endian format within the binary.

**Effect:** When `getGameNetState()` returns 2 (which it will after Patch B), this branch SKIPS `openConnectingServer()` and falls through to the network status check at `0x3c160e`. This is the first step toward bypassing the error popup.

---

### PATCH B: `getGameNetState()` — Always Return 2 (CONNECTING)

**Purpose:** Replace the original function body with `movs r0, #2; bx lr` to always return state 2 (CONNECTING), regardless of the actual network state.

**File offset:** `0x3d5d00–0x3d5d03` (4 bytes)

**Before:**
```asm
3d5d00: 6800       ldr r0, [r0, #0]    @ Load state from memory address in r0
3d5d02: 4770       bx lr               @ Return
```

**Hex bytes before:** `[0x68, 0x00, 0x47, 0x70]`

The original function loads the state from a memory address (passed in r0 and returns it. This is why it returns -5 (DISCONNECTED) when the server is dead — that's the actual state stored in memory.

**After:**
```asm
3d5d00: 2002       movs r0, #2         @ Set r0 = 2 (CONNECTING state)
3d5d02: 4770       bx lr               @ Return to caller
```

**Hex bytes after:** `[0x02, 0x20, 0x70, 0x47]`

**Byte-by-byte breakdown:**
- `movs r0, #2` = Thumb encoding `0x2002` → stored as `[0x02, 0x20]` (LOW byte first)
- `bx lr` = Thumb encoding `0x4770` → stored as `[0x70, 0x47]`) (LOW byte first)

**CRITICAL:** Each pair of bytes is REVERSED from the instruction encoding because Thumb instructions are stored in little-endian format. The Thumb word `0x2002` becomes memory bytes `[0x02, 0x20]`, NOT `[0x20, 0x02]`.

**Effect:** `networking()` always sees state == 2 (CONNECTING). Combined with Patch A (which now uses `bne.n`), when state is 2, the branch SKIPS `openConnectingServer()` and falls through to the network status check.

---

### PATCH C: `getNetworkStatus()` — Always Return -1 (0xff)

**Purpose:** Replace the original function body with `movs r0, #0xff; bx lr` to return -1 (0xff as unsigned). This value passes ALL THREE conditions in the calling code's if-else chain.

**File offset:** `0x3d5d04–0x3d5d07` (4 bytes)

**Before (original):**
```asm
3d5d04: [original function body — returns -5 when disconnected]
```

The original function reads the actual network status from memory. When the server is dead, it returns -5 (DISCONNECTED).

**After:**
```asm
3d5d04: 20ff       movs r0, #255       @ Set r0 = 255 (0xff = -1 as signed)
3d5d06: 4770       bx lr               @ Return to caller
```

**Hex bytes after:** `[0xff, 0x20, 0x70, 0x47]`

**Byte-by-byte breakdown:**
- `movs r0, #255` = Thumb encoding `0x20ff` → stored as `[0xff, 0x20]` (LOW byte first)
- `bx lr` = Thumb encoding `0x4770` → stored as `[0x70, 0x47]` (LOW byte first)

---

### PATCH D: `getResult()` — Always Return 1 (SUCCESS)

**Purpose:** Replace the original function body with `movs r0, #1; bx lr; nop` to always return 1 (SUCCESS), tricking the game into thinking the connection succeeded.

**File offset:** `0x3d5e98–0x3d5e9d` (6 bytes)

**Before:**
```asm
3d5e98: 4b01       ldr r3, [pc, #4]    @ Load pointer from next address
3d5e9a: c056       ldrsb r0, [r0, r3]  @ Load signed byte from that address
3d5e9c: 4770       bx lr               @ Return (with whatever was in r0)
```

**Hex bytes before:** `[0x4b, 0x01, 0xc0, 0x56, 0x70, 0x47]`

The original function loads a result code from memory and returns it. This is where the actual connection result (success/failure) would be stored after the TCP connection completes.

**After:**
```asm
3d5e98: 2001       movs r0, #1         @ Set r0 = 1 (SUCCESS)
3d5e9a: 4770       bx lr               @ Return to caller
3d5e9c: 46c0       nop                 @ No-op (fill remaining space)
```

**Hex bytes after:** `[0x01, 0x20, 0x70, 0x47, 0xc0, 0x46]`

**Byte-by-byte breakdown:**
- `movs r0, #1` = Thumb encoding `0x2001` → stored as `[0x01, 0x20]` (LOW byte first)
- `bx lr` = Thumb encoding `0x4770` → stored as `[0x70, 0x47]` (LOW byte first)
- `nop` = Thumb encoding `0x46c0` → stored as `[0xc0, 0x46]` (NOOP filler)

**Effect:** `getResult()` always returns 1 (SUCCESS). When the code reaches this function (after we fix the `getPacketType()` return issue), it will think the connection succeeded and proceed to the success path: sync server time, load progress, dispatch "connect" event → MAIN MENU.

---

## Step 7: Apply the Patches

### Method: Python Script to Write Raw Bytes

Save this as `apply_patches.py` (or run inline):

```python
#!/usr/bin/env python3
"""Apply all four hex patches to Darkness Survival binary."""

BINARY = '~/GIT/darkness-survival-revival/project/lib/armeabi/libcocos2dcpp.so'

# Read the original binary
with open(BINARY, 'rb') as f:
    data = bytearray(f.read())

print(f"Loaded {len(data)} bytes from {BINARY}")

# PATCH A: networking() — Change beq.n to bne.n at 0x3c1608-0x3c1609
# Thumb word 0xd101 (bne.n) stored as [0x01, 0xd1]
print("\nPATCH A: networking() — Change beq.n to bne.n")
print(f"  Offset: {hex(0x3c1608)}-{hex(0x3c1609)}")
print(f"  Before: [{hex(data[0x3c1608])}, {hex(data[0x3c1609])}]")
data[0x3c1608] = 0x01  # LOW byte of 0xd101
data[0x3c1609] = 0xd1  # HIGH byte of 0xd101
print(f"  After:  [{hex(data[0x3c1608])}, {hex(data[0x3c1609])}]")

# PATCH B: getGameNetState() — Always return 2 at 0x3d5d00-0x3d5d03
# movs r0, #2 / bx lr = [0x02, 0x20, 0x70, 0x47]
print("\nPATCH B: getGameNetState() — Always return 2")
print(f"  Offset: {hex(0x3d5d00)}-{hex(0x3d5d03)}")
print(f"  Before: [{hex(data[0x3d5d00])}, {hex(data[0x3d5d01])}, {hex(data[0x3d5d02])}, {hex(data[0x3d5d03])}]")
data[0x3d5d00] = 0x02  # LOW byte of 0x2002 (movs r0, #2)
data[0x3d5d01] = 0x20  # HIGH byte of 0x2002
data[0x3d5d02] = 0x70  # LOW byte of 0x4770 (bx lr)
data[0x3d5d03] = 0x47  # HIGH byte of 0x4770
print(f"  After:  [{hex(data[0x3d5d00])}, {hex(data[0x3d5d01])}, {hex(data[0x3d5d02])}, {hex(data[0x3d5d03])}]")

# PATCH C: getNetworkStatus() — Always return -1 (0xff) at 0x3d5d04-0x3d5d07
# movs r0, #0xff / bx lr = [0xff, 0x20, 0x70, 0x47]
print("\nPATCH C: getNetworkStatus() — Always return -1 (0xff)")
print(f"  Offset: {hex(0x3d5d04)}-{hex(0x3d5d07]}")
print(f"  Before: [{hex(data[0x3d5d04])}, {hex(data[0x3d5d05])}, {hex(data[0x3d5d06])}, {hex(data[0x3d5d07]]}")
data[0x3d5d04] = 0xff  # LOW byte of 0x20ff (movs r0, #255)
data[0x3d5d05] = 0x20  # HIGH byte of 0x20ff
data[0x3d5d06] = 0x70  # LOW byte of 0x4770 (bx lr)
data[0x3d5d07] = 0x47  # HIGH byte of 0x4770
print(f"  After:  [{hex(data[0x3d5d04])}, {hex(data[0x3d5d05])}, {hex(data[0x3d5d06])}, {hex(data[0x3d5d07]]}")

# PATCH D: getResult() — Always return 1 (SUCCESS) at 0x3d5e98-0x3d5e9d
# movs r0, #1 / bx lr / nop = [0x01, 0x20, 0x70, 0x47, 0xc0, 0x46]
print("\nPATCH D: getResult() — Always return 1 (SUCCESS)")
print(f"  Offset: {hex(0x3d5e98)}-{hex(0x3d5e9d)}")
print(f"  Before: [{hex(data[0x3d5e98])}, {hex(data[0x3d5e99])}, {hex(data[0x3d5e9a])}, {hex(data[0x3d5e9b])}, {hex(data[0x3d5e9c])}, {hex(data[0x3d5e9d])}]")
data[0x3d5e98] = 0x01  # LOW byte of 0x2001 (movs r0, #1)
data[0x3d5e99] = 0x20  # HIGH byte of 0x2001
data[0x3d5e9a] = 0x70  # LOW byte of 0x4770 (bx lr)
data[0x3d5e9b] = 0x47  # HIGH byte of 0x4770
data[0x3d5e9c] = 0xc0  # LOW byte of 0x46c0 (nop)
data[0x3d5e9d] = 0x46  # HIGH byte of 0x46c0
print(f"  After:  [{hex(data[0x3d5e98])}, {hex(data[0x3d5e99])}, {hex(data[0x3d5e9a])}, {hex(data[0x3d5e9b])}, {hex(data[0x3d5e9c])}, {hex(data[0x3d5e9d])}]")

# Write patched binary
with open(BINARY, 'wb') as f:
    f.write(data)

print(f"\nWrote {len(data)} bytes to {BINARY}")
print("All patches applied successfully.")
```

### Run It

```bash
python3 apply_patches.py
```

---

## Step 8: Verify Patches with objdump

After applying patches, verify each one by disassembling the affected regions:

### Verify Patch A (networking)

```bash
arm-linux-gnueabihf-objdump -d --start-address=0x3c15f8 \
  --stop-address=0x3c1624 \
  project/lib/armeabi/libcocos2dcpp.so
```

**Expected output (key lines):**
```asm
3c1606: 2802       cmp r0, #2
3c1608: d101       bne.n 3c160e      @ ← Changed from d001 (beq.n to d101 (bne.n)
3c160a: f000 ff54    bl 3c24b6
```

### Verify Patch B (getGameNetState)

```bash
arm-linux-gnueabihf-objdump -d --start-address=0x3d5cf8 \
  --stop-address=0x3d5d10 \
  project/lib/armeabi/libcocos2dcpp.so
```

**Expected output (key lines):**
```asm
3d5d00: 2002       movs r0, #2        @ ← Changed from 6800 (ldr r0,[r0,#0])
3d5d02: 4770       bx lr              @ ← Return immediately with value 2
```

### Verify Patch C (getNetworkStatus)

Same command as above — verify the next function:

**Expected output (key lines):**
```asm
3d5d04: 20ff       movs r0, #255      @ ← Changed to return 0xff (-1)
3d5d06: 4770       bx lr              @ ← Return immediately
```

### Verify Patch D (getResult)

```bash
arm-linux-gnueabihf-objdump -d --start-address=0x3d5e90 \
  --stop-address=0x3d5ea8 \
  project/lib/armeabi/libcocos2dcpp.so
```

**Expected output (key lines):**
```asm
3d5e98: 2001       movs r0, #1        @ ← Changed from 4b01 c056 to always return 1
3d5e9a: 4770       bx lr              @ ← Return immediately
3d5e9c: 46c0       nop                @ ← No-op filler
```

---

## Step 9: Compile and Install on Device

### The APK Build Pipeline

After patching the binary, you need to use the (3-re-apply.sh) script

This will:
1. Rebuild the APK (takes ~30 seconds)
2. Sign it with the debug keystore
3. Uninstall the old version from your device
4. Install the new APK
5. Launch the app
6. Clear logcat and start capturing logs, showing a crashlog if the changes corrupted the binary

---

## Step 10: Expected Behavior After All Patches

### The New Flow

```
1. App starts up
2. Timer fires every ~3 seconds → networking() called
3. getGameNetState() returns 2 (forced by Patch B)
4. bne.n at 0x3c1608: state==2, so CONDITION IS FALSE → SKIP openConnectingServer(), fall through to status check
5. getNetworkStatus() returns -1/0xff (Patch C): 
   - Condition "status != -5" → TRUE (enter block)
   - Condition "status < -5" → FALSE (skip connectGameServer)
   - Condition "-3 < status" → TRUE (call openConnectingServer)
6. openConnectingServer() shows loading screen, then falls through
7. getPacketType() → switch/jumptable → RETURN from function ⚠️
8. getResult() at end of function — Patch D never takes effect (THE REMAINING PROBLEM)
```

### What You See on Device

1. The app boots up
2. "Connecting to the Server" loading screen appears
3. After ~3 seconds, the error popup shows: **"Failed to connect to server. Try again later."**
4. Tap "Retry or close the popup
5. Loading screen appears again
6. `getPacketType()` returns before reaching `getResult()` — **the function exits early**
7. The app is stuck on the loading screen, never reaching the main menu

### Why Patch D Never Executes

After the error popup + disconnect sequence, the code calls `getPacketType()` which contains a switch/jumptable that **returns from the function**. The `getResult()` call at line ~107 in the decompilation is AFTER this return, so it never executes.

The fix options are:
- **Option A:** Patch `getPacketType()` to return a value that falls through to the success path
- **Option B:** Insert a branch from after `getPacketType()` to the success path
- **Option C:** Patch `openConnectingServer()` to fall through instead of returning

---

## Troubleshooting

### Problem: App crashes on startup with segfault at 0x3d5d02

**Cause:** Wrong byte ordering in Patch B. The bytes were written as `[0x20, 0x02]` instead of `[0x02, 0x20]`.

**Fix:** Remember: each pair of bytes in a Thumb word is REVERSED. For `movs r0, #2` (encoding `0x2002`), write `[0x02, 0x20]` (LOW byte first).

### Problem: App shows connecting screen but no error popup

**Cause:** Patch A condition is wrong — the branch skips to the wrong place.

**Fix:** Verify with objdump that `d101` appears at offset 0x3c1608-0x3c1609. The `bne.n` should branch to 0x3c160e (the status check), not skip past it.

### Problem: App crashes after showing error popup

**Cause:** `getPacketType()` returns a value that hits an invalid jumptable entry.

**Fix:** Need to also patch `getPacketType()` or insert a branch to skip it entirely.

### Verifying Byte Ordering Rule

Every Thumb instruction is 2 bytes. When the instruction encoding is `0xABCD`:
- Memory byte at offset N: `0xCD` (LOW byte)
- Memory byte at offset N+1: `0xAB` (HIGH byte)

Examples from our patches:
| Instruction | Encoding | Memory bytes (offset, offset+1) |
|-------------|----------|--------------------------------|
| `movs r0, #2` | `0x2002` | `[0x02, 0x20]` |
| `movs r0, #255` | `0x20ff` | `[0xff, 0x20]` |
| `movs r0, #1` | `0x2001` | `[0x01, 0x20]` |
| `bx lr` | `0x4770` | `[0x70, 0x47]` |
| `bne.n` (was `beq.n`) | `0xd101` | `[0x01, 0xd1]` |

### Checking the Binary After Patching

```bash
# Check file size hasn't changed
ls -la project/lib/armeabi/libcocos2dcpp.so

# Verify MD5 changed (patches were applied)
md5sum project/lib/armeabi/libcocos2dcpp.so

# Compare with original
md5sum project/lib/armeabi/libcocos2dcpp.so.bak
```

The patched binary should have a different MD5 than the original. If they match, the patches weren't applied correctly.

## Summary of All Patches

| Patch | Function | File Offset | Before (hex) | After (hex) | Effect |
|-------|----------|-------------|--------------|-------------|--------|
| **A** | `networking()` | `0x3c1608-0x3c1609` | `d0 01` | `01 d1` | Change `beq.n` to `bne.n` — skip openConnectingServer when state==2 |
| **B** | `getGameNetState()` | `0x3d5d00-0x3d5d03` | `68 00 47 70` | `02 20 70 47` | Always return 2 (CONNECTING) instead of reading from memory |
| **C** | `getNetworkStatus()` | `0x3d5d04-0x3d5d07` | *(original body)* | `ff 20 70 47` | Always return -1 (0xff), passes all status check conditions |
| **D** | `getResult()` | `0x3d5e98-0x3d5e9d` | `4b 01 c0 56 70 47` | `01 20 70 47 c0 46` | Always return 1 (SUCCESS) instead of reading from memory |

### How Each Patch Works Together

```
Patch B forces getGameNetState() → returns 2
    ↓
Patch A changes branch condition so state==2 SKIPS openConnectingServer()
    ↓
Patch C makes getNetworkStatus() return -1, which:
    - Enters the status check block (status != -5)
    - Skips connectGameServer() (status is NOT < -5)
    - Calls openConnectingServer() (-3 < status)
    - Falls through to getPacketType() → RETURN
    ↓
Patch D makes getResult() return 1, but it never executes because
    getPacketType() returns first (REMAINING PROBLEM)
```

## All File Offsets Reference

| Symbol | File Offset | Description |
|--------|-------------|-------------|
| `UILayer::networking` | `0x3d15e4` | Main connection loop — PATCHED (Patch A at 0x3c1608) |
| `GameNet::getGameNetState` | `0x3d5d00` | Returns state — PATCHED (Patch B, always returns 2) |
| `GameNet::getNetworkStatus` | `0x3d5d04` | Returns status — PATCHED (Patch C, always returns -1/0xff) |
| `GameNet::connectGameServer` | `0x3e5e04` | Attempts TCP connection |
| `GameNet::disconnect` | `0x3e5e68` | Sets state to DISCONNECTED |
| `GameNet::getResult` | `0x3d5e98` | Returns result code — PATCHED (Patch D, always returns 1) |
| `GameNet::getPacketType` | `0x3d5e94` | Returns packet type — Jumptable, RETURNS early |
| `TextDataManager::getText(int)` | `0x3bb428` | i18n string lookup |
| `UIMessageBox::create` | `0x3d74b8` | Message box popup |
| `PopupManager::openPopup` | `0x3b1940` | Display popup on screen |
| `UILayer::openConnectingServer` | `0x3d0418` | Shows loading screen |
| `UILayer::closeConnectingServer` | `0x3d04a0` | Hides loading screen |

---

## All String IDs Found in networking()

| ID | Text | Where Used in networking() |
|----|------|---------------------------|
| **2222** | "Connecting to the Server" | Loading screen title (openConnectingServer) |
| **2223** | "Failed to connect to server. Try again later." | Error message box |
| **2696** | "New version has been released. Please update game and play again." | Secondary error popup |
| **2700** | "Sorry, we're having a problem connecting to our server..." | Alternative connection error |

Event names (from .rodata):
- `"__connection_fail"` at `.rodata` offset `0x797c03` — dispatched on connection failure
- `"___ongcli___`" at `.rodata `offset 0x7968b1` — internal event (unknown purpose)

## Quick Reference Card

### Memory byte ordering reminder

For each 16-bit Thumb word `0xABCD`:
- **Instruction encoding:** `AB CD` (HIGH byte first, as you'd write in assembly)
- **Memory bytes:** `[CD, AB]` (LOW byte first, as stored in the file)

Every patch pair: first byte = LOW, second byte = HIGH.
