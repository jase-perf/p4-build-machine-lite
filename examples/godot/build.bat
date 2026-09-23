@echo off
rem Builds a Godot 4 project on Windows. Put it and build.sh next to project.godot and submit them.
rem Needs a "Windows Desktop" export preset, Godot's export templates on this computer,
rem and GODOT set to your Godot _console.exe (or godot on PATH).
if "%GODOT%"=="" set GODOT=godot
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0build
if "%BUILD_KIND%"=="" set BUILD_KIND=test
set SMOKE=%TEMP%\smoke-%RANDOM%.log
rem Work in this script's folder (%~dp0), wherever it's run from.
cd /d "%~dp0"
if not exist "%BUILD_OUTPUT%" mkdir "%BUILD_OUTPUT%"

rem The two things that are usually missing. Without these checks, cmd says only
rem "'"godot"' is not recognized", and Godot buries its own reason in pages of output.
set GODOT_FOUND=
if exist "%GODOT%" set GODOT_FOUND=1
where "%GODOT%" > nul 2>&1 && set GODOT_FOUND=1
if not defined GODOT_FOUND echo Can't find Godot: %GODOT%. Set GODOT in build-machine.ini to your Godot _console.exe, or put godot on the PATH. & exit /b 1
if not exist export_presets.cfg echo This project has no export_presets.cfg next to project.godot. In Godot: Project menu, Export, add a "Windows Desktop" preset, then submit the file. & exit /b 1

rem 1. Export a debug build. Only debug builds print script errors.
"%GODOT%" --headless --export-debug "Windows Desktop" "%BUILD_OUTPUT%\MyGame.exe" || exit /b 1

rem 2. Run it for 300 frames. Fail if it crashes or prints an error.
"%BUILD_OUTPUT%\MyGame.console.exe" --headless --quit-after 300 > "%SMOKE%" 2>&1
set SMOKE_EXIT=%ERRORLEVEL%
type "%SMOKE%"
rem findstr's exit code is 0 when it finds the text.
findstr /C:"ERROR" "%SMOKE%" > nul
set SMOKE_ERROR=%ERRORLEVEL%
del "%SMOKE%"
if not "%SMOKE_EXIT%"=="0" exit /b 1
if "%SMOKE_ERROR%"=="0" exit /b 1
if /I not "%BUILD_KIND%"=="release" exit /b 0

rem 3. Release builds: swap in a release export, and check it starts.
rem    (start /wait is how a windowed program's exit code comes back.)
del /q "%BUILD_OUTPUT%\*"
"%GODOT%" --headless --export-release "Windows Desktop" "%BUILD_OUTPUT%\MyGame.exe" || exit /b 1
echo Starting the release build for 300 frames
start /wait "" "%BUILD_OUTPUT%\MyGame.exe" --headless --quit-after 300
if not "%ERRORLEVEL%"=="0" exit /b 1
exit /b 0
