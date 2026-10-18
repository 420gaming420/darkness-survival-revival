### Note
This research and summary is pure speculation, some things may be wrong or contain made up AI hallucinations.

# textdata_en.dat — Reverse Engineering Reference

## Overview

`textdata_en.dat` is the English text data file extracted from the Android APK of *Darkness Survival*. It is a binary file containing **2978 null-terminated strings** organized behind a **Relative Offset Pointer Table (LUT)** with a sentinel entry.

**File size:** 98,131 bytes (95.8 KB)  
**Architecture:** ARM:LE:32:v5 (Android APK extraction)  
**Encoding:** UTF-8 / ASCII, null-terminated strings

---

## File Layout

```
OFFSET       SIZE     FIELD
0x0000       4        Header (uint32 LE)
0x0004       11912    String Pointers (2978 entries x 4 bytes each)
0x2E8C       4        Sentinel (uint32 LE)
0x2E90       86211    String data region (null-terminated UTF-8/ASCII)
```

### Header (offset 0x0000, 4 bytes)

A single `uint32` in little-endian format. Its value is `0x00002E88` (11,912). This is the **byte size of the string pointer section only** (2978 entries × 4 bytes = 11,912). It does **not** include the sentinel entry.

```
STRING_REGION_START = header_value + 8 = 0x2E88 + 8 = 0x2E90
```

### String Pointers (offset 0x0004–0x0004+11911 = 0x2E8B)

Contains **2978 entries**, each a `uint32` in little-endian format. Each entry stores an **offset relative to the string region start** (0x2E90).

```
absolute_string_address = 0x2E90 + pointer_value
```

Each resolved address points to a null-terminated string.

**Example:**

| LUT file offset | Pointer value (LE) | Absolute address | String |
|-----------------|-------------------|------------------|--------|
| 0x0004 | `00 00 00 00` | 0x2E90 + 0x00000000 = 0x2E90 | `Accuracy :<CF3F300FF> High<CFFFFFFFF>` |
| 0x0FA0 | `9F 6B 00 00` | 0x2E90 + 0x00006B9F = 0x9A2F | `It's very hard substance, but easy to process, so commonly used to manufacture weapons.` |
| 0x1F40 | `2C DE 00 00` | 0x2E90 + 0x0000DE2C = 0x10CBC | `Weight Stone` |
| 0x2E88 | `B4 50 01 00` | 0x2E90 + 0x000150B4 = 0x17F44 | `Privacy Policy` |

### Sentinel (offset 0x2E8C–0x2E8F, 4 bytes)

A single `uint32` in little-endian format. Its value is the **end offset of the last string** (i.e., `last_string_addr + last_string_len + 1` for the null terminator), expressed as a stripped offset from the string region base (0x2E90).

```
sentinel_value = (last_string_addr + last_string_len + 1) - 0x2E90
```

In the original file, the sentinel value is `0x000150C3` (86,211), which resolves to absolute address `0x17F53` — one byte past the null terminator of "Privacy Policy" at `0x17F44` (14 chars + 1 null = 15 bytes, ending at `0x17F53`).

### String Data Region (offset 0x2E90–0x17F52)

All strings are stored sequentially in a single contiguous block starting at file offset `0x2E90`. Each string is:

- **Null-terminated** (`\x00`)
- **UTF-8 / ASCII** encoded
- **No embedded nulls** — each `\x00` marks the end of exactly one string
- Strings are laid out back-to-back with no padding or alignment gaps

---

## Validation Checksums

The following 4 entries are known-good anchors used to verify parser correctness:

| LUT Address | String Address | Expected Content |
|-------------|----------------|-----------------|
| `0x00000004` | `0x00002E90` | `Accuracy :<CF3F300FF> High<CFFFFFFFF>` |
| `0x00000FA0` | `0x00009A2F` | `It's very hard substance, but easy to process, so commonly used to manufacture weapons.` |
| `0x00001F40` | `0x00010CBC` | `Weight Stone` |
| `0x00002E88` | `0x00017F44` | `Privacy Policy` |

---

## Tools

### `hexview` — Binary Hexdump Viewer

A lightweight hexdump utility for inspecting the `.dat` file at arbitrary offsets. Displays 4-byte (uint32 LE) values per line with hex and ASCII columns.

**Usage:**
```bash
./hexview textdata_en.dat                  # First 10 lines
./hexview textdata_en.dat --offset 2E90    # Skip LUT, view string region
./hexview textdata_en.dat --offset 2E90 --lines 50  # 50 lines from string region
./hexview textdata_en.dat --offset 0x1F40 --lines 5   # View LUT entry at 0x1F40
```

**Arguments:**
- `FILE` — Path to the `.dat` file
- `--offset HEX` — Starting offset (accepts hex `0x2E88`, `2E88`, or segment `0000:2E88` format)
- `--skip HEX` — Additional bytes to skip from the offset
- `--lines, -n INT` — Number of 4-byte lines to display (default: 10)

---

### `textdata_parser.py` — String Extraction Script

Parses the `.dat` file and extracts all 2978 strings into two output formats:

1. **Markdown table** (`textdata_en_parsed.md`) — human-readable hexdump with hex, ASCII, and byte count per string
2. **JSON** (`textdata_en_parsed.json`) — structured data with all metadata for programmatic processing

**Usage:**
```bash
python3 textdata_parser.py [INPUT_FILE]
```

- `INPUT_FILE` — Path to the `.dat` file (default: `textdata_en.dat`)
- Outputs: `<input>_parsed.md` and `<input>_parsed.json`

**JSON Structure:**
```json
{
  "_header": "textdata_en.dat parsed strings",
  "_count": 2978,
  "strings": [
    {
      "index_addr": "00000004",
      "string_addr": "00002e90",
      "stripped_offset": "00000000",
      "hex_data": "4163637572616379203a3c4346334633303046463e...",
      "ascii_data": "Accuracy :<CF3F300FF> High<CFFFFFFFF>",
      "byte_count": 37
    }
  ]
}
```

**Fields per string entry:**
- `index_addr` — File offset of the LUT entry (hex)
- `string_addr` — Absolute file offset of the string (hex)
- `stripped_offset` — Offset from string region start (hex)
- `hex_data` — Hex representation of string bytes (without null terminator)
- `ascii_data` — Decoded string content
- `byte_count` — Length in bytes (without null terminator)

---

### `view_textdata.py` — PyQt6 GUI Viewer

A graphical viewer for `textdata_en_parsed.json` with search, sorting, and copy functionality.

**Usage:**
```bash
python3 view_textdata.py [JSON_FILE]
```

- `JSON_FILE` — Path to the parsed JSON file (default: `textdata_en_parsed.json`)

**Features:**
- **Search/filter** — Type in the search bar to filter rows by any column (regex-supported)
- **Right-click copy** — Right-click any cell to copy its content to clipboard
- **Column headers** — INDEX_ADDR, STRING_ADDR, STRIPPED, HEX, ASCII, BYTES
- **Alternating row colors** for readability
- **Monospace font** for consistent alignment

---

### `textdata_generate.py` — Binary Reconstruction Script

Reconstructs a `.dat` file from a parsed JSON file. Works with both unmodified and modified strings, producing byte-for-byte identical or customized output.

**Usage:**
```bash
python3 textdata_generate.py --input textdata_en_parsed.json --output textdata_en_copy.dat
python3 textdata_generate.py --input modified.json --output modified.dat
python3 textdata_generate.py --input textdata_en_parsed.json --output textdata_en_copy.dat --compare textdata_en.dat
```

**Arguments:**
- `--input` — Input JSON file (required)
- `--output` — Output `.dat` file (required)
- `--compare` — Original `.dat` file for verification (optional)

**How it works:**
1. Reads each string's `ascii_data`, encodes to UTF-8, and appends a null terminator (`\x00`)
2. Places each string at its `string_addr` offset within the string data region
3. Builds the pointer table from each entry's `stripped_offset` (string_addr - 0x2E90)
4. Appends a sentinel entry: `(last_string_addr + byte_count + 1) - 0x2E90`
5. Writes the header: `num_strings * 4` (pointer section size, excluding sentinel)
6. Concatenates: `header + pointers + sentinel + string_region`

**Verification:** When `--compare` is provided, the script compares the output against the original using byte-by-byte comparison and MD5 hash. A successful run produces:
```
[+] Byte-for-byte identical to original
  Original MD5: 35c59fea429754b31b18b03969215455
  New MD5:      35c59fea429754b31b18b03969215455
  [OK] MD5 match: True
```

---

## Parsing Algorithm

```
1. Read file header (4 bytes) → header_value
2. STRING_REGION = header_value + 8
3. num_pointers = header_value / 4
4. For i in range(num_pointers):
    a. Read 4-byte LE uint32 at offset 0x04 + i*4 → pointer_value
    b. abs_pos = STRING_REGION + pointer_value
    c. Find next \x00 after abs_pos
    d. Extract bytes[abs_pos:null_pos] as the string
    e. Decode as UTF-8
5. Read sentinel at offset 0x04 + num_pointers*4
6. Output results
```

---

## Notes

- The header value (`0x2E88` / 11,912) is the byte size of the **string pointer section only** — it does not include the 4-byte sentinel.
- All addresses are **file offsets** unless prefixed with "LUT", "pointer", or "stripped".
- The pointer entries are stored in **ascending file offset order** (by `index_addr`), but the string addresses they point to are **not** in any particular order.
- The sentinel is stored **after** all pointer entries, at file offset `0x2E8C`.
- Strings may contain ANSI escape-like sequences (e.g., `<CF3F300FF>`) used by the game engine for color/formatting.
- The total string content is approximately 86 KB of readable text.
- To modify a string and regenerate the `.dat` file, update `ascii_data` in the JSON and run `textdata_generate.py`. The script recalculates all offsets dynamically.
