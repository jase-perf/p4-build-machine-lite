@echo off
rem Build script for a Godot 4 project. Put it next to project.godot and submit it.
rem The build machine runs it after syncing. You can run it yourself too.
rem Needs: export_presets.cfg with a "Windows Desktop" preset (submitted), export templates
rem installed on this computer, and GODOT set to your Godot _console.exe (or godot on PATH).
if "%GODOT%"=="" set GODOT=godot
rem %~dp0 is this script's own folder.
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0build
if not exist "%BUILD_OUTPUT%" mkdir "%BUILD_OUTPUT%"

rem 1. Export the game. A debug export, so the smoke test below can see script errors.
"%GODOT%" --headless --export-debug "Windows Desktop" "%BUILD_OUTPUT%\MyGame.exe" || exit /b 1

rem 2. Smoke test: run it for 300 frames. Fail if it crashed or printed an error.
"%BUILD_OUTPUT%\MyGame.console.exe" --headless --quit-after 300 > smoke.log 2>&1
set SMOKE_EXIT=%ERRORLEVEL%
type smoke.log
if not "%SMOKE_EXIT%"=="0" exit /b 1
rem findstr succeeds when it finds the text, and then we fail the build.
findstr /C:"ERROR" smoke.log > nul && exit /b 1
exit /b 0
