@echo off
setlocal
cd /d "%~dp0"
set "UVT_INSTALLER=%~dp0scripts\windows\Install-Optional-Engines.ps1"
if not exist "%UVT_INSTALLER%" set "UVT_INSTALLER=%~dp0INSTALLA_MOTORI_OPZIONALI_WINDOWS.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%UVT_INSTALLER%" %*
set "UVT_EXIT=%ERRORLEVEL%"
if not "%UVT_NONINTERACTIVE%"=="1" pause
exit /b %UVT_EXIT%
