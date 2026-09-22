@echo off
rem Builds a Unity 6 project on Windows. Copy this folder's contents into your project
rem (build.bat and build.sh next to Assets) and submit them. It uses the Unity version your
rem project was saved with, from Unity Hub's usual folder. Otherwise set UNITY in build-machine.ini.
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0build
if not exist "%BUILD_OUTPUT%" mkdir "%BUILD_OUTPUT%"
if "%UNITY%"=="" for /f "tokens=2" %%v in ('findstr /b "m_EditorVersion:" "%~dp0ProjectSettings\ProjectVersion.txt"') do set "UNITY=%ProgramFiles%\Unity\Hub\Editor\%%v\Editor\Unity.exe"
if not exist "%UNITY%" echo Can't find Unity at %UNITY%. Install your project's version with Unity Hub, or set UNITY in build-machine.ini. & exit /b 1

rem 1. Build the scenes in Build Profiles. Assets\Editor\BuildScript.cs makes a
rem    development build, or a normal one when BUILD_KIND is release.
"%UNITY%" -batchmode -quit -projectPath "%~dp0." -buildTarget win64 -executeMethod BuildScript.Build -logFile - || exit /b 1

rem 2. Run it. Assets\SmokeTest.cs quits after 5 seconds, with exit code 1 on any error.
"%BUILD_OUTPUT%\MyGame.exe" -batchmode -nographics -smoketest -logFile - || exit /b 1
