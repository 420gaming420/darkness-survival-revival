#!/bin/bash
# save-backup.sh — Backs up all game save files from the device to sources/saves/
# Usage: ./save-backup.sh

SAVES_DIR="$PWD/sources/saves"
BACKUP_COUNT=0
mkdir -p "$SAVES_DIR"

echo "Backing up save files..."

# Discover which gamedata*.dat files exist on the device
FILE_LIST=$(adb shell "run-as com.zeroplusplus.rpg1 ls /data/data/com.zeroplusplus.rpg1/files/ | grep ^gamedata" 2>/dev/null || true)
if [ -z "$FILE_LIST" ]; then
    echo "No save files found on device."
    exit 1
fi

echo "  Found files: $(echo "$FILE_LIST" | wc -l)" >&2
while IFS= read -r bname; do
    echo "  Processing: [$bname]" >&2
    echo "  Backing up $bname..."
    adb shell < /dev/null "run-as com.zeroplusplus.rpg1 cat /data/data/com.zeroplusplus.rpg1/files/$bname" > "$SAVES_DIR/$bname.bak" 2>/dev/null
    if [ $? -eq 0 ] && [ -s "$SAVES_DIR/$bname.bak" ]; then
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
        echo "    OK ($(wc -c < "$SAVES_DIR/$bname.bak") bytes)."
    else
        echo "    FAILED or empty."
    fi
done <<< "$FILE_LIST"

if [ "$BACKUP_COUNT" -gt 0 ]; then
    echo "Save files backed up successfully ($BACKUP_COUNT file(s) in $SAVES_DIR/)."
else
    echo "No save files were backed up."
    exit 1
fi
