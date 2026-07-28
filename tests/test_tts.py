from uvt.tts import KOKORO_VOICES


def test_italian_kokoro_voices() -> None:
    assert KOKORO_VOICES["Sara (Kokoro, donna)"] == "if_sara"
    assert KOKORO_VOICES["Nicola (Kokoro, uomo)"] == "im_nicola"
