#!/bin/bash
# mod-binary.sh — Apply offline mode hex patches to libcocos2dcpp.so
# Requires: project/ already decompressed via 1-import.sh

set -e

BINARY="project/lib/armeabi/libcocos2dcpp.so"
EXPECTED_SHA="a77254afb0603f10cb31ef555bb6b3c94992950609da13f1ec6c8f82cd7c4a5e"

if [ ! -f "$BINARY" ]; then
    echo "Error: $BINARY not found. Run 1-import.sh first."
    exit 1
fi

ACTUAL_SHA=$(sha256sum "$BINARY" | awk '{print $1}')
echo "Binary SHA256: $ACTUAL_SHA"

if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
    echo "Error: Expected original binary SHA256 [$EXPECTED_SHA] but got [$ACTUAL_SHA]"
    echo "The binary has already been patched or is not the original APK content."
    exit 1
fi

echo "Original binary confirmed. Applying patches..."

python3 - <<'PYEOF'
import sys

BINARY = "project/lib/armeabi/libcocos2dcpp.so"
with open(BINARY, "rb") as f:
    data = bytearray(f.read())

print(f"Loaded {len(data)} bytes from {BINARY}")

patches = [
    # (name, offset, before_bytes, after_bytes)
    ("A", 0x3c1608, bytes([0x01, 0xd0]), bytes([0x01, 0xd1])),
    ("B", 0x3d5d00, bytes([0x00, 0x68, 0x70, 0x47]), bytes([0x02, 0x20, 0x70, 0x47])),
    ("C", 0x3d5d04, bytes([0xf0, 0xb5, 0x2e, 0x4d]), bytes([0xff, 0x20, 0x70, 0x47])),
    ("D", 0x3d5e98, bytes([0x01, 0x4b, 0xc0, 0x56, 0x70, 0x47]), bytes([0x01, 0x20, 0x70, 0x47, 0xc0, 0x46])),
    ("E", 0x3c04c0, bytes([0x38, 0xb5, 0x08, 0x4d]), bytes([0x02, 0x20, 0x70, 0x47])),
]

applied = 0
skipped = 0

for name, offset, before, after in patches:
    current = bytes(data[offset:offset + len(before)])
    if current == after:
        print(f"  Patch {name} at 0x{offset:x}: already applied, skipping")
        skipped += 1
    elif current == before:
        data[offset:offset + len(before)] = after
        print(f"  Patch {name} at 0x{offset:x}: applied ({before.hex()} -> {after.hex()})")
        applied += 1
    else:
        print(f"  Patch {name} at 0x{offset:x}: unexpected bytes ({current.hex()}), expected {before.hex()}")
        sys.exit(1)

with open(BINARY, "wb") as f:
    f.write(data)

print(f"\nApplied {applied} patches, skipped {skipped}. Wrote {len(data)} bytes to {BINARY}.")
PYEOF

echo "Binary patched successfully."
