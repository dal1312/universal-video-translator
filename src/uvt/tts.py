from __future__ import annotations

from pathlib import Path
from typing import Protocol


KOKORO_VOICES = {
    "Sara (Kokoro, donna)": "if_sara",
    "Nicola (Kokoro, uomo)": "im_nicola",
}


class SpeechEngine(Protocol):
    def speak(self, text: str) -> None: ...

    def save(self, text: str, destination: str | Path) -> None: ...

    def stop(self) -> None: ...


class WindowsSpeech:
    def __init__(self, rate: int = 185, voice: str = "default") -> None:
        import pyttsx3

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        if voice != "default":
            for item in self.engine.getProperty("voices"):
                if voice.casefold() in {
                    str(item.id).casefold(),
                    str(item.name).casefold(),
                }:
                    self.engine.setProperty("voice", item.id)
                    break

    def speak(self, text: str) -> None:
        self.engine.say(text)
        self.engine.runAndWait()

    def save(self, text: str, destination: str | Path) -> None:
        self.engine.save_to_file(text, str(destination))
        self.engine.runAndWait()

    def stop(self) -> None:
        self.engine.stop()


class KokoroSpeech:
    def __init__(self, rate: int = 185, voice: str = "if_sara") -> None:
        try:
            from kokoro import KPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Kokoro non installato. Esegui: pip install -e .[kokoro]"
            ) from exc
        self.pipeline = KPipeline(
            lang_code="i", repo_id="hexgrad/Kokoro-82M"
        )
        self.voice = voice if voice in KOKORO_VOICES.values() else "if_sara"
        self.speed = max(0.65, min(1.5, rate / 185))
        self._player = None

    def _audio(self, text: str):
        import numpy as np

        chunks = [
            np.asarray(audio, dtype=np.float32)
            for _graphemes, _phonemes, audio in self.pipeline(
                text, voice=self.voice, speed=self.speed
            )
        ]
        if not chunks:
            raise RuntimeError("Kokoro non ha generato audio.")
        return np.concatenate(chunks)

    def speak(self, text: str) -> None:
        import soundcard as sc

        audio = self._audio(text).reshape(-1, 1)
        speaker = sc.default_speaker()
        if speaker is None:
            raise RuntimeError("Nessuna uscita audio disponibile.")
        with speaker.player(samplerate=24000) as player:
            self._player = player
            player.play(audio)
        self._player = None

    def save(self, text: str, destination: str | Path) -> None:
        import soundfile as sf

        sf.write(str(destination), self._audio(text), 24000)

    def stop(self) -> None:
        self._player = None


def create_speech_engine(
    engine: str = "windows", voice: str = "default", rate: int = 185
) -> SpeechEngine:
    if engine == "kokoro":
        return KokoroSpeech(rate=rate, voice=voice)
    return WindowsSpeech(rate=rate, voice=voice)


def windows_voice_names() -> list[str]:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        names = [str(item.name) for item in engine.getProperty("voices")]
        engine.stop()
        return names
    except Exception:
        return []
