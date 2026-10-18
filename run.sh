#!/bin/bash
# run.sh — Full offline mode patch & deploy pipeline
# Reads GAME_APK from .env (defaults to Darkness_Survival.apk)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source .env if it exists
if [ -f ".env" ]; then
    source .env
fi

GAME_APK="${GAME_APK:-Darkness_Survival.apk}"

# ── Dependency checks ─────────────────────────────────────────────────────────

_missing=()

check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        _missing+=("$2")
    fi
}

check_cmd apktool      "apktool not installed. Install it with: sudo apt install apktool (or download from https://ibotpeaches.github.io/Apktool/)"
check_cmd adb          "adb not found. Install Android SDK Platform Tools or set ANDROID_HOME."
check_cmd jarsigner    "Java/JDK not found. Install JDK 8+ (e.g. sudo apt install openjdk-8-jdk)."
check_cmd python3      "python3 not found. Install Python 3.10+."

if [ ${#_missing[@]} -gt 0 ]; then
    echo ""
    echo "========================================"
    echo "ERROR: Missing dependencies"
    echo "========================================"
    for msg in "${_missing[@]}"; do
        echo "  - $msg"
    done
    echo "========================================"
    echo ""
    exit 1
fi

echo "=== Darkness Survival — Offline Mode Patch Pipeline ==="
echo "APK: $GAME_APK"
echo ""

# Step 1: Decompile if project/ doesn't exist
if [ ! -d "project" ]; then
    echo "=== Step 1: Decompile APK ==="
    ./1-import.sh "$GAME_APK"
    echo ""
else
    echo "=== Step 1: project/ already exists, skipping decompile ==="
    echo ""
fi

# Step 2: Patch native binary
echo "=== Step 2: Patch native binary ==="
./mod-binary.sh
echo ""

# Step 3: Patch smali
echo "=== Step 3: Patch smali ==="
./mod-smali.sh
echo ""

# Step 4: Recompile
echo "=== Step 4: Recompile APK ==="
./2-compile.sh
echo ""

# Step 5: Deploy to device
echo "=== Step 5: Deploy to device ==="
./3-re-apply.sh
echo ""

echo "=== Done ==="
