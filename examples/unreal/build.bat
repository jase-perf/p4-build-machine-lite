@echo off
rem Builds an Unreal Engine 5 project on Windows. Put it and build.sh next to the .uproject
rem and submit them. It finds the engine your project names, whether the Epic Games Launcher
rem installed it or you registered a source build. Otherwise set UE_ROOT in build-machine.ini.
rem Run by hand, the game lands in Packaged (Build is one of Unreal's own folders).
if "%BUILD_OUTPUT%"=="" set BUILD_OUTPUT=%~dp0Packaged
for %%f in ("%~dp0*.uproject") do set PROJECT=%%f
for /f "tokens=2 delims=:, " %%v in ('findstr "EngineAssociation" "%PROJECT%"') do set "ENGINE=%%~v"
if "%UE_ROOT%"=="" for /f "tokens=2,*" %%a in ('reg query "HKLM\SOFTWARE\EpicGames\Unreal Engine\%ENGINE%" /v InstalledDirectory 2^>nul ^| findstr REG_SZ') do set "UE_ROOT=%%b"
if "%UE_ROOT%"=="" for /f "tokens=2,*" %%a in ('reg query "HKCU\Software\Epic Games\Unreal Engine\Builds" /v "%ENGINE%" 2^>nul ^| findstr REG_SZ') do set "UE_ROOT=%%b"
if not exist "%UE_ROOT%\Engine\Build\BatchFiles\RunUAT.bat" echo Can't find Unreal Engine %ENGINE%. Set UE_ROOT in build-machine.ini to its folder. & exit /b 1

rem Test builds package Development; release builds package Shipping.
set CONFIG=Development
if /I "%BUILD_KIND%"=="release" set CONFIG=Shipping

rem Compile, cook and package. A missing asset or a broken Blueprint fails the cook.
call "%UE_ROOT%\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="%PROJECT%" -platform=Win64 -clientconfig=%CONFIG% -build -cook -stage -pak -archive -archivedirectory="%BUILD_OUTPUT%" -noP4 -utf8output || exit /b 1
