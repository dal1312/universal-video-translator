from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SOUND_VOLUME_VIEW_SHA256 = (
    "b5af5bd60f7a29af8cb4d8a566382b90f0fe07cac97228d218cb913f3382d647"
)


class PreflightError(RuntimeError):
    pass


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise PreflightError(message)
    _ok(message)


def _command(name: str) -> Path:
    resolved = shutil.which(name)
    if not resolved and name == "deno":
        candidate = Path.home() / ".deno" / "bin" / "deno.exe"
        if candidate.is_file():
            resolved = str(candidate)
    if not resolved:
        raise PreflightError(f"Comando richiesto non trovato: {name}")
    path = Path(resolved).resolve()
    _ok(f"{name}: {path}")
    return path


def _run(command: list[str], description: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise PreflightError(f"{description} non riuscito (codice {result.returncode}).")
    _ok(description)
    return result


def _import_modules(names: tuple[str, ...]) -> None:
    for name in names:
        importlib.import_module(name)
        _ok(f"Import Python: {name}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_versions() -> None:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

    from uvt import __version__

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "browser_extension" / "manifest.json").read_text(encoding="utf-8")
    )
    versions = {
        str(project["project"]["version"]),
        str(manifest["version"]),
        str(__version__),
    }
    _check(len(versions) == 1, "Versione coerente tra progetto, package ed estensione")


def _check_python() -> None:
    _check(sys.version_info[:2] == (3, 10), "Python 3.10 per i vincoli Windows")
    _check(platform.architecture()[0] == "64bit", "Python Windows x64")
    _check(sys.prefix != sys.base_prefix, "Ambiente virtuale attivo")
    _run([sys.executable, "-m", "pip", "check"], "Integrita dipendenze pip")


def _check_vendor_files() -> None:
    vendor = ROOT / "third_party" / "SoundVolumeView"
    executable = vendor / "SoundVolumeView.exe"
    for name in ("SoundVolumeView.exe", "SoundVolumeView.chm", "readme.txt"):
        _check((vendor / name).is_file(), f"Risorsa SoundVolumeView: {name}")
    _check(
        _sha256(executable) == SOUND_VOLUME_VIEW_SHA256,
        "Integrita SoundVolumeView 2.53",
    )
    _check(
        (ROOT / "browser_extension" / "service-worker.js").is_file(),
        "Estensione browser inclusa",
    )


def _check_python_resources() -> None:
    import espeakng_loader
    import language_tags

    espeak_data = Path(espeakng_loader.get_data_path())
    _check(espeak_data.is_dir(), "Dati eSpeak NG disponibili")
    package_root = Path(language_tags.__file__).resolve().parent
    _check(
        (package_root / "data" / "json" / "index.json").is_file(),
        "Dati language-tags disponibili",
    )


def _check_external_tools(*, require_model: bool, require_cable: bool) -> None:
    media_tools = tuple(_command(name) for name in ("ffmpeg", "ffprobe", "ffplay"))
    _check(
        len({path.parent for path in media_tools}) == 1,
        "FFmpeg, ffprobe e ffplay provengono dalla stessa distribuzione",
    )
    _command("deno")
    ollama = _command("ollama")
    if require_model:
        result = _run([str(ollama), "list"], "Connessione Ollama")
        models = {line.split()[0].lower() for line in result.stdout.splitlines() if line.strip()}
        _check(
            "translategemma:latest" in models,
            "Modello Ollama translategemma:latest installato",
        )
    if require_cable:
        from uvt.live import capture_device_names, preferred_cable_output

        _check(
            preferred_cable_output(capture_device_names()) is not None,
            "VB-Cable rilevato come CABLE Output",
        )


def run(profile: str, *, skip_model: bool, skip_cable: bool) -> None:
    os.chdir(ROOT)
    _check_python()
    _check_versions()
    _import_modules(("requests", "pyttsx3", "langdetect"))
    if profile in {"full", "build"}:
        _import_modules(
            (
                "faster_whisper",
                "soundcard",
                "kokoro",
                "soundfile",
                "yt_dlp",
                "espeakng_loader",
                "language_tags",
            )
        )
        _check_python_resources()
        _check_vendor_files()
        _check_external_tools(
            require_model=profile == "full" and not skip_model,
            require_cable=profile == "full" and not skip_cable,
        )
    if profile == "build":
        _import_modules(("PyInstaller",))


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight Windows UVT")
    parser.add_argument("--profile", choices=("source", "full", "build"), default="full")
    parser.add_argument("--skip-model", action="store_true")
    parser.add_argument("--skip-cable", action="store_true")
    args = parser.parse_args()
    try:
        run(args.profile, skip_model=args.skip_model, skip_cable=args.skip_cable)
    except (PreflightError, ImportError, OSError, subprocess.SubprocessError) as error:
        print(f"[ERRORE] {error}", file=sys.stderr)
        return 1
    print("PREFLIGHT COMPLETATO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
