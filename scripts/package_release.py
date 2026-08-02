from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path


PAYLOAD_DOCUMENTS = (
    "README.md",
    "README.en.md",
    "CHANGELOG.md",
    "CHANGELOG.en.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "WINDOWS_BENCHMARK.json",
    "INSTALLA_MOTORI_OPZIONALI_WINDOWS.bat",
    "VERIFY_RELEASE_WINDOWS.ps1",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def copy_payload(source: Path, target: Path, repo: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    for name in PAYLOAD_DOCUMENTS:
        path = repo / name
        if not path.is_file():
            raise FileNotFoundError(f"Release document missing: {name}")
        shutil.copy2(path, target / name)
    shutil.copy2(
        repo / "scripts" / "windows" / "Install-Optional-Engines.ps1",
        target / "INSTALLA_MOTORI_OPZIONALI_WINDOWS.ps1",
    )
    licenses = target / "licenses"
    licenses.mkdir(exist_ok=True)
    shutil.copy2(
        repo / "third_party" / "SoundVolumeView" / "readme.txt",
        licenses / "SoundVolumeView-readme.txt",
    )
    constraints = repo / "requirements" / "windows-py310-x64.constraints.txt"
    shutil.copy2(constraints, licenses / "Windows-build-constraints.txt")
    if not (licenses / "FFmpeg-LICENSE.txt").is_file():
        raise FileNotFoundError("FFmpeg-LICENSE.txt was not staged by the build.")


def provenance(repo: Path, target: Path, version: str, epoch: int) -> dict:
    inputs = {
        "UniversalVideoTranslator.spec": sha256(repo / "UniversalVideoTranslator.spec"),
        "constraints": sha256(
            repo / "requirements" / "windows-py310-x64.constraints.txt"
        ),
        "third_party_manifest": sha256(repo / "third_party" / "manifest.json"),
    }
    bundled = {}
    for relative in (
        "UniversalVideoTranslator.exe",
        "ffmpeg.exe",
        "ffprobe.exe",
        "ffplay.exe",
        "_internal/third_party/SoundVolumeView/SoundVolumeView.exe",
    ):
        path = target / Path(relative)
        if not path.is_file():
            raise FileNotFoundError(f"Required release file missing: {relative}")
        bundled[relative] = sha256(path)
    try:
        pyinstaller_version = importlib.metadata.version("pyinstaller")
    except importlib.metadata.PackageNotFoundError:
        pyinstaller_version = "unknown"
    return {
        "schema_version": 1,
        "application": "Universal Video Translator",
        "version": version,
        "platform": "windows-x86_64",
        "source": {
            "commit": git_value(repo, "rev-parse", "HEAD"),
            "dirty": bool(git_value(repo, "status", "--porcelain")),
            "source_date_epoch": epoch,
        },
        "toolchain": {
            "python": platform_python(),
            "pyinstaller": pyinstaller_version,
        },
        "inputs_sha256": inputs,
        "bundled_sha256": bundled,
        "external_runtime": [
            "Ollama",
            "translategemma:latest",
            "Deno for YouTube",
            "VB-Cable for automatic browser Overlay",
        ],
    }


def platform_python() -> str:
    return ".".join(str(part) for part in sys.version_info[:3])


def write_checksums(target: Path) -> None:
    checksum_file = target / "SHA256SUMS.txt"
    lines = []
    for path in sorted(item for item in target.rglob("*") if item.is_file()):
        if path == checksum_file:
            continue
        relative = path.relative_to(target).as_posix()
        lines.append(f"{sha256(path)}  {relative}")
    checksum_file.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def deterministic_zip(source: Path, destination: Path, epoch: int) -> None:
    if destination.exists():
        destination.unlink()
    timestamp = list(time.gmtime(max(epoch, 315532800))[:6])
    timestamp[5] -= timestamp[5] % 2
    root_name = source.name
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = Path(root_name) / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=tuple(timestamp))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            with path.open("rb") as handle, archive.open(info, "w", force_zip64=True) as out:
                shutil.copyfileobj(handle, out, length=1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create deterministic UVT Windows ZIP")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    repo = args.repo.resolve()
    if not (source / "UniversalVideoTranslator.exe").is_file():
        raise FileNotFoundError("UniversalVideoTranslator.exe not found in source")
    output.mkdir(parents=True, exist_ok=True)
    artifact_name = f"UniversalVideoTranslator-{args.version}-windows-x86_64"
    target = output / artifact_name
    copy_payload(source, target, repo)
    epoch_text = os.environ.get("SOURCE_DATE_EPOCH") or git_value(
        repo, "show", "-s", "--format=%ct", "HEAD"
    )
    epoch = int(epoch_text) if str(epoch_text).isdigit() else 315532800
    (target / "PROVENANCE.json").write_text(
        json.dumps(provenance(repo, target, args.version, epoch), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_checksums(target)
    if not args.stage_only:
        zip_path = output / f"{artifact_name}.zip"
        deterministic_zip(target, zip_path, epoch)
        (output / f"{artifact_name}.zip.sha256").write_text(
            f"{sha256(zip_path)}  {zip_path.name}\n",
            encoding="utf-8",
            newline="\n",
        )
        print(zip_path)
    else:
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
