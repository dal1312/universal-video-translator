@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Esegui prima INSTALL_WINDOWS.bat
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install "pyinstaller>=6,<7"
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name UniversalVideoTranslator ^
  --paths src ^
  --collect-all pyttsx3 ^
  --collect-all soundcard ^
  --collect-all faster_whisper ^
  --collect-all ctranslate2 ^
  --collect-all yt_dlp ^
  universal_video_translator.py

if errorlevel 1 (
  echo BUILD FALLITA
  pause
  exit /b 1
)

echo EXE creato in dist\UniversalVideoTranslator.exe
pause
