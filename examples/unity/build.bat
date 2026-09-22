@echo off
rem Builds a Unity 6 project. Copy this folder's contents into your project (build.bat
rem next to Assets) and submit them. Set UNITY to your Unity.exe, e.g.
rem   C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0build
if not exist "%BUILD_OUTPUT%" mkdir "%BUILD_OUTPUT%"

rem 1. Build the scenes in Build Profiles. Assets\Editor\BuildScript.cs makes a
rem    development build, or a normal one when BUILD_KIND is release.
"%UNITY%" -batchmode -quit -projectPath "%~dp0." -buildTarget win64 -executeMethod BuildScript.Build -logFile - || exit /b 1

rem 2. Run it. Assets\SmokeTest.cs quits after 5 seconds, with exit code 1 on any error.
"%BUILD_OUTPUT%\MyGame.exe" -batchmode -nographics -smoketest -logFile - || exit /b 1
