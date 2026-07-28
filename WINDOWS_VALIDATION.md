# Windows Validation

Date: 2026-07-28  
Status: **PASS — EXE BUILT AND LAUNCHED**

## Environment

- Windows 10
- Python 3.10.6
- FFmpeg: available in PATH
- Ollama: available
- Translation model: `qwen3:4b`

## Results

```text
.......... [100%]
10 passed in 0.08s
```

The source code, automated tests, FFmpeg installation, Ollama installation and required model passed `VERIFICA_WINDOWS.bat`.

## Executable

- PyInstaller build: PASS
- Output: `dist\UniversalVideoTranslator.exe`
- Application launch on Windows: PASS

## Functional validation

- SRT functional test: PASS
- Ollama model: `translategemma:latest`
- English-to-Italian output: PASS
- Windows text-to-speech: PASS
- Confirmed output:
  - Benvenuti in Universal Video Translator.
  - Questa frase sarà tradotta e pronunciata in italiano.
  - Il prototipo locale funziona.

## Kokoro voice validation

- Kokoro environment: PASS
- eSpeak NG: PASS
- Italian voice `if_sara` (Sara): PASS
- Italian voice `im_nicola` (Nicola): PASS
- Translation and speech pipeline: PASS
- Automated tests: 13 passed

## Packaged application validation

- PyInstaller onedir build: PASS
- Bundled `language_tags` data: PASS
- Bundled `espeakng_loader` data: PASS
- Packaged onedir executable with Kokoro: PASS
- Executable: `dist\UniversalVideoTranslator\UniversalVideoTranslator.exe`
