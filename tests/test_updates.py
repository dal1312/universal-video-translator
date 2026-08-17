from __future__ import annotations

import zipfile

import pytest

from uvt.updates import AutomaticUpdater, _require_https, _safe_extract, is_newer


def test_semantic_update_comparison() -> None:
    assert is_newer("0.2.2", "0.2.1")
    assert is_newer("v1.0.0", "0.9.9")
    assert not is_newer("0.2.1", "0.2.1")
    assert not is_newer("invalid", "0.2.1")


def test_update_archive_rejects_path_traversal(tmp_path) -> None:
    archive = tmp_path / "update.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside.exe", b"unsafe")

    with pytest.raises(ValueError, match="non sicuro"):
        _safe_extract(archive, tmp_path / "stage")

    assert not (tmp_path / "outside.exe").exists()


def test_source_install_reports_update_without_mutating_files(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"tag_name": "v0.2.2", "assets": []}

    class Session:
        def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.delattr("sys.frozen", raising=False)
    updater = AutomaticUpdater("0.2.1", session=Session())

    result = updater.check_and_stage()

    assert result.status == "available"
    assert result.version == "0.2.2"


def test_update_downloads_require_https() -> None:
    _require_https("https://example.com/update.zip")
    with pytest.raises(ValueError, match="non sicuro"):
        _require_https("http://example.com/update.zip")
