@echo off
rem Builds a Godot 4 project. Put it next to project.godot and submit it.
rem Needs a "Windows Desktop" export preset, Godot's export templates on this computer,
rem and GODOT set to your Godot _console.exe (or godot on PATH).
if "%GODOT%"=="" set GODOT=godot
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0build
if "%BUILD_KIND%"=="" set BUILD_KIND=test
rem Work in this script's folder (%~dp0), wherever it's run from.
cd /d "%~dp0"
if not exist "%BUILD_OUTPUT%" mkdir "%BUILD_OUTPUT%"

rem 1. Export a debug build. Only debug builds print script errors.
"%GODOT%" --headless --export-debug "Windows Desktop" "%BUILD_OUTPUT%\MyGame.exe" || exit /b 1

rem 2. Run it for 300 frames. Fail if it crashes or prints an error.
"%BUILD_OUTPUT%\MyGame.console.exe" --headless --quit-after 300 > smoke.log 2>&1
set SMOKE_EXIT=%ERRORLEVEL%
type smoke.log
if not "%SMOKE_EXIT%"=="0" exit /b 1
findstr /C:"ERROR" smoke.log > nul && exit /b 1
if /I not "%BUILD_KIND%"=="release" exit /b 0

rem 3. Release builds: swap in a release export, and check it starts.
rem    (start /wait is how a windowed program's exit code comes back.)
del /q "%BUILD_OUTPUT%\*"
"%GODOT%" --headless --export-release "Windows Desktop" "%BUILD_OUTPUT%\MyGame.exe" || exit /b 1
echo Starting the release build for 300 frames
start /wait "" "%BUILD_OUTPUT%\MyGame.exe" --headless --quit-after 300
if not "%ERRORLEVEL%"=="0" exit /b 1
exit /b 0
