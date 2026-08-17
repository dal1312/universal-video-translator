from __future__ import annotations

import threading
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

    def set_rate(self, rate: int) -> None: ...


class SilentSpeech:
    def speak(self, _text: str) -> None:
        return

    def save(self, _text: str, _destination: str | Path) -> None:
        return

    def stop(self) -> None:
        return

    def set_rate(self, _rate: int) -> None:
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
        self.pipeline = KPipeline(lang_code="i", repo_id="hexgrad/Kokoro-82M")
        self.voice = voice if voice in KOKORO_VOICES.values() else "if_sara"
        self.speed = max(0.65, min(1.5, rate / 185))
        self._player = None
        self._prepared: dict[str, object] = {}
        self._prepared_lock = threading.Lock()
        self._render_lock = threading.Lock()

    def _generate_audio(self, text: str, speed: float):
        import numpy as np

        with self._render_lock:
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
        with self._prepared_lock:
            prepared = self._prepared.pop(text, None)
        if prepared is not None:
            return prepared
        return self._generate_audio(text, self.speed)

    def prewarm(self, text: str) -> None:
        with self._prepared_lock:
            if text in self._prepared:
                return
        audio = self._generate_audio(text, self.speed)
        with self._prepared_lock:
            self._prepared.setdefault(text, audio)

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
            required_speed = self.speed * len(audio) / (max_duration * 24000)
            audio = self._generate_audio(text, min(2.2, required_speed * 1.03))
        return audio, 24000

    def stop(self) -> None:
        self._player = None

    def set_rate(self, rate: int) -> None:
        self.speed = max(0.65, min(1.65, int(rate) / 185))


def create_speech_engine(
    engine: str = "kokoro", voice: str = "Sara (Kokoro, donna)", rate: int = 185
) -> SpeechEngine:
    engine = compatible_speech_engine(engine, voice)
    if engine == "silent":
        return SilentSpeech()
    if engine == "kokoro":
        # Kokoro is an explicit voice choice. Never silently replace it with
        # a Windows SAPI voice: a missing neural engine must be visible to the
        # user so the selected voice remains predictable.
        return KokoroSpeech(
            rate=rate,
            voice=KOKORO_VOICES.get(voice, KOKORO_VOICES["Sara (Kokoro, donna)"]),
        )
    raise RuntimeError(
        "Sono disponibili solo le voci neurali Kokoro. "
        "Seleziona Sara o Nicola nelle impostazioni."
    )


def compatible_speech_engine(engine: str, voice: str) -> str:
    """Migrate legacy SAPI/Piper selections to the supported Kokoro engine."""
    return "kokoro"
