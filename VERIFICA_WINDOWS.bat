@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERRORE: esegui prima INSTALL_WINDOWS.bat
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install "pytest>=8,<9"
python -m compileall -q src universal_video_translator.py tests
if errorlevel 1 goto failed

python -m pytest -q
if errorlevel 1 goto failed

where ffmpeg >nul 2>nul || goto missing_ffmpeg
where ollama >nul 2>nul || goto missing_ollama
ollama list | findstr /i "translategemma:latest" >nul || goto missing_model

echo.
echo VERIFICA COMPLETATA: codice, test, FFmpeg, Ollama e modello disponibili.
pause
exit /b 0

:missing_ffmpeg
echo ERRORE: FFmpeg non trovato nel PATH.
goto failed

:missing_ollama
echo ERRORE: Ollama non trovato nel PATH.
goto failed

:missing_model
echo ERRORE: modello translategemma:latest non installato.
goto failed

:failed
echo.
echo VERIFICA FALLITA.
pause
exit /b 1
