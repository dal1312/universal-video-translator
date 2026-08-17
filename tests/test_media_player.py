from uvt.media_player import MediaPreview


def test_preview_initial_state() -> None:
    preview = MediaPreview()
    assert preview.process is None
    assert preview.pipeline is None
    preview.stop()


def test_pcm_stream_uses_translated_audio_only(monkeypatch) -> None:
    commands = []

    class FakePipe:
        def close(self) -> None:
            pass

    class FakeProcess:
        def __init__(self, command, **_kwargs) -> None:
            commands.append(command)
            self.stdin = FakePipe()

        def poll(self):
            return None

        def terminate(self) -> None:
            pass

    monkeypatch.setattr(MediaPreview, "_ffplay", staticmethod(lambda: "ffplay"))
    monkeypatch.setattr(
        MediaPreview,
        "_has_media_streams",
        staticmethod(lambda _media: (True, True)),
    )
    monkeypatch.setattr("uvt.media_player.ensure_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr("uvt.media_player.subprocess.Popen", FakeProcess)

    MediaPreview().open_pcm_stream("video.mp4")

    ffmpeg_command = commands[1]
    assert "-filter_complex" not in ffmpeg_command
    assert "0:a:0" not in ffmpeg_command
    assert "1:a:0" in ffmpeg_command
    assert ffmpeg_command[ffmpeg_command.index("-af") + 1] == "apad"


def test_preview_stop_waits_for_processes() -> None:
    events: list[str] = []

    class FakeProcess:
        stdin = None

        def __init__(self, name: str) -> None:
            self.name = name
            self.running = True

        def poll(self):
            return None if self.running else 0

        def terminate(self) -> None:
            events.append(f"terminate:{self.name}")
            self.running = False

        def wait(self, timeout=None) -> int:
            events.append(f"wait:{self.name}")
            return 0

    preview = MediaPreview()
    preview.pipeline = FakeProcess("pipeline")  # type: ignore[assignment]
    preview.process = FakeProcess("player")  # type: ignore[assignment]

    assert preview.stop()
    assert events == [
        "terminate:pipeline",
        "wait:pipeline",
        "terminate:player",
        "wait:player",
    ]
    assert preview.pipeline is None
    assert preview.process is None
