@echo off
rem Build script for a Unity 6 project. Copy this whole example folder's contents into
rem your project (build.bat and .p4ignore next to Assets, and the two .cs files where
rem they already are, under Assets) and submit them. Unity only runs -executeMethod on
rem scripts inside an Assets\Editor folder. Set UNITY to your Unity.exe, e.g.
rem   C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0build
rem BUILD_KIND is "test" for an everyday build, "release" for the copy players get.
rem BuildScript.cs reads it: a test build is a Development Build, a release build isn't.
if "%BUILD_KIND%"=="" set BUILD_KIND=test
if not exist "%BUILD_OUTPUT%" mkdir "%BUILD_OUTPUT%"

rem 1. Build the scenes listed in Build Profiles (File > Build Profiles > Scene List).
"%UNITY%" -batchmode -quit -projectPath "%~dp0." -buildTarget win64 -executeMethod BuildScript.Build -logFile - || exit /b 1

rem 2. Smoke test: SmokeTest.cs quits after 5 seconds, with exit code 1 on any error.
"%BUILD_OUTPUT%\MyGame.exe" -batchmode -nographics -smoketest -logFile - || exit /b 1
