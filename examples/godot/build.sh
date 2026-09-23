#!/usr/bin/env bash
# Builds a Godot 4 project on macOS or Linux. Put it and build.bat next to project.godot and
# submit them. Needs a "macOS" or "Linux" export preset and Godot's export templates on this
# computer. If Godot isn't on the PATH or in Applications, set GODOT in build-machine.ini.
set -e
cd "$(dirname "$0")"                # work in this script's folder, wherever it's run from
GODOT="${GODOT:-$(command -v godot || echo /Applications/Godot.app)}"
if [ -d "$GODOT" ]; then GODOT="$GODOT/Contents/MacOS/Godot"; fi    # a macOS app is a folder
if [ ! -x "$GODOT" ]; then echo "Can't find Godot. Set GODOT in build-machine.ini to your Godot program."; exit 1; fi
BUILD_OUTPUT="${BUILD_OUTPUT:-$PWD/build}"
BUILD_KIND="${BUILD_KIND:-test}"
SMOKE="$(mktemp)"
trap 'rm -f "$SMOKE"' EXIT
mkdir -p "$BUILD_OUTPUT"
if [ "$(uname)" = Darwin ]; then PRESET="macOS" GAME="MyGame.app"; else PRESET="Linux" GAME="MyGame.x86_64"; fi
# Godot buries its reason for this in pages of output, so say it here.
if [ ! -f export_presets.cfg ]; then
    echo "This project has no export_presets.cfg next to project.godot."
    echo "In Godot: Project menu, Export, add a \"$PRESET\" preset, then submit the file."
    exit 1
fi

run_game() {                        # a macOS app is a folder: its program's name is in Info.plist
    local program="$BUILD_OUTPUT/$GAME"
    if [ -d "$program" ]; then
        program="$program/Contents/MacOS/$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$program/Contents/Info.plist")"
    fi
    "$program" --headless --quit-after 300
}

# 1. Export a debug build. Only debug builds print script errors.
"$GODOT" --headless --export-debug "$PRESET" "$BUILD_OUTPUT/$GAME"

# 2. Run it for 300 frames. Fail if it crashes or prints an error.
smoke_exit=0
run_game > "$SMOKE" 2>&1 || smoke_exit=$?
cat "$SMOKE"
if [ "$smoke_exit" -ne 0 ] || grep -q "ERROR" "$SMOKE"; then exit 1; fi
if [ "$BUILD_KIND" != release ]; then exit 0; fi

# 3. Release builds: swap in a release export, and check it starts.
rm -rf "${BUILD_OUTPUT:?}"/*
"$GODOT" --headless --export-release "$PRESET" "$BUILD_OUTPUT/$GAME"
echo "Starting the release build for 300 frames"
run_game
