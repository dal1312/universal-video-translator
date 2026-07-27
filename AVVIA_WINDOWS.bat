@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Esegui prima INSTALL_WINDOWS.bat
  pause
  exit /b 1
)

start "" /b ollama serve >nul 2>nul
".venv\Scripts\python.exe" universal_video_translator.py
