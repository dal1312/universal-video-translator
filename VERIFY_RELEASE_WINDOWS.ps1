[CmdletBinding()]
param(
    [string]$ReleaseDirectory = $PSScriptRoot,
    [string]$ZipPath
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath $ReleaseDirectory).Path
$Manifest = Join-Path $Root 'SHA256SUMS.txt'
if (-not (Test-Path -LiteralPath $Manifest)) {
    throw 'SHA256SUMS.txt non trovato.'
}

foreach ($Line in Get-Content -LiteralPath $Manifest) {
    if ($Line -notmatch '^([0-9a-fA-F]{64})  (.+)$') {
        throw "Riga checksum non valida: $Line"
    }
    $Expected = $Matches[1].ToUpperInvariant()
    $Relative = $Matches[2].Replace('/', [IO.Path]::DirectorySeparatorChar)
    $File = Join-Path $Root $Relative
    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) {
        throw "File mancante: $Relative"
    }
    $Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $File).Hash
    if ($Actual -ne $Expected) {
        throw "Checksum non valido: $Relative"
    }
}

if ($ZipPath) {
    $ResolvedZip = (Resolve-Path -LiteralPath $ZipPath).Path
    $Sidecar = "$ResolvedZip.sha256"
    if (-not (Test-Path -LiteralPath $Sidecar)) {
        throw "Checksum ZIP non trovato: $Sidecar"
    }
    $ExpectedZip = ((Get-Content -LiteralPath $Sidecar -Raw) -split '\s+')[0].ToUpperInvariant()
    $ActualZip = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResolvedZip).Hash
    if ($ActualZip -ne $ExpectedZip) {
        throw 'Checksum ZIP non valido.'
    }
}

Write-Host 'VERIFICA RELEASE COMPLETATA' -ForegroundColor Green
