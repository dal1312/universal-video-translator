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

if not exist "%VIRTUAL_ENV%\Lib\site-packages\language_tags\data\json\index.json" (
  echo ERRORE: language_tags\data\json\index.json non trovato.
  echo Esegui nuovamente INSTALL_WINDOWS.bat.
  pause
  exit /b 1
)

if not exist "%VIRTUAL_ENV%\Lib\site-packages\espeakng_loader\espeak-ng-data" (
  echo ERRORE: espeakng_loader\espeak-ng-data non trovato.
  echo Esegui nuovamente INSTALL_WINDOWS.bat.
  pause
  exit /b 1
)

if exist "dist\UniversalVideoTranslator.exe" del /q "dist\UniversalVideoTranslator.exe"

pyinstaller --noconfirm --clean --onedir --windowed ^
  --name UniversalVideoTranslator ^
  --paths src ^
  --collect-all pyttsx3 ^
  --collect-all soundcard ^
  --collect-all kokoro ^
  --collect-all misaki ^
  --collect-all language_tags ^
  --collect-all phonemizer ^
  --collect-all espeakng_loader ^
  --collect-all torch ^
  --collect-all faster_whisper ^
  --collect-all ctranslate2 ^
  --collect-all yt_dlp ^
  universal_video_translator.py

if errorlevel 1 (
  echo BUILD FALLITA
  pause
  exit /b 1
)

xcopy "%VIRTUAL_ENV%\Lib\site-packages\language_tags\data" "dist\UniversalVideoTranslator\_internal\language_tags\data\" /E /I /Y >nul
if not exist "dist\UniversalVideoTranslator\_internal\language_tags\data\json\index.json" (
  echo BUILD FALLITA: index.json non copiato.
  pause
  exit /b 1
)

xcopy "%VIRTUAL_ENV%\Lib\site-packages\espeakng_loader\espeak-ng-data" "dist\UniversalVideoTranslator\_internal\espeakng_loader\espeak-ng-data\" /E /I /Y >nul
if not exist "dist\UniversalVideoTranslator\_internal\espeakng_loader\espeak-ng-data" (
  echo BUILD FALLITA: espeak-ng-data non copiato.
  pause
  exit /b 1
)

for /f "delims=" %%F in ('where ffmpeg') do if not defined UVT_FFMPEG set "UVT_FFMPEG=%%F"
for /f "delims=" %%F in ('where ffprobe') do if not defined UVT_FFPROBE set "UVT_FFPROBE=%%F"
if not defined UVT_FFMPEG (
  echo BUILD FALLITA: ffmpeg.exe non trovato.
  pause
  exit /b 1
)
copy /Y "%UVT_FFMPEG%" "dist\UniversalVideoTranslator\ffmpeg.exe" >nul
if defined UVT_FFPROBE copy /Y "%UVT_FFPROBE%" "dist\UniversalVideoTranslator\ffprobe.exe" >nul

echo EXE creato in dist\UniversalVideoTranslator\UniversalVideoTranslator.exe
pause
