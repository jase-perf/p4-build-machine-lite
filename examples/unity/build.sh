#!/usr/bin/env bash
# Builds a Unity 6 project on macOS or Linux. Copy this folder's contents into your project
# (build.bat and build.sh next to Assets) and submit them. It uses the Unity version your
# project was saved with, from Unity Hub's usual folder. Otherwise set UNITY in build-machine.ini.
set -e
cd "$(dirname "$0")"                # work in this script's folder, wherever it's run from
BUILD_OUTPUT="${BUILD_OUTPUT:-$PWD/build}"
mkdir -p "$BUILD_OUTPUT"
VERSION="$(sed -n 's/^m_EditorVersion: *//p' ProjectSettings/ProjectVersion.txt | tr -d '\r')"
if [ "$(uname)" = Darwin ]; then
    UNITY="${UNITY:-/Applications/Unity/Hub/Editor/$VERSION/Unity.app}" TARGET=osxuniversal
else
    UNITY="${UNITY:-$HOME/Unity/Hub/Editor/$VERSION/Editor/Unity}" TARGET=linux64
fi
if [ -d "$UNITY" ]; then UNITY="$UNITY/Contents/MacOS/Unity"; fi    # a macOS app is a folder
if [ ! -x "$UNITY" ]; then
    echo "Can't find Unity at $UNITY. Install your project's version with Unity Hub, or set UNITY in build-machine.ini."; exit 1
fi

# 1. Build the scenes in Build Profiles. Assets/Editor/BuildScript.cs makes a
#    development build, or a normal one when BUILD_KIND is release.
"$UNITY" -batchmode -quit -projectPath "$PWD" -buildTarget "$TARGET" -executeMethod BuildScript.Build -logFile -

# 2. Run it. Assets/SmokeTest.cs quits after 5 seconds, with exit code 1 on any error.
GAME="$BUILD_OUTPUT/MyGame.x86_64"
if [ -d "$BUILD_OUTPUT/MyGame.app" ]; then   # a macOS app: its program's name is in Info.plist
    GAME="$BUILD_OUTPUT/MyGame.app/Contents/MacOS/$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$BUILD_OUTPUT/MyGame.app/Contents/Info.plist")"
fi
"$GAME" -batchmode -nographics -smoketest -logFile -
