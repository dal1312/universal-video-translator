from uvt.media_player import MediaPreview


def test_preview_initial_state() -> None:
    preview = MediaPreview()
    assert preview.process is None
    assert preview.pipeline is None
    preview.stop()
