@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (
  echo ERRORE: Python non trovato nel PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" python -m venv .venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -e ".[audio]"

where ffmpeg >nul 2>nul || (
  echo.
  echo ATTENZIONE: FFmpeg non trovato.
  echo Installa FFmpeg e aggiungilo al PATH prima di tradurre video o audio.
)

where ollama >nul 2>nul || (
  echo.
  echo ATTENZIONE: Ollama non trovato.
  echo Scaricalo da https://ollama.com/download/windows
  goto done
)

ollama pull translategemma:latest

:done
echo.
echo Installazione completata. Avvia con AVVIA_WINDOWS.bat
pause
