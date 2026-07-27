from uvt.downloader import is_web_url


def test_web_url_validation() -> None:
    assert is_web_url("https://www.youtube.com/watch?v=abc")
    assert not is_web_url("C:/video.mp4")
    assert not is_web_url("javascript:alert(1)")
