from __future__ import annotations

from pathlib import Path

from uvt.executables import find_executable


def test_find_executable_prefers_path(monkeypatch) -> None:
    monkeypatch.setattr("uvt.executables.shutil.which", lambda name: f"X:/{name}.exe")

    assert find_executable("ffmpeg") == "X:/ffmpeg.exe"


def test_find_executable_finds_bundled_runtime(monkeypatch, tmp_path) -> None:
    executable = tmp_path / "app.exe"
    bundled = tmp_path / "_internal" / "ffprobe.exe"
    bundled.parent.mkdir()
    bundled.touch()
    monkeypatch.setattr("uvt.executables.shutil.which", lambda _name: None)
    monkeypatch.setattr("uvt.executables.sys.executable", str(executable))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert find_executable("ffprobe") == str(Path(bundled))
