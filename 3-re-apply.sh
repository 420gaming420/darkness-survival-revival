#!/bin/bash

echo "=== Compile APK ==="
./2-compile.sh
if [ $? -ne 0 ]; then
    echo "Error: Compilation failed."
    exit 1
fi

echo "=== Applying compiled APK to device==="

# It's better to manually back up your save to avoid from overwriting it accidently.
# # --- Backup save files before uninstall ---
# echo "Backing up save files..."
# ./save-backup.sh
# if [ $? -ne 0 ]; then
#     echo "Warning: Save backup failed or no saves found. Will skip restore after install."
# fi

echo "Uninstalling..."
adb uninstall com.zeroplusplus.rpg1
if [ $? -ne 0 ]; then
    echo "Warning: Uninstall failed or package not installed. Continuing anyway."
fi

echo "Installing modified APK..."
adb install -r "$PWD"/project.apk
if [ $? -ne 0 ]; then
    echo "Error: Installation failed."
    exit 1
fi

# --- Restore save files after install ---
./save-restore.sh

# Uncomment this if you comment out/remove ./save-restore.sh
# echo "=== Logcat (last 100 lines for com.zeroplusplus.rpg1) ==="
# sleep 5
#
# APP_PID=$(adb shell ps | grep -w 'com\.zeroplusplus\.rpg1' | awk '{print $2}' | head -n1)
# if [ -n "$APP_PID" ]; then
#     echo "Found app PID: $APP_PID"
#     echo "Waiting 10 seconds before capturing logcat..."
#     sleep 10
#     adb logcat --pid="$APP_PID" -v threadtime -t 100
# else
#     echo "Warning: Could not find app PID, dumping crash log."
#     adb logcat -d | grep -E "FATAL|AndroidRuntime|rpg1|crash|Fatal|Exception|Error\(|E/" | tail -100
# fi

echo "Done."
