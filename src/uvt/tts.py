from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol

from .paths import app_paths


KOKORO_VOICES = {
    "Sara (Kokoro, donna)": "if_sara",
    "Nicola (Kokoro, uomo)": "im_nicola",
}
PIPER_VOICES = {
    "Paola (Piper, donna)": "it_IT-paola-medium",
    "Riccardo (Piper, uomo leggero)": "it_IT-riccardo-x_low",
}


class SpeechEngine(Protocol):
    def speak(self, text: str) -> None: ...

    def save(self, text: str, destination: str | Path) -> None: ...

    def stop(self) -> None: ...

    def set_rate(self, rate: int) -> None: ...


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

    def set_rate(self, rate: int) -> None:
        self.engine.setProperty("rate", max(80, min(360, int(rate))))

    def prewarm(self, _text: str) -> None:
        return


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

    def set_rate(self, rate: int) -> None:
        self.speed = max(0.65, min(1.65, int(rate) / 185))


class PiperSpeech:
    """Use Piper from an isolated external GPL runtime."""

    def __init__(self, rate: int = 185, voice: str = "it_IT-paola-medium") -> None:
        paths = app_paths()
        executable_name = "python.exe" if sys.platform == "win32" else "python"
        executable_folder = "Scripts" if sys.platform == "win32" else "bin"
        self.python = paths.piper_runtime / executable_folder / executable_name
        self.voice_directory = paths.piper_voices
        self.voice = voice if voice in PIPER_VOICES.values() else "it_IT-paola-medium"
        self.rate = max(80, min(360, int(rate)))
        self._prepared: dict[str, tuple[object, int]] = {}
        self._player = None
        if not self.python.is_file():
            raise RuntimeError(
                "Piper non installato. Esegui "
                "INSTALLA_MOTORI_OPZIONALI_WINDOWS.bat -Piper "
                "-AcceptPiperGPL."
            )
        for suffix in (".onnx", ".onnx.json"):
            if not (self.voice_directory / f"{self.voice}{suffix}").is_file():
                raise RuntimeError(
                    f"Voce Piper {self.voice} non installata. Esegui "
                    "INSTALLA_MOTORI_OPZIONALI_WINDOWS.bat -Piper "
                    "-AcceptPiperGPL."
                )

    def _render_native(self, text: str):
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory(prefix="uvt-piper-") as directory:
            output = Path(directory) / "speech.wav"
            result = subprocess.run(
                [
                    str(self.python),
                    "-m",
                    "piper",
                    "-m",
                    self.voice,
                    "--data-dir",
                    str(self.voice_directory),
                    "-f",
                    str(output),
                    "--",
                    text,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode or not output.is_file():
                detail = result.stderr.strip() or "generazione audio non riuscita"
                raise RuntimeError(f"Errore Piper: {detail[:500]}")
            audio, sample_rate = sf.read(output, dtype="float32")
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        speed = self.rate / 185
        if len(audio) and abs(speed - 1.0) > 0.01:
            target_size = max(1, round(len(audio) / speed))
            positions = np.linspace(0, len(audio) - 1, target_size)
            audio = np.interp(
                positions, np.arange(len(audio)), audio
            ).astype(np.float32)
        return audio, int(sample_rate)

    def render(self, text: str):
        prepared = self._prepared.pop(text, None)
        return prepared if prepared is not None else self._render_native(text)

    def render_to_duration(self, text: str, max_duration: float):
        import numpy as np

        audio, sample_rate = self.render(text)
        maximum = round(max_duration * sample_rate)
        if max_duration > 0 and len(audio) > maximum:
            positions = np.linspace(0, len(audio) - 1, max(1, maximum))
            audio = np.interp(
                positions, np.arange(len(audio)), audio
            ).astype(np.float32)
        return audio, sample_rate

    def prewarm(self, text: str) -> None:
        if text not in self._prepared:
            self._prepared[text] = self._render_native(text)

    def speak(self, text: str) -> None:
        import soundcard as sc

        audio, sample_rate = self.render(text)
        speaker = sc.default_speaker()
        if speaker is None:
            raise RuntimeError("Nessuna uscita audio disponibile.")
        with speaker.player(samplerate=sample_rate) as player:
            self._player = player
            player.play(audio.reshape(-1, 1))
        self._player = None

    def save(self, text: str, destination: str | Path) -> None:
        import soundfile as sf

        audio, sample_rate = self.render(text)
        sf.write(str(destination), audio, sample_rate)

    def stop(self) -> None:
        self._player = None

    def set_rate(self, rate: int) -> None:
        self.rate = max(80, min(360, int(rate)))


def available_piper_voices() -> tuple[str, ...]:
    paths = app_paths()
    executable_name = "python.exe" if sys.platform == "win32" else "python"
    executable_folder = "Scripts" if sys.platform == "win32" else "bin"
    if not (paths.piper_runtime / executable_folder / executable_name).is_file():
        return ()
    return tuple(
        label
        for label, model in PIPER_VOICES.items()
        if (paths.piper_voices / f"{model}.onnx").is_file()
        and (paths.piper_voices / f"{model}.onnx.json").is_file()
    )


def create_speech_engine(
    engine: str = "windows", voice: str = "default", rate: int = 185
) -> SpeechEngine:
    if engine == "silent":
        return SilentSpeech()
    if engine == "kokoro":
        return KokoroSpeech(rate=rate, voice=voice)
    if engine == "piper":
        return PiperSpeech(rate=rate, voice=voice)
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
