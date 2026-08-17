@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "UVT_PYTHON_REL="
rem Preferisci il runtime applicativo verificato; .venv può essere un trampoline non avviabile.
if exist ".venv_app\Scripts\python.exe" set "UVT_PYTHON_REL=.venv_app\Scripts\python.exe"
if not defined UVT_PYTHON_REL if exist ".venv\Scripts\python.exe" set "UVT_PYTHON_REL=.venv\Scripts\python.exe"
if not defined UVT_PYTHON_REL (
  echo Esegui prima INSTALL_WINDOWS.bat
  if not "%UVT_NONINTERACTIVE%"=="1" pause
  exit /b 1
)

rem Il runtime Tcl/Tk non gestisce correttamente i percorsi Windows con spazi.
rem Usiamo una lettera temporanea libera per avviare Python con un percorso breve.
set "UVT_DRIVE="
for %%D in (Z Y X W V U T S R Q P) do if not defined UVT_DRIVE if not exist "%%D:\" set "UVT_DRIVE=%%D:"
if defined UVT_DRIVE (
  subst %UVT_DRIVE% "%~dp0" >nul 2>nul
  set "UVT_PYTHON=%UVT_DRIVE%\%UVT_PYTHON_REL%"
  if exist "%UVT_DRIVE%\.uv-managed-python\cpython-3.12.13-windows-x86_64-none\tcl\tcl8.6\init.tcl" set "TCL_LIBRARY=%UVT_DRIVE%\.uv-managed-python\cpython-3.12.13-windows-x86_64-none\tcl\tcl8.6"
  if exist "%UVT_DRIVE%\.uv-managed-python\cpython-3.12.13-windows-x86_64-none\tcl\tk8.6\tk.tcl" set "TK_LIBRARY=%UVT_DRIVE%\.uv-managed-python\cpython-3.12.13-windows-x86_64-none\tcl\tk8.6"
) else (
  set "UVT_PYTHON=%~dp0%UVT_PYTHON_REL%"
)

set "UVT_OLLAMA=ollama.exe"
where ollama.exe >nul 2>nul
if errorlevel 1 if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "UVT_OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%UVT_OLLAMA%" start "" /b "%UVT_OLLAMA%" serve >nul 2>nul
if "%UVT_OLLAMA%"=="ollama.exe" where ollama.exe >nul 2>nul && start "" /b ollama serve >nul 2>nul
if defined UVT_DRIVE (
  "%UVT_PYTHON%" "%UVT_DRIVE%\universal_video_translator.py"
) else (
  "%UVT_PYTHON%" "%~dp0universal_video_translator.py"
)
set "UVT_EXIT=%ERRORLEVEL%"
if defined UVT_DRIVE subst %UVT_DRIVE% /d >nul 2>nul
exit /b %UVT_EXIT%
