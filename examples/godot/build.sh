#!/usr/bin/env bash
# Build script for a Godot 4 project on Linux. Put it next to project.godot and submit it.
# The build machine runs it after syncing. You can run it yourself too.
# Needs: export_presets.cfg with a "Linux" preset (submitted), export templates installed
# on this computer, and GODOT set to your Godot binary (or godot on PATH).
set -e
GODOT="${GODOT:-godot}"
BUILD_OUTPUT="${BUILD_OUTPUT:-$PWD/build}"
mkdir -p "$BUILD_OUTPUT"

# 1. Export the game. A debug export, so the smoke test below can see script errors.
"$GODOT" --headless --export-debug "Linux" "$BUILD_OUTPUT/MyGame.x86_64"

# 2. Smoke test: run it for 300 frames. Fail if it crashed or printed an error.
smoke_exit=0
"$BUILD_OUTPUT/MyGame.x86_64" --headless --quit-after 300 > smoke.log 2>&1 || smoke_exit=$?
cat smoke.log
if [ "$smoke_exit" -ne 0 ] || grep -q "ERROR" smoke.log; then exit 1; fi
