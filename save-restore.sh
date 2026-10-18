#!/bin/bash
# save-restore.sh — Restores all backed up game save files to the device
# Usage: ./save-restore.sh
#
# Requires: save-backup.sh has been run (or .bak files exist in sources/saves/)
# Side effect: launches the app for 5s then stops it before restoring,
#              then relaunches the app.

SAVES_DIR="$PWD/sources/saves"
RESTORE_COUNT=$(ls "$SAVES_DIR"/gamedata*.bak 2>/dev/null | wc -l)

if [ "$RESTORE_COUNT" -eq 0 ]; then
    echo "No backup files found in $SAVES_DIR/"
    exit 1
fi

echo "Restoring $RESTORE_COUNT save file(s)..."

# Start the app so it creates its data directory and runs
echo "  Launching app (5s)..."
adb logcat -c
adb shell am start -n com.zeroplusplus.rpg1/com.zeroplusplus.rpg1.RPG1
sleep 5

# Stop the app
echo "  Stopping app..."
adb shell am force-stop com.zeroplusplus.rpg1
sleep 2

# Restore each backed up save file
for bak in "$SAVES_DIR"/gamedata*.bak; do
    bname="${bak##*/}"
    name="${bname%.bak}"
    echo "  Restoring $name..."
    adb push "$bak" "/data/local/tmp/$name" 2>/dev/null
    adb shell "run-as com.zeroplusplus.rpg1 touch /data/data/com.zeroplusplus.rpg1/files/$name" 2>/dev/null
    adb shell "run-as com.zeroplusplus.rpg1 dd if=/data/local/tmp/$name of=/data/data/com.zeroplusplus.rpg1/files/$name bs=4096" 2>/dev/null
    RESTORE_SIZE=$(adb shell "run-as com.zeroplusplus.rpg1 cat /data/data/com.zeroplusplus.rpg1/files/$name" 2>/dev/null | wc -c)
    EXPECTED_SIZE=$(wc -c < "$bak")
    if [ "$RESTORE_SIZE" = "$EXPECTED_SIZE" ]; then
        echo "    $name restored successfully ($RESTORE_SIZE bytes)."
    else
        echo "    Warning: $name restore may have failed (got '$RESTORE_SIZE' bytes, expected $EXPECTED_SIZE)."
    fi
    adb shell rm -f "/data/local/tmp/$name" 2>/dev/null
done

echo "  Relaunching app..."
sleep 2

adb logcat -c
adb shell am start -n com.zeroplusplus.rpg1/com.zeroplusplus.rpg1.RPG1
sleep 3

APP_PID=$(adb shell ps | grep -w 'com\.zeroplusplus\.rpg1' | awk '{print $2}' | head -n1)
if [ -n "$APP_PID" ]; then
    echo "Found app PID: $APP_PID"
    echo "Waiting 5 seconds before capturing logcat..."
    sleep 5
    adb logcat -d --pid="$APP_PID" | grep 51413
else
    echo "Warning: Could not find app PID, dumping crash log."
    adb logcat -d | grep -E "FATAL|AndroidRuntime|rpg1|crash|Fatal|Exception|Error\(|E/" | tail -100
fi
