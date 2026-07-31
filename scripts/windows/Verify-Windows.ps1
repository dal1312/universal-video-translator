[CmdletBinding()]
param(
    [switch]$SkipModel,
    [switch]$SkipCable
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'

function Invoke-CheckedPython {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Verifica non riuscita: $($Arguments -join ' ')"
    }
}

try {
    Set-Location $Root
    if (-not (Test-Path -LiteralPath $Python)) {
        throw 'Ambiente virtuale assente. Esegui prima INSTALL_WINDOWS.bat.'
    }
    Invoke-CheckedPython @('-m', 'compileall', '-q', 'src', 'universal_video_translator.py', 'tests')
    Invoke-CheckedPython @('-m', 'pytest', '-q')
    $Preflight = @('scripts\windows\preflight.py', '--profile', 'full')
    if ($SkipModel) { $Preflight += '--skip-model' }
    if ($SkipCable) { $Preflight += '--skip-cable' }
    Invoke-CheckedPython $Preflight
    Write-Host ''
    Write-Host 'VERIFICA COMPLETATA:  test, dipendenze e componenti Windows disponibili.' -ForegroundColor Green
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
