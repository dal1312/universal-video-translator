[CmdletBinding()]
param(
    [switch]$PullModel
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$Constraints = Join-Path $Root 'requirements\windows-py310-x64.constraints.txt'

function Invoke-CheckedPython {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $VenvPython @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Comando Python non riuscito: $($Arguments -join ' ')"
    }
}

try {
    Set-Location $Root
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        $SystemPython = (Get-Command python -ErrorAction Stop).Source
        & $SystemPython -c "import platform,sys; assert sys.version_info[:2] == (3,10); assert platform.architecture()[0] == '64bit'"
        if ($LASTEXITCODE -ne 0) {
            throw 'Questa serie di vincoli richiede Python x64 3.10.'
        }
        & $SystemPython -m venv (Join-Path $Root '.venv')
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) {
            throw 'Creazione ambiente virtuale non riuscita.'
        }
    }

    & $VenvPython -c "import platform,sys; assert sys.version_info[:2] == (3,10); assert platform.architecture()[0] == '64bit'"
    if ($LASTEXITCODE -ne 0) {
        throw 'La .venv esistente non usa Python x64 3.10. Rimuovila e ripeti l installazione.'
    }

    Invoke-CheckedPython @('-m', 'pip', 'install', '--upgrade', 'pip==26.1.2', 'setuptools==83.0.0')
    Invoke-CheckedPython @(
        '-m', 'pip', 'install',
        '-c', $Constraints,
        '-e', '.[all,dev]',
        'pyinstaller==6.21.0'
    )
    Invoke-CheckedPython @('-m', 'pip', 'check')
    Invoke-CheckedPython @('scripts\windows\preflight.py', '--profile', 'source')

    if ($PullModel) {
        $Ollama = (Get-Command ollama -ErrorAction Stop).Source
        & $Ollama pull translategemma:latest
        if ($LASTEXITCODE -ne 0) {
            throw 'Download del modello translategemma:latest non riuscito.'
        }
    }

    Write-Host ''
    Write-Host 'Installazione Python completata.' -ForegroundColor Green
    if (-not $PullModel) {
        Write-Host 'Modello non scaricato. Usa INSTALL_WINDOWS.bat -PullModel oppure: ollama pull translategemma:latest'
    }
    Write-Host 'Esegui VERIFICA_WINDOWS.bat per controllare FFmpeg, Deno, Ollama, VB-Cable e tutte le funzioni.'
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
