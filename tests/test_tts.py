from types import SimpleNamespace

from uvt.tts import KOKORO_VOICES, PIPER_VOICES, PiperSpeech


def test_italian_kokoro_voices() -> None:
    assert KOKORO_VOICES["Sara (Kokoro, donna)"] == "if_sara"
    assert KOKORO_VOICES["Nicola (Kokoro, uomo)"] == "im_nicola"


def test_italian_piper_voices() -> None:
    assert PIPER_VOICES["Paola (Piper, donna)"] == "it_IT-paola-medium"
    assert PIPER_VOICES["Riccardo (Piper, uomo leggero)"] == (
        "it_IT-riccardo-x_low"
    )


def test_piper_uses_isolated_runtime(monkeypatch, tmp_path) -> None:
    runtime = tmp_path / "runtime"
    python = runtime / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    voices = tmp_path / "voices"
    voices.mkdir()
    for suffix in (".onnx", ".onnx.json"):
        (voices / f"it_IT-paola-medium{suffix}").touch()
    monkeypatch.setattr(
        "uvt.tts.app_paths",
        lambda: SimpleNamespace(
            piper_runtime=runtime,
            piper_voices=voices,
        ),
    )

    speech = PiperSpeech(voice="it_IT-paola-medium")

    assert speech.python == python
    assert speech.voice_directory == voices
