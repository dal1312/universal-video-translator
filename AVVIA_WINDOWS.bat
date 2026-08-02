@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Esegui prima INSTALL_WINDOWS.bat
  if not "%UVT_NONINTERACTIVE%"=="1" pause
  exit /b 1
)

set "UVT_OLLAMA=ollama.exe"
where ollama.exe >nul 2>nul
if errorlevel 1 if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "UVT_OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%UVT_OLLAMA%" start "" /b "%UVT_OLLAMA%" serve >nul 2>nul
if "%UVT_OLLAMA%"=="ollama.exe" where ollama.exe >nul 2>nul && start "" /b ollama serve >nul 2>nul
".venv\Scripts\python.exe" universal_video_translator.py
set "UVT_EXIT=%ERRORLEVEL%"
exit /b %UVT_EXIT%
