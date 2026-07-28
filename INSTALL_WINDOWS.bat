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
python -m pip install -e ".[all]"

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

where espeak-ng >nul 2>nul || (
  echo.
  echo ATTENZIONE: Kokoro richiede eSpeak NG per la voce italiana.
  echo Installa eSpeak NG x64 dal progetto ufficiale:
  echo https://github.com/espeak-ng/espeak-ng/releases
)

where tesseract >nul 2>nul || (
  echo.
  echo ATTENZIONE: Tesseract OCR non trovato.
  echo Installa con: winget install UB-Mannheim.TesseractOCR
  echo Poi riavvia PowerShell.
)

:done
echo.
echo Installazione completata. Avvia con AVVIA_WINDOWS.bat
pause
