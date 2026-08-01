@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Esegui prima INSTALL_WINDOWS.bat
  if not "%UVT_NONINTERACTIVE%"=="1" pause
  exit /b 1
)

where ollama.exe >nul 2>nul
if not errorlevel 1 start "" /b ollama serve >nul 2>nul
".venv\Scripts\python.exe" universal_video_translator.py
set "UVT_EXIT=%ERRORLEVEL%"
exit /b %UVT_EXIT%
