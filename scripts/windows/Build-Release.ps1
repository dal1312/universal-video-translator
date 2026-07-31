[CmdletBinding()]
param(
    [string]$PythonPath = '.venv\Scripts\python.exe',
    [string]$FFmpegDirectory,
    [string]$DistDirectory = 'dist-browser-v0.2-release',
    [string]$WorkDirectory = 'build-browser-v0.2-release',
    [string]$ReleaseDirectory = 'release',
    [switch]$SkipTests,
    [switch]$KeepWork,
    [switch]$AllowDirty,
    [switch]$Sign,
    [string]$CertificateThumbprint
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

function Resolve-RootedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    if ([IO.Path]::IsPathRooted($Path)) { return $Path }
    return Join-Path $Root $Path
}

function Invoke-CheckedPython {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Comando Python non riuscito: $($Arguments -join ' ')"
    }
}

function Require-File {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "File richiesto non trovato: $Path"
    }
}

try {
    Set-Location $Root
    $Python = Resolve-RootedPath $PythonPath
    Require-File $Python
    $Dist = Resolve-RootedPath $DistDirectory
    $Work = Resolve-RootedPath $WorkDirectory
    $Release = Resolve-RootedPath $ReleaseDirectory
    $Version = (& $Python -c "import sys;sys.path.insert(0,'src');import uvt;print(uvt.__version__)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Version) { throw 'Versione applicazione non disponibile.' }

    if (-not $AllowDirty) {
        $Dirty = & git status --porcelain
        if ($LASTEXITCODE -ne 0 -or $Dirty) { throw 'La release ufficiale richiede un worktree Git pulito.' }
        $Tag = (& git tag --points-at HEAD).Trim()
        if (($Tag -split '\s+') -notcontains "v$Version") {
            throw "HEAD deve avere il tag v$Version."
        }
    }

    $env:PYTHONHASHSEED = '0'
    $env:SOURCE_DATE_EPOCH = (& git show -s --format=%ct HEAD).Trim()
    Invoke-CheckedPython @('scripts\windows\preflight.py', '--profile', 'build')
    if (-not $SkipTests) {
        Invoke-CheckedPython @('-m', 'compileall', '-q', 'src', 'universal_video_translator.py', 'tests')
        Invoke-CheckedPython @('-m', 'pytest', '-q')
    }

    foreach ($Directory in @($Dist, $Work)) {
        if (Test-Path -LiteralPath $Directory) {
            Remove-Item -LiteralPath $Directory -Recurse -Force
        }
    }
    Invoke-CheckedPython @(
        '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--distpath', $Dist, '--workpath', $Work,
        'UniversalVideoTranslator.spec'
    )

    $AppDirectory = Join-Path $Dist 'UniversalVideoTranslator'
    Require-File (Join-Path $AppDirectory 'UniversalVideoTranslator.exe')
    if ($FFmpegDirectory) {
        $MediaDirectory = (Resolve-Path -LiteralPath $FFmpegDirectory).Path
    }
    else {
        $MediaDirectory = Split-Path -Parent (Get-Command ffmpeg -ErrorAction Stop).Source
    }
    foreach ($Tool in @('ffmpeg.exe', 'ffprobe.exe', 'ffplay.exe')) {
        $Source = Join-Path $MediaDirectory $Tool
        Require-File $Source
        Copy-Item -LiteralPath $Source -Destination (Join-Path $AppDirectory $Tool) -Force
    }
    $FFmpegLicense = Join-Path (Split-Path -Parent $MediaDirectory) 'LICENSE'
    Require-File $FFmpegLicense
    $Licenses = Join-Path $AppDirectory 'licenses'
    New-Item -ItemType Directory -Path $Licenses -Force | Out-Null
    Copy-Item -LiteralPath $FFmpegLicense -Destination (Join-Path $Licenses 'FFmpeg-LICENSE.txt') -Force

    foreach ($Required in @(
        'ffmpeg.exe',
        'ffprobe.exe',
        'ffplay.exe',
        '_internal\browser_extension\manifest.json',
        '_internal\third_party\SoundVolumeView\SoundVolumeView.exe',
        '_internal\third_party\SoundVolumeView\readme.txt',
        '_internal\language_tags\data\json\index.json'
    )) {
        Require-File (Join-Path $AppDirectory $Required)
    }
    if (-not (Test-Path -LiteralPath (Join-Path $AppDirectory '_internal\espeakng_loader\espeak-ng-data') -PathType Container)) {
        throw 'Dati eSpeak NG mancanti dalla build.'
    }

    if ($Sign) {
        if (-not $CertificateThumbprint) { throw 'Specificare -CertificateThumbprint quando si usa -Sign.' }
        $SignTool = (Get-Command signtool.exe -ErrorAction Stop).Source
        $Application = Join-Path $AppDirectory 'UniversalVideoTranslator.exe'
        & $SignTool sign /sha1 $CertificateThumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Application
        if ($LASTEXITCODE -ne 0) { throw 'Firma Authenticode non riuscita.' }
        & $SignTool verify /pa $Application
        if ($LASTEXITCODE -ne 0) { throw 'Verifica firma Authenticode non riuscita.' }
    }

    Invoke-CheckedPython @(
        'scripts\package_release.py',
        '--source', $AppDirectory,
        '--output', $Release,
        '--repo', $Root,
        '--version', $Version
    )
    $ArtifactName = "UniversalVideoTranslator-$Version-windows-x86_64"
    $Payload = Join-Path $Release $ArtifactName
    $Zip = Join-Path $Release "$ArtifactName.zip"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'VERIFY_RELEASE_WINDOWS.ps1') -ReleaseDirectory $Payload -ZipPath $Zip
    if ($LASTEXITCODE -ne 0) { throw 'Verifica checksum release non riuscita.' }

    if (-not $KeepWork -and (Test-Path -LiteralPath $Work)) {
        Remove-Item -LiteralPath $Work -Recurse -Force
    }
    Write-Host ''
    Write-Host "RELEASE COMPLETATA: $Zip" -ForegroundColor Green
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
