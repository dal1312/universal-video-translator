import sys
import types

import pytest

from uvt.downloader import (
    DownloadError,
    YOUTUBE_FORMAT,
    download_video,
    is_web_url,
    is_youtube_url,
    subtitle_language_candidates,
)


def test_web_url_validation() -> None:
    assert is_web_url("https://www.youtube.com/watch?v=abc")
    assert not is_web_url("C:/video.mp4")
    assert not is_web_url("javascript:alert(1)")


def test_youtube_url_detection() -> None:
    assert is_youtube_url("https://youtube.com/watch?v=abc")
    assert is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert is_youtube_url("https://youtu.be/abc")
    assert not is_youtube_url("https://rumble.com/example")


def test_explicit_source_language_selects_spanish_subtitles() -> None:
    assert subtitle_language_candidates(
        "spagnolo", "en", ("en", "es", "fr")
    ) == ["es"]


def test_auto_uses_native_metadata_language() -> None:
    assert subtitle_language_candidates(
        "auto", "es", ("en", "es", "it", "fr")
    ) == ["es"]


def test_auto_does_not_default_to_english_without_language_metadata() -> None:
    assert subtitle_language_candidates(
        "auto", None, ("en", "es", "it", "fr")
    ) == []


def test_language_candidates_matches_regional_variant() -> None:
    assert subtitle_language_candidates(
        "inglese", "es", ("en-US", "es", "it")
    ) == ["en-US"]


def test_youtube_requires_deno(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("uvt.downloader.shutil.which", lambda _name: None)

    with pytest.raises(DownloadError, match="Deno"):
        download_video("https://www.youtube.com/watch?v=abc", tmp_path)


def test_youtube_download_caps_video_at_720p(monkeypatch, tmp_path) -> None:
    received: dict = {}

    class FakeYoutubeDL:
        def __init__(self, options) -> None:
            received.update(options)
            self.params = options

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def extract_info(self, _url: str, download: bool):
            assert not download
            return {"id": "video", "ext": "mp4"}

        def process_ie_result(self, info, download: bool):
            assert download
            path = self.prepare_filename(info)
            path.write_bytes(b"video")
            return info

        def prepare_filename(self, info):
            return tmp_path / f"{info['id']}.{info['ext']}"

    monkeypatch.setattr("uvt.downloader.shutil.which", lambda _name: "deno")
    monkeypatch.setattr("uvt.downloader.ensure_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setitem(
        sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    )

    video, has_subtitles = download_video(
        "https://www.youtube.com/watch?v=abc", tmp_path
    )

    assert video.name == "video.mp4"
    assert not has_subtitles
    assert received["format"] == YOUTUBE_FORMAT
