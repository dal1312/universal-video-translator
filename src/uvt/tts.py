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

    def prewarm(self, _text: str) -> None:
        return


class SilentSpeech:
    def speak(self, _text: str) -> None:
        return

    def save(self, _text: str, _destination: str | Path) -> None:
        return

    def stop(self) -> None:
        return

    def prewarm(self, _text: str) -> None:
        return


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
        self._prepared: dict[str, object] = {}

    def _generate_audio(self, text: str, speed: float):
        import numpy as np

        chunks = [
            np.asarray(audio, dtype=np.float32)
            for _graphemes, _phonemes, audio in self.pipeline(
                text, voice=self.voice, speed=speed
            )
        ]
        if not chunks:
            raise RuntimeError("Kokoro non ha generato audio.")
        return np.concatenate(chunks)

    def _audio(self, text: str):
        prepared = self._prepared.pop(text, None)
        if prepared is not None:
            return prepared
        return self._generate_audio(text, self.speed)

    def prewarm(self, text: str) -> None:
        if text not in self._prepared:
            self._prepared[text] = self._audio(text)

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

    def render(self, text: str):
        return self._audio(text), 24000

    def render_to_duration(self, text: str, max_duration: float):
        audio = self._audio(text)
        if max_duration > 0 and len(audio) > round(max_duration * 24000):
            required_speed = self.speed * len(audio) / (
                max_duration * 24000
            )
            audio = self._generate_audio(
                text, min(2.2, required_speed * 1.03)
            )
        return audio, 24000

    def stop(self) -> None:
        self._player = None


def create_speech_engine(
    engine: str = "windows", voice: str = "default", rate: int = 185
) -> SpeechEngine:
    if engine == "silent":
        return SilentSpeech()
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
