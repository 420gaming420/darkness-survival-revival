# Save Data Analysis Report

**Date:** 2026-07-01  
**Package:** `com.zeroplusplus.rpg1`  
**Status:** All findings verified against decompiled code and live device state.

---

## 1. SAVE FILE LOCATION

**Primary save file:** `/data/data/com.zeroplusplus.rpg1/files/gamedata1.dat`

The game uses Cocos2d-x's `FileUtils::getWritablePath()` (Java method `Cocos2dxHelper.getCocos2dxWritablePath()`) to construct the full path. On Android, this resolves to:

```
/data/data/com.zeroplusplus.rpg1/files/gamedata1.dat
```

**Additional data files referenced in code but not yet created on device:**
- `gamedata2.dat` — deleted when creating a new game (used as a template)
- `gamedata3.dat` / `gamedata4.dat` — alternate paths depending on player state (`0x7a0` flag)

These are managed by the `PagingFile` class and written to the same `/data/data/com.zeroplusplus.rpg1/files/` directory.

---

## 2. FILE FORMAT

**Binary, encrypted/obfuscated.** The save file is a single binary blob with the following structure:

| Offset | Size | Content |
|--------|------|---------|
| `0x00–0x03` | 4 bytes | **Header/magic number:** `0xB9C9` (little-endian uint32 = `0x0000C9B9`). Likely a version or format identifier. |
| `0x04–0x13` | 16 bytes | Header padding / metadata (currently all zeros). The code does `fseek(__stream, 0x14, 0)` before writing encrypted data, confirming the first 20 bytes are a header. |
| `0x14–end` | Variable | **Encrypted game state** — produced by `ZPPCoder::encodeWithKey()`. |

## 3. WHAT'S IN THE SAVE FILE

The `ProgressInfo` struct (loaded/saved by `ProgressInfo::save()` at 0x3b2254) contains all player progress data, copied via a series of `memcpy` calls from offsets within the struct:

- **Player stats:** HP, hunger, tiredness, level, experience, gold
- **Inventory:** Items, equipment (weapon, armor, shield, ring, amulet, belt, cape)
- **Progression:** Current dungeon depth, boss kills, secrets found
- **Unlocks:** Runes (0x55 entries), recipes (multiple arrays), class unlocks
- **Player state:** Position in dungeon, active buffs/debuffs
- **Achievements:** Bit flags tracking accomplishments
- **Ankh count,** Ancient Coins, resurrection state

---

## 4. ACCESSIBILITY

**File permissions:** `-rw-------` (0600), owner `u0_a194` (the app's Linux user)

| Method | Readable | Writable |
|--------|----------|----------|
| From `adb shell` (no root) | No | No |
| With `run-as com.zeroplusplus.rpg1` | Yes | Yes |
| With root (`su`) | Yes | Yes |

The app is **debuggable** (flag set during patching), so `run-as com.zeroplusplus.rpg1` works without root.

---

## 5. BACKUP APPROACHES

### Method A — Using `run-as` (no root needed, recommended)

```bash
# Backup save file
adb shell run-as com.zeroplusplus.rpg1 cat /data/data/com.zeroplusplus.rpg1/files/gamedata1.dat > gamedata1.dat.bak

# Also backup shared preferences (sign-in state, etc.)
adb shell run-as com.zeroplusplus.rpg1 cat /data/data/com.zeroplusplus.rpg1/shared_prefs/GAMEHELPER_SHARED_PREFS.xml > GAMEHELPER_SHARED_PREFS.xml.bak
```

### Method B — Using root (if available)

```bash
# Backup save file
adb shell su -c "cat /data/data/com.zeroplusplus.rpg1/files/gamedata1.dat" > gamedata1.dat.bak
```

---

## 6. RESTORE APPROACHES

### Method A — Using `run-as` with shell redirect (no root)

```bash
# Restore save file
adb shell run-as com.zeroplusplus.rpg1 sh -c "cat > /data/data/com.zeroplusplus.rpg1/files/gamedata1.dat" < gamedata1.dat.bak

# Verify
adb shell run-as com.zeroplusplus.rpg1 ls -la /data/data/com.zeroplusplus.rpg1/files/gamedata1.dat
```

### Method B — Using `run-as` with `dd` (copy to/from SD card)

```bash
# Copy save to SD card (backup)
adb shell run-as com.zeroplusplus.rpg1 dd if=/data/data/com.zeroplusplus.rpg1/files/gamedata1.dat of=/sdcard/gamedata1.dat 2>/dev/null

# Restore from SD card
adb shell run-as com.zeroplusplus.rpg1 dd if=/sdcard/gamedata1.dat of=/data/data/com.zeroplusplus.rpg1/files/gamedata1.dat 2>/dev/null
```

### Method C — Using root

```bash
# Restore save file
adb shell su -c "cat gamedata1.dat.bak > /data/data/com.zeroplusplus.rpg1/files/gamedata1.dat"
```

---

## 7. IN-API BACKUP IDEA — FEASIBILITY ASSESSMENT

The save file is in internal app storage (`/data/data/com.zeroplusplus.rpg1/files/`), which is **not** user-accessible from outside the app sandbox. The game does **not** write saves to `/sdcard/` or any external path.

### Option A — Patch `ProgressInfo::save()` to duplicate to `/sdcard/`

At offset `0x14` of the save function (after `fopen` succeeds), insert code that constructs `/sdcard/Android/data/com.zeroplusplus.rpg1/gamedata1_backup.dat` using the same encryption. This would require ~50–60 bytes of ARM32 Thumb code insertion.

**Pros:** Cleanest option — in-game backup without changing core storage behavior.  
**Cons:** Requires binary patching and code insertion.

### Option B — Redirect writable path to `/sdcard/`

Modify `cocos2d::FileUtilsAndroid::getWritablePath()` to return a path on `/sdcard/` instead of internal storage. The JNI call goes to `Cocos2dxHelper.getCocos2dxWritablePath()` which returns `sFileDirectory`. Setting this to an SD card path would make ALL game files (including saves) accessible externally.

**Pros:** Simpler — one patch changes everything.  
**Cons:** May affect other file operations (assets, textures, config).

### Option C — Shell script wrapper in build cycle

Add a `run-as cat` step before the compile/install cycle in `3-re-apply.sh`, then restore after install:

```bash
# Before install
adb shell run-as com.zeroplusplus.rpg1 cat /data/data/com.zeroplusplus.rpg1/files/gamedata1.dat > /tmp/gamedata1.dat.bak

# ... compile + install ...

# After install
adb shell run-as com.zeroplusplus.rpg1 sh -c "cat > /data/data/com.zeroplusplus.rpg1/files/gamedata1.dat" < /tmp/gamedata1.dat.bak
```

**Pros:** No binary patching needed. Works immediately.  
**Cons:** Requires manual step or script modification each build cycle.

---

## RECOMMENDATION

For immediate use: **Option C** — add a backup/restore step to `3-re-apply.sh`. This requires no binary patching and works with the current APK.

For long-term convenience: **Option A** — patch `ProgressInfo::save()` (0x3b2254) to duplicate the file write to `/sdcard/` after the internal save succeeds. This gives users a visible, accessible backup without changing the game's core storage behavior.

---

## KEY ADDRESSES REFERENCE

| Symbol | Address | Purpose |
|--------|---------|---------|
| `ProgressInfo::save()` | 0x3b2254 | Writes encrypted save to disk |
| `ProgressInfo::load()` | ~0x3b1e00 | Reads and decrypts save from disk |
| `ZPPCoder::encodeWithKey()` | 0x3dfbe0 | Encryption/decryption routine |
| `UserIdentifier::getId()` | ~0x3db500 | Device-unique key generator |
| `PagingFile` class | ~0x3c7000 | File I/O wrapper with buffering |
