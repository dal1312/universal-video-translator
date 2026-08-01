# Windows Validation

Date: 2026-08-02
Version: **0.2.1**
Status: **PASS - SOURCE, FULL PREFLIGHT, GUI SMOKE, PACKAGE, CHECKSUM, AND SINGLE INSTANCE**

## Environment

- Windows 11 build 26200 (reported by Python as `Windows-10-10.0.26200-SP0`)
- Python 3.10.6 x64
- PyInstaller 6.21.0
- FFmpeg 8.1.2 full build, including `ffmpeg`, `ffprobe`, and `ffplay`
- Deno available
- Ollama available and responding
- Translation model `translategemma:latest` installed
- VB-Cable detected as `CABLE Output`
- SoundVolumeView 2.53 package and SHA256 verified

## Automated Verification

```text
187 passed in 8.65s
```

Additional checks:

- Python `compileall`: PASS
- browser extension JavaScript syntax (`node --check`): PASS
- PowerShell 5.1 parser validation: PASS
- `git diff --check`: PASS, excluding expected line-ending notices
- source/full/build preflight: PASS
- source GUI smoke (`scripts/windows/smoke_gui.py`): PASS
- contextual settings open/close and deterministic GUI shutdown: PASS
- parallel Ollama, Whisper, and speech warm-up tests: PASS
- media export controller and progressive worker ownership tests: PASS
- controlled local benchmark (`WINDOWS_BENCHMARK.json`): PASS
- project, Python package, and extension version agreement: PASS
- deterministic package metadata tests: PASS

The full preflight validated Python dependencies, eSpeak NG data, language-tags data, SoundVolumeView integrity, the browser extension, all FFmpeg tools from one distribution, Deno, Ollama, the default model, and VB-Cable.

## Controlled Local Benchmark

- Whisper `base` word error rate: `0.000`
- Ollama warm-up: `1.095 s`
- translation median: `1.800 s`
- translation worst case: `2.221 s`
- multilingual keyword fidelity: `1.000`
- Kokoro generation realtime factor: `0.443`

This benchmark exercises the real local Whisper, `translategemma:latest`, and
Kokoro engines. Browser end-to-end latency additionally depends on capture,
VAD, natural speech pauses, and live queues.

## Packaged Application

- PyInstaller onedir build: PASS
- Windows version metadata: PASS
- UPX disabled: PASS
- bundled browser extension: PASS
- bundled SoundVolumeView package and notice: PASS
- bundled language-tags data: PASS
- bundled eSpeak NG data: PASS
- bundled FFmpeg trio and license: PASS
- EXE launch: PASS
- main window responding: PASS
- second EXE launch forwarded to the existing instance: PASS
- processes after first launch: `1`
- processes after second launch: `1`
- processes after test shutdown: `0`

Executable:

```text
dist-browser-v0.2-release\UniversalVideoTranslator\UniversalVideoTranslator.exe
```

Executable size: `50,490,570` bytes
Executable SHA256:

```text
3E84FBAD8F7243D239BED7CF319C48216675731BE39C5742CA4038C89237909B
```

## Portable Release

Artifact:

```text
release\UniversalVideoTranslator-0.2.1-windows-x86_64.zip
```

ZIP size: `600,463,218` bytes
ZIP SHA256:

```text
2721EC10E06F1FF7AFB24C538B52E72655A27CD9F2C33AB0A80178068125E67D
```

Payload contents:

- 18,380 files
- 1,732,435,286 unpacked bytes
- Italian and English README/changelog
- Apache 2.0 project license
- third-party notices and FFmpeg/SoundVolumeView license material
- deterministic `PROVENANCE.json`
- sorted per-file `SHA256SUMS.txt`
- `VERIFY_RELEASE_WINDOWS.ps1`
- external ZIP checksum sidecar

`VERIFY_RELEASE_WINDOWS.ps1` validated every payload hash and the ZIP sidecar successfully.

## Release Qualification Note

This validation artifact was generated from commit `afe87234bd3310d0b46fa677639786297320034e` with the current improvements still present as uncommitted worktree changes. `PROVENANCE.json` therefore correctly records `dirty: true`.

The artifact is suitable for local acceptance testing. The standard release command now rejects dirty or untagged source by default. A local acceptance build must opt in with `Build-Release.ps1 -AllowDirty`; optional Authenticode signing can be enabled explicitly for the final clean/tagged build.
