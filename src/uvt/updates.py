from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .paths import app_paths


RELEASE_API = "https://api.github.com/repos/dal1312/universal-video-translator/releases/latest"
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True, slots=True)
class UpdateResult:
    status: str
    version: str | None = None
    message: str = ""


def is_newer(candidate: str, current: str) -> bool:
    left = _VERSION.fullmatch(candidate.strip())
    right = _VERSION.fullmatch(current.strip())
    if not left or not right:
        return False
    return tuple(map(int, left.groups())) > tuple(map(int, right.groups()))


class AutomaticUpdater:
    def __init__(self, current_version: str, *, session=None) -> None:
        self.current_version = current_version
        self.session = session or requests.Session()
        self.root = app_paths().updates

    def check_and_stage(self) -> UpdateResult:
        response = self.session.get(
            RELEASE_API,
            headers={"Accept": "application/vnd.github+json"},
            timeout=8,
        )
        response.raise_for_status()
        release = response.json()
        version = str(release.get("tag_name", "")).removeprefix("v")
        if not is_newer(version, self.current_version):
            return UpdateResult("current", self.current_version, "Versione aggiornata")
        if not getattr(sys, "frozen", False):
            return UpdateResult(
                "available", version, f"Aggiornamento {version} disponibile"
            )
        assets = {
            str(item.get("name")): str(item.get("browser_download_url"))
            for item in release.get("assets", [])
            if isinstance(item, dict)
        }
        archive_name = f"UniversalVideoTranslator-{version}-windows-x86_64.zip"
        checksum_name = f"{archive_name}.sha256"
        if not assets.get(archive_name) or not assets.get(checksum_name):
            return UpdateResult("unavailable", version, "Pacchetto firmato non disponibile")
        _require_https(assets[archive_name])
        _require_https(assets[checksum_name])
        self.root.mkdir(parents=True, exist_ok=True)
        archive = self.root / archive_name
        expected = self._download_text(assets[checksum_name]).split()[0].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Checksum aggiornamento non valido")
        self._download_file(assets[archive_name], archive)
        if _sha256(archive) != expected:
            archive.unlink(missing_ok=True)
            raise ValueError("Checksum aggiornamento non corrispondente")
        stage = self.root / f"stage-{version}"
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir()
        _safe_extract(archive, stage)
        payload = stage / f"UniversalVideoTranslator-{version}-windows-x86_64"
        executable = payload / "UniversalVideoTranslator.exe"
        if not executable.is_file():
            raise ValueError("Eseguibile mancante nel pacchetto di aggiornamento")
        if os.name == "nt" and not _signatures_match(
            executable, Path(sys.executable)
        ):
            shutil.rmtree(stage, ignore_errors=True)
            raise ValueError("Firma digitale dell'aggiornamento non valida")
        pending = {
            "version": version,
            "payload": str(payload.resolve()),
            "target": str(Path(sys.executable).resolve().parent),
        }
        (self.root / "pending.json").write_text(
            json.dumps(pending, indent=2) + "\n", encoding="utf-8"
        )
        return UpdateResult("staged", version, f"Aggiornamento {version} pronto")

    def _download_text(self, url: str) -> str:
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        return response.text[:4096]

    def _download_file(self, url: str, destination: Path) -> None:
        with self.session.get(url, timeout=60, stream=True) as response:
            response.raise_for_status()
            content_length = int(response.headers.get("Content-Length", "0") or 0)
            if content_length > 2 * 1024 * 1024 * 1024:
                raise ValueError("Pacchetto di aggiornamento troppo grande")
            downloaded = 0
            with destination.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        downloaded += len(chunk)
                        if downloaded > 2 * 1024 * 1024 * 1024:
                            raise ValueError("Pacchetto di aggiornamento troppo grande")
                        handle.write(chunk)


def launch_pending_update() -> bool:
    if not getattr(sys, "frozen", False) or os.name != "nt":
        return False
    pending_path = app_paths().updates / "pending.json"
    try:
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        payload = Path(pending["payload"]).resolve()
        target = Path(pending["target"]).resolve()
        candidate = payload / "UniversalVideoTranslator.exe"
        if not candidate.is_file():
            return False
        if target != Path(sys.executable).resolve().parent:
            return False
        if not _signatures_match(candidate, Path(sys.executable)):
            return False
        script = app_paths().updates / "apply-update.ps1"
        quoted_payload = str(payload).replace("'", "''")
        quoted_target = str(target).replace("'", "''")
        quoted_pending = str(pending_path).replace("'", "''")
        script.write_text(
            "$ErrorActionPreference='Stop'\n"
            f"Wait-Process -Id {os.getpid()}\n"
            f"Copy-Item -Path '{quoted_payload}\\*' -Destination "
            f"'{quoted_target}' -Recurse -Force\n"
            f"Remove-Item -LiteralPath '{quoted_pending}' -Force\n"
            f"Start-Process -FilePath '{quoted_target}\\UniversalVideoTranslator.exe'\n",
            encoding="utf-8",
        )
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_https(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("URL aggiornamento non sicuro")


def _signature_thumbprint(executable: Path) -> str | None:
    escaped = str(executable.resolve()).replace("'", "''")
    command = (
        f"$s=Get-AuthenticodeSignature -LiteralPath '{escaped}'; "
        "if ($s.Status -eq 'Valid' -and $s.SignerCertificate) "
        "{ Write-Output $s.SignerCertificate.Thumbprint; exit 0 } else { exit 1 }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    thumbprint = result.stdout.decode(errors="replace").strip().upper()
    return thumbprint if result.returncode == 0 and thumbprint else None


def _signatures_match(candidate: Path, installed: Path) -> bool:
    candidate_thumbprint = _signature_thumbprint(candidate)
    installed_thumbprint = _signature_thumbprint(installed)
    return bool(
        candidate_thumbprint
        and installed_thumbprint
        and candidate_thumbprint == installed_thumbprint
    )


def _safe_extract(archive: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            target = (destination / item.filename).resolve()
            if root not in target.parents and target != root:
                raise ValueError("Percorso non sicuro nel pacchetto")
        bundle.extractall(destination)
