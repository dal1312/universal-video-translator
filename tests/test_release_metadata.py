import hashlib
import json
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from scripts.package_release import deterministic_zip
from uvt import __version__


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_project_package_and_extension_versions_match() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "browser_extension" / "manifest.json").read_text(encoding="utf-8")
    )

    assert project["project"]["version"] == __version__
    assert manifest["version"] == __version__


def test_deterministic_zip_has_stable_hash_and_sorted_entries(tmp_path) -> None:
    source = tmp_path / "payload"
    source.mkdir()
    (source / "b.txt").write_text("second\n", encoding="utf-8")
    (source / "a.txt").write_text("first\n", encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    deterministic_zip(source, first, 1_700_000_000)
    deterministic_zip(source, second, 1_700_000_000)

    assert _sha256(first) == _sha256(second)
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["payload/a.txt", "payload/b.txt"]


def test_official_release_requires_clean_tag_by_default() -> None:
    script = (ROOT / "scripts" / "windows" / "Build-Release.ps1").read_text(
        encoding="utf-8"
    )

    assert "[switch]$AllowDirty" in script
    assert "if (-not $AllowDirty)" in script
    assert "[switch]$RequireCleanTag" not in script
