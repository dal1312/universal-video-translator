[CmdletBinding()]
param(
    [switch]$Argos,
    [switch]$Piper,
    [switch]$AcceptPiperGPL,
    [switch]$AcceptModelLicenses
)

$ErrorActionPreference = 'Stop'
$Root = if ((Split-Path $PSScriptRoot -Leaf) -eq 'windows') {
    (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}
else {
    $PSScriptRoot
}
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$PackagedApp = Join-Path $Root 'UniversalVideoTranslator.exe'
$DataRoot = Join-Path $env:LOCALAPPDATA 'UniversalVideoTranslator'

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Comando non riuscito: $Executable $($Arguments -join ' ')"
    }
}

try {
    Set-Location $Root
    if (-not $Argos -and -not $Piper) {
        $Argos = $true
        $Piper = $true
    }
    if (($Argos -or $Piper) -and -not $AcceptModelLicenses) {
        throw 'Leggi i MODEL_CARD delle risorse e ripeti con -AcceptModelLicenses.'
    }
    if ($Argos) {
        if (Test-Path -LiteralPath $Python -PathType Leaf) {
            $Constraints = Join-Path $Root (
                'requirements\windows-py310-x64.constraints.txt'
            )
            $InstallArguments = @('-m', 'pip', 'install')
            if (Test-Path -LiteralPath $Constraints -PathType Leaf) {
                $InstallArguments += @('-c', $Constraints)
            }
            $InstallArguments += 'argostranslate==1.11.0'
            Invoke-Checked $Python $InstallArguments
            Invoke-Checked $Python @(
                'scripts\windows\install_optional_engines.py', '--argos'
            )
        }
        elseif (Test-Path -LiteralPath $PackagedApp -PathType Leaf) {
            Invoke-Checked $PackagedApp @('--install-argos-models')
        }
        else {
            throw 'Runtime UVT non trovato: manca .venv o UniversalVideoTranslator.exe.'
        }
    }
    if ($Piper) {
        if (-not $AcceptPiperGPL) {
            throw 'Piper è GPL-3.0-or-later. Ripeti con -AcceptPiperGPL.'
        }
        $PiperRoot = Join-Path $DataRoot 'engines\piper'
        $PiperVenv = Join-Path $PiperRoot '.venv'
        $PiperPython = Join-Path $PiperVenv 'Scripts\python.exe'
        $VoiceDirectory = Join-Path $DataRoot 'voices\piper'
        New-Item -ItemType Directory -Path $PiperRoot, $VoiceDirectory -Force |
            Out-Null
        if (-not (Test-Path -LiteralPath $PiperPython -PathType Leaf)) {
            if (Test-Path -LiteralPath $Python -PathType Leaf) {
                $BootstrapPython = $Python
                $BootstrapPrefix = @()
            }
            else {
                $Launcher = Get-Command py.exe -ErrorAction Stop
                $BootstrapPython = $Launcher.Source
                $BootstrapPrefix = @('-3.10')
            }
            $VenvArguments = $BootstrapPrefix + @('-m', 'venv', $PiperVenv)
            Invoke-Checked $BootstrapPython $VenvArguments
        }
        Invoke-Checked $PiperPython @(
            '-m', 'pip', 'install', '--upgrade', 'pip', 'piper-tts==1.5.0'
        )
        Invoke-Checked $PiperPython @(
            '-m', 'piper.download_voices',
            '--data-dir', $VoiceDirectory,
            'it_IT-paola-medium',
            'it_IT-riccardo-x_low'
        )
    }
    Write-Host 'MOTORI OPZIONALI INSTALLATI' -ForegroundColor Green
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
