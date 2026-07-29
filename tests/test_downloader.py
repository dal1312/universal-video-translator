from uvt.downloader import is_web_url, subtitle_language_candidates


def test_web_url_validation() -> None:
    assert is_web_url("https://www.youtube.com/watch?v=abc")
    assert not is_web_url("C:/video.mp4")
    assert not is_web_url("javascript:alert(1)")


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
