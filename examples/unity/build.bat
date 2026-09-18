@echo off
rem Build script for a Unity 6 project. Put it next to the Assets folder and submit it,
rem along with SmokeTest.cs somewhere under Assets. Set UNITY to your Unity.exe, e.g.
rem   C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0build
if not exist "%BUILD_OUTPUT%" mkdir "%BUILD_OUTPUT%"

rem 1. Build the scenes listed in Build Profiles (File > Build Profiles > Scene List).
"%UNITY%" -batchmode -quit -projectPath "%~dp0." -buildWindows64Player "%BUILD_OUTPUT%\MyGame.exe" -logFile - || exit /b 1

rem 2. Smoke test: SmokeTest.cs quits after 5 seconds, with exit code 1 on any error.
"%BUILD_OUTPUT%\MyGame.exe" -batchmode -nographics -smoketest -logFile - || exit /b 1
