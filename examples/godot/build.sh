#!/usr/bin/env bash
# Build script for a Godot 4 project on Linux. Put it next to project.godot and submit it.
# The build machine runs it after syncing. You can run it yourself too.
# Needs: export_presets.cfg with a "Linux" preset (submitted), export templates installed
# on this computer, and GODOT set to your Godot binary (or godot on PATH).
set -e
GODOT="${GODOT:-godot}"
BUILD_OUTPUT="${BUILD_OUTPUT:-$PWD/build}"
# BUILD_KIND is "test" for an everyday build, "release" for the copy players get.
BUILD_KIND="${BUILD_KIND:-test}"
mkdir -p "$BUILD_OUTPUT"

# 1. Export the game as a debug build. A release export prints no script errors at all,
#    so a debug export is the only one step 2 can learn anything from.
"$GODOT" --headless --export-debug "Linux" "$BUILD_OUTPUT/MyGame.x86_64"

# 2. Smoke test: run it for 300 frames. Fail if it crashed or printed an error.
smoke_exit=0
"$BUILD_OUTPUT/MyGame.x86_64" --headless --quit-after 300 > smoke.log 2>&1 || smoke_exit=$?
cat smoke.log
if [ "$smoke_exit" -ne 0 ] || grep -q "ERROR" smoke.log; then exit 1; fi

# A test build is done: whatever is in BUILD_OUTPUT becomes the zip people download.
if [ "$BUILD_KIND" != release ]; then exit 0; fi

# 3. A release build replaces it with a release export: no debug tools, and it runs faster.
rm -f "$BUILD_OUTPUT"/*
"$GODOT" --headless --export-release "Linux" "$BUILD_OUTPUT/MyGame.x86_64"

# 4. Start the release copy as well. It won't print script errors, so this only catches a
#    game that won't start — but this is the copy people get, so it's worth five seconds.
echo "Starting the release build for 300 frames"
"$BUILD_OUTPUT/MyGame.x86_64" --headless --quit-after 300
