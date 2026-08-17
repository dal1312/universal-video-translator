@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Build-Release.ps1" %*
set "UVT_EXIT=%ERRORLEVEL%"
if not "%UVT_NONINTERACTIVE%"=="1" pause
exit /b %UVT_EXIT%
