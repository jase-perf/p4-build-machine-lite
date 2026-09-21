@echo off
rem Build script for a Godot 4 project. Put it next to project.godot and submit it.
rem The build machine runs it after syncing. You can run it yourself too.
rem Needs: export_presets.cfg with a "Windows Desktop" preset (submitted), export templates
rem installed on this computer, and GODOT set to your Godot _console.exe (or godot on PATH).
if "%GODOT%"=="" set GODOT=godot
rem %~dp0 is this script's own folder.
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0build
rem BUILD_KIND is "test" for an everyday build, "release" for the copy players get.
if "%BUILD_KIND%"=="" set BUILD_KIND=test
if not exist "%BUILD_OUTPUT%" mkdir "%BUILD_OUTPUT%"

rem 1. Export the game as a debug build. A release export prints no script errors at all,
rem    so a debug export is the only one step 2 can learn anything from.
"%GODOT%" --headless --export-debug "Windows Desktop" "%BUILD_OUTPUT%\MyGame.exe" || exit /b 1

rem 2. Smoke test: run it for 300 frames. Fail if it crashed or printed an error.
"%BUILD_OUTPUT%\MyGame.console.exe" --headless --quit-after 300 > smoke.log 2>&1
set SMOKE_EXIT=%ERRORLEVEL%
type smoke.log
if not "%SMOKE_EXIT%"=="0" exit /b 1
rem findstr succeeds when it finds the text, and then we fail the build.
findstr /C:"ERROR" smoke.log > nul && exit /b 1

rem A test build is done: whatever is in BUILD_OUTPUT becomes the zip people download.
if /I not "%BUILD_KIND%"=="release" exit /b 0

rem 3. A release build replaces it with a release export: no debug tools, and it runs faster.
del /q "%BUILD_OUTPUT%\*"
"%GODOT%" --headless --export-release "Windows Desktop" "%BUILD_OUTPUT%\MyGame.exe" || exit /b 1

rem 4. Start the release copy as well. It won't print script errors, so this only catches a
rem    game that won't start — but this is the copy people get, so it's worth five seconds.
rem    start /wait is how a windowed program's exit code comes back in a .bat file. It runs
rem    in a window of its own, so nothing it prints reaches this log.
echo Starting the release build for 300 frames
start /wait "" "%BUILD_OUTPUT%\MyGame.exe" --headless --quit-after 300
if not "%ERRORLEVEL%"=="0" exit /b 1
exit /b 0
