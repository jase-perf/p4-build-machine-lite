#!/usr/bin/env bash
# Builds a Godot 4 project on Linux. Put it next to project.godot and submit it.
# Needs a "Linux" export preset, Godot's export templates on this computer,
# and GODOT set to your Godot binary (or godot on PATH).
set -e
cd "$(dirname "$0")"                # work in this script's folder, wherever it's run from
GODOT="${GODOT:-godot}"
BUILD_OUTPUT="${BUILD_OUTPUT:-$PWD/build}"
BUILD_KIND="${BUILD_KIND:-test}"
mkdir -p "$BUILD_OUTPUT"

# 1. Export a debug build. Only debug builds print script errors.
"$GODOT" --headless --export-debug "Linux" "$BUILD_OUTPUT/MyGame.x86_64"

# 2. Run it for 300 frames. Fail if it crashes or prints an error.
smoke_exit=0
"$BUILD_OUTPUT/MyGame.x86_64" --headless --quit-after 300 > smoke.log 2>&1 || smoke_exit=$?
cat smoke.log
if [ "$smoke_exit" -ne 0 ] || grep -q "ERROR" smoke.log; then exit 1; fi
if [ "$BUILD_KIND" != release ]; then exit 0; fi

# 3. Release builds: swap in a release export, and check it starts.
rm -f "$BUILD_OUTPUT"/*
"$GODOT" --headless --export-release "Linux" "$BUILD_OUTPUT/MyGame.x86_64"
echo "Starting the release build for 300 frames"
"$BUILD_OUTPUT/MyGame.x86_64" --headless --quit-after 300
