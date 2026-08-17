@echo on
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "UVT_ROOT=%~dp0"
if not defined UVT_APP_ROOT (
    if defined LOCALAPPDATA (
        set "UVT_APP_ROOT=%LOCALAPPDATA%\UniversalVideoTranslator"
    ) else (
        set "UVT_APP_ROOT=%TEMP%\UniversalVideoTranslator"
    )
)
set "UVT_TMP_INSTANCE_DIR=%UVT_APP_ROOT%\instance"
set "PYTHONPATH=%UVT_ROOT%src;%PYTHONPATH%"
set "PYTHONDONTWRITEBYTECODE=1"
set "UVT_EXE=%UVT_ROOT%\dist-browser-v0.2-release\UniversalVideoTranslator\UniversalVideoTranslator.exe"
set "UVT_CANDIDATE_LOG=%TEMP%\uvt_python_candidates.log"
set "UVT_APP_ARGS="
set "UVT_SOURCE_RC=1"

rd /s /q "%UVT_ROOT%__pycache%" >nul 2>nul
rd /s /q "%UVT_ROOT%src\__pycache%" >nul 2>nul
rd /s /q "%UVT_ROOT%src\uvt\__pycache%" >nul 2>nul

if not defined UVT_KILL_EXISTING set "UVT_KILL_EXISTING=1"
if /i "%UVT_KILL_EXISTING%"=="1" (
    taskkill /F /IM UniversalVideoTranslator.exe >nul 2>nul
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq UniversalVideoTranslator*" >nul 2>nul
)
if not defined UVT_FORCE_SOURCE set "UVT_FORCE_SOURCE=1"
if not defined UVT_NONINTERACTIVE set "UVT_NONINTERACTIVE=0"

set "UVT_MODE=SOURCE"
if /i "%UVT_FORCE_SOURCE%"=="0" set "UVT_MODE=EXE"
if not defined UVT_CLEAN_STALE set "UVT_CLEAN_STALE=1"

if /i "%UVT_CLEAN_STALE%"=="1" (
    call :is_uvt_running
    if errorlevel 1 (
        call :cleanup_stale
    )
)

echo %date% %time% | findstr "." >"%TEMP%\uvt_launch_args_debug.txt"
>>"%TEMP%\uvt_launch_args_debug.txt" echo Args=%*
>>"%TEMP%\uvt_launch_args_debug.txt" echo ForceSource=%UVT_FORCE_SOURCE%
echo MODALITA=%UVT_MODE% >>"%TEMP%\uvt_launch_mode_debug.txt"

if /i "%UVT_MODE%"=="EXE" (
    if exist "%UVT_EXE%" (
        echo Avvio tramite pacchetto: %UVT_EXE%
        "%UVT_EXE%"
        set "UVT_SOURCE_RC=%ERRORLEVEL%"
        if "%UVT_SOURCE_RC%"=="0" exit /b 0
        echo AVVIO_EXE_KO=%UVT_SOURCE_RC% >>"%UVT_CANDIDATE_LOG%"
        echo Modalità EXE non riuscita, provo fallback source...
    )
)

call :resolve_args "%~1"
call :choose_python
if defined UVT_PYTHON_REL_WITH_SOUNDCARD (
    set "UVT_PYTHON_REL=%UVT_PYTHON_REL_WITH_SOUNDCARD%"
)
if not defined UVT_PYTHON_REL (
    if exist "%UVT_EXE%" (
        echo Nessun Python compatibile trovato; utilizzo EXE.
        "%UVT_EXE%"
        exit /b %ERRORLEVEL%
    )
    echo Nessun Python compatibile con Tkinter e nessun EXE disponibile.
    echo Esegui INSTALL_WINDOWS.bat.
    if not "%UVT_NONINTERACTIVE%"=="1" pause
    exit /b 1
)

set "UVT_PYTHON=%UVT_PYTHON_REL%"
echo DEBUG_PY=%UVT_PYTHON%
>>"%UVT_CANDIDATE_LOG%" echo [DEBUG_PY=%UVT_PYTHON%]
if "%UVT_PYTHON%"=="" (
    if exist "%UVT_EXE%" (
        echo Nessun Python compatibile trovato; utilizzo EXE.
        "%UVT_EXE%"
        exit /b %ERRORLEVEL%
    )
    echo Nessun Python compatibile con Tkinter e nessun EXE disponibile.
    echo Esegui INSTALL_WINDOWS.bat.
    if not "%UVT_NONINTERACTIVE%"=="1" pause
    exit /b 1
)
for %%P in ("%UVT_PYTHON%") do if /I not "%%~xP"==".exe" if exist "%%~fP.exe" set "UVT_PYTHON=%%~fP.exe"
set "UVT_PYTHON=%UVT_PYTHON:"=%"

set "UVT_OLLAMA=ollama.exe"
where ollama.exe >nul 2>nul
if errorlevel 1 if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "UVT_OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%UVT_OLLAMA%" start "" /b "%UVT_OLLAMA%" serve >nul 2>nul

echo Python selezionato: %UVT_PYTHON%
>>"%UVT_CANDIDATE_LOG%" echo Python selezionato: %UVT_PYTHON%
>>"%UVT_CANDIDATE_LOG%" echo AppMode=%UVT_APP_MODE% Arg=%UVT_APP_ARGS%

echo %date% %time% | findstr "." >"%TEMP%\uvt_launch_args_debug.txt"
>>"%TEMP%\uvt_launch_args_debug.txt" echo AppMode=%UVT_APP_MODE% AppArgs=%UVT_APP_ARGS%

if defined UVT_APP_ARGS (
    "%UVT_PYTHON%" "%UVT_ROOT%\universal_video_translator.py" %UVT_APP_ARGS%
) else (
    "%UVT_PYTHON%" "%UVT_ROOT%\universal_video_translator.py"
)
set "UVT_SOURCE_RC=%ERRORLEVEL%"
if "%UVT_SOURCE_RC%"=="0" exit /b 0

if exist "%UVT_EXE%" (
    echo Avvio Python fallito (exit=%UVT_SOURCE_RC%), provo fallback EXE.
    "%UVT_EXE%"
    exit /b %ERRORLEVEL%
)
echo Avvio Python fallito (exit=%UVT_SOURCE_RC%).
if not "%UVT_NONINTERACTIVE%"=="1" pause
exit /b %UVT_SOURCE_RC%

:resolve_args
set "UVT_APP_ARGS="
set "UVT_APP_MODE="
if "%~1"=="" (
    exit /b 0
)
if /i "%~1"=="--native-messaging-host" (
    set "UVT_APP_MODE=native"
    set "UVT_APP_ARGS=--native-messaging-host"
    exit /b 0
)
if /i "%~1"=="--install-argos-models" (
    set "UVT_APP_MODE=argos"
    set "UVT_APP_ARGS=--install-argos-models"
    exit /b 0
)
set "UVT_APP_MODE=uri"
set "UVT_APP_ARGS=%~1"
if not "%UVT_NONINTERACTIVE%"=="1" echo Argomento pass-through: "%~1"
>>"%UVT_CANDIDATE_LOG%" echo Argomento pass-through: "%~1"
exit /b 0

:choose_python
> "%UVT_CANDIDATE_LOG%" echo [%date% %time%] Avvio controllo python per UVT
>>"%UVT_CANDIDATE_LOG%" echo Root: %UVT_ROOT%
set "UVT_PYTHON_REL="
set "UVT_PYTHON_REL_WITH_SOUNDCARD="

if defined UVT_PYTHON_EXE (
    set "UVT_PYTHON_EXE_TMP=!UVT_PYTHON_EXE!"
    set "UVT_PYTHON_EXE_TMP=!UVT_PYTHON_EXE_TMP:"=!"
    if not defined UVT_PYTHON_EXE_TMP goto :skip_override_python
    if not exist "!UVT_PYTHON_EXE_TMP!" goto :skip_override_python
    echo Override python rilevato: !UVT_PYTHON_EXE!
    echo [OV_RAW=!UVT_PYTHON_EXE!]
    for %%F in ("!UVT_PYTHON_EXE_TMP!") do set "UVT_PYTHON=%%~fF"
    if defined UVT_PYTHON_EXE_TMP set "UVT_PYTHON_EXE=!UVT_PYTHON_EXE_TMP!"
    set "UVT_PYTHON_EXE_TMP="
    echo [OV_SET=!UVT_PYTHON!]
    call :pcandidate "!UVT_PYTHON!"
    echo Override non valido: !UVT_PYTHON!
)
:skip_override_python

call :pcandidate "%UVT_ROOT%.venv_app\Scripts\python.exe"
call :pcandidate "%UVT_ROOT%.uv-managed-python\cpython-3.12.13-windows-x86_64-none\python.exe"
call :pcandidate "%UVT_ROOT%.venv\Scripts\python.exe"
call :pcandidate "%UVT_ROOT%.uv-python\cpython-3.12.13-windows-x86_64-none\python.exe"
call :pcandidate "C:\Users\Il Kazaro\AppData\Local\Programs\Python\Python310\python.exe"
call :pcandidate "C:\Program Files\Python310\python.exe"
exit /b 0

:pcandidate
if defined UVT_PYTHON_REL_WITH_SOUNDCARD exit /b 0
echo [CANDRAW=%~1]
set "UVT_CANDIDATE=%~1"
set "UVT_CANDIDATE=%UVT_CANDIDATE:\"=%"
if "%UVT_CANDIDATE%"=="" (
    >>"%UVT_CANDIDATE_LOG%" echo [MISS/EMPTY] %UVT_CANDIDATE%
    exit /b 0
)
for %%C in ("%UVT_CANDIDATE%") do if /I not "%%~xC"==".exe" if exist "%%~fC.exe" set "UVT_CANDIDATE=%%~fC.exe"
if not exist "%UVT_CANDIDATE%" (
    >>"%UVT_CANDIDATE_LOG%" echo [MISS] %UVT_CANDIDATE%
    exit /b 0
)
>>"%UVT_CANDIDATE_LOG%" echo Test candidato: %UVT_CANDIDATE%

set "UVT_PROBE_LOG=%UVT_CANDIDATE%.probe.log"
if exist "%UVT_PROBE_LOG%" del /f /q "%UVT_PROBE_LOG%" >nul 2>nul
"%UVT_CANDIDATE%" -c "import os;os.environ['UVT_BOOTSTRAP_TK_FIX']='1';import importlib;from uvt import bootstrap; bootstrap._configure_tk_paths();import tkinter as tk;root=tk.Tk();root.withdraw();root.destroy();importlib.import_module('uvt.app');importlib.import_module('uvt.gui');importlib.import_module('universal_video_translator');import importlib.util;print('UVT_READY');print('SOUNDCARD_READY='+str(importlib.util.find_spec('soundcard') is not None))" >"%UVT_PROBE_LOG%" 2>&1
if errorlevel 1 (
    >>"%UVT_CANDIDATE_LOG%" echo [KO] %UVT_CANDIDATE%
    >>"%UVT_CANDIDATE_LOG%" type "%UVT_PROBE_LOG%"
    if exist "%UVT_PROBE_LOG%" del /f /q "%UVT_PROBE_LOG%" >nul 2>nul
    exit /b 0
)

findstr /C:"UVT_READY" "%UVT_PROBE_LOG%" >nul && (
    >>"%UVT_CANDIDATE_LOG%" echo [OK] %UVT_CANDIDATE%
    if not defined UVT_PYTHON_REL (
        set "UVT_PYTHON_REL=%UVT_CANDIDATE%"
    )
    findstr /C:"SOUNDCARD_READY=True" "%UVT_PROBE_LOG%" >nul && (
        set "UVT_PYTHON_REL_WITH_SOUNDCARD=%UVT_CANDIDATE%"
        >>"%UVT_CANDIDATE_LOG%" echo [OK_SOUNDCARD] %UVT_CANDIDATE%
    ) || (
        >>"%UVT_CANDIDATE_LOG%" echo [OK_NO_SOUNDCARD] %UVT_CANDIDATE%
    )
) || (
    >>"%UVT_CANDIDATE_LOG%" echo [KO:UI] %UVT_CANDIDATE%
    >>"%UVT_CANDIDATE_LOG%" type "%UVT_PROBE_LOG%"
)
if exist "%UVT_PROBE_LOG%" del /f /q "%UVT_PROBE_LOG%" >nul 2>nul
exit /b 0

:cleanup_stale
if exist "%UVT_TMP_INSTANCE_DIR%" (
    del /f /q "%UVT_TMP_INSTANCE_DIR%\ipc-*.json" >nul 2>nul
    rmdir /s /q "%UVT_TMP_INSTANCE_DIR%" >nul 2>nul
)
if exist "%UVT_TMP_INSTANCE_DIR%\instance-owner.lock" del /f /q "%UVT_TMP_INSTANCE_DIR%\instance-owner.lock" >nul 2>nul

powershell -NoProfile -NoLogo -Command "$root=[string]$env:UVT_ROOT; if([string]::IsNullOrWhiteSpace($root)){exit 0}; $root=$root.TrimEnd('\\'); $proc=Get-Process -Name python,pythonw,python3,UniversalVideoTranslator -ErrorAction SilentlyContinue; if(-not $proc){exit 0}; $target=$proc | Where-Object { $_.Path -like \"$root\\*\" -or $_.CommandLine -like \"*$root*universal_video_translator.py*\" }; $target | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }"
if exist "%UVT_TMP_INSTANCE_DIR%" (
    del /f /q "%UVT_TMP_INSTANCE_DIR%\ipc-v*.json" >nul 2>nul
)
if /i "%UVT_NONINTERACTIVE%"=="0" (
    echo Pulizia stato precedente completata.
) else (
    timeout /T 1 >nul
)
exit /b 0

:is_uvt_running
powershell -NoProfile -NoLogo -Command "$p=Get-Process -Name python,pythonw,python3,UniversalVideoTranslator -ErrorAction SilentlyContinue | Where-Object { $_.Path -like (Join-Path $env:UVT_ROOT '*') -or $_.CommandLine -like \"*$env:UVT_ROOT*universal_video_translator.py*\" }; if($p){ exit 0 } else { exit 1 }"
if %ERRORLEVEL%==0 exit /b 0
exit /b 1
