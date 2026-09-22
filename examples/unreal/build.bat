@echo off
rem Builds an Unreal Engine 5 project. Put it next to the .uproject and submit it.
rem Set UE_ROOT to your engine folder, e.g. C:\Program Files\Epic Games\UE_5.7
rem Run by hand, the game lands in Packaged (Build is one of Unreal's own folders).
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0Packaged
for %%f in ("%~dp0*.uproject") do set PROJECT=%%f

rem Test builds package Development; release builds package Shipping.
set CONFIG=Development
if /I "%BUILD_KIND%"=="release" set CONFIG=Shipping

rem Compile, cook and package. A missing asset or a broken Blueprint fails the cook.
call "%UE_ROOT%\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="%PROJECT%" -platform=Win64 -clientconfig=%CONFIG% -build -cook -stage -pak -archive -archivedirectory="%BUILD_OUTPUT%" -noP4 -utf8output || exit /b 1
