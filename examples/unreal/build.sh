#!/usr/bin/env bash
# Builds an Unreal Engine 5 project on macOS or Linux. Put it and build.bat next to the
# .uproject and submit them. On macOS it finds the engine your project names, installed by
# the Epic Games Launcher, and needs Xcode. On Linux, or for a source-built engine, set
# UE_ROOT in build-machine.ini to the engine's folder. Run by hand, the game lands in Packaged.
set -e
cd "$(dirname "$0")"                # work in this script's folder, wherever it's run from
BUILD_OUTPUT="${BUILD_OUTPUT:-$PWD/Packaged}"
PROJECT="$(ls "$PWD"/*.uproject 2>/dev/null | head -1)"
if [ -z "$PROJECT" ]; then echo "There's no .uproject next to this script."; exit 1; fi
VERSION="$(sed -n 's/.*"EngineAssociation" *: *"\([^"]*\)".*/\1/p' "$PROJECT")"
if [ "$(uname)" = Darwin ]; then
    UE_ROOT="${UE_ROOT:-/Users/Shared/Epic Games/UE_$VERSION}" PLATFORM=Mac
else
    PLATFORM=Linux
fi
if [ ! -f "$UE_ROOT/Engine/Build/BatchFiles/RunUAT.sh" ]; then
    echo "Can't find Unreal Engine $VERSION. Set UE_ROOT in build-machine.ini to its folder."; exit 1
fi

# Test builds package Development; release builds package Shipping.
CONFIG=Development
if [ "$BUILD_KIND" = release ]; then CONFIG=Shipping; fi

# Compile, cook and package. A missing asset or a broken Blueprint fails the cook.
"$UE_ROOT/Engine/Build/BatchFiles/RunUAT.sh" BuildCookRun -project="$PROJECT" -platform="$PLATFORM" -clientconfig="$CONFIG" -build -cook -stage -pak -archive -archivedirectory="$BUILD_OUTPUT" -noP4 -utf8output
