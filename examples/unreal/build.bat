@echo off
rem Build script for an Unreal Engine 5 project. Put it next to the .uproject and submit it.
rem Set UE_ROOT to your engine folder, e.g. C:\Program Files\Epic Games\UE_5.7
rem Run by hand, the game lands in Packaged (not Build: Unreal keeps icons in there).
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0Packaged
for %%f in ("%~dp0*.uproject") do set PROJECT=%%f

rem Compile, cook and package the game. A missing asset or a Blueprint that
rem won't compile fails the cook, and this line with it.
call "%UE_ROOT%\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="%PROJECT%" -platform=Win64 -clientconfig=Development -build -cook -stage -pak -archive -archivedirectory="%BUILD_OUTPUT%" -noP4 -utf8output || exit /b 1
