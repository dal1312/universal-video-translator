from __future__ import annotations

import threading
from typing import Callable


class VoiceCommandError(RuntimeError):
    pass


class VoiceCommandRecorder:
    def __init__(
        self,
        model_name: str = "small",
        duration: float = 5.0,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self.model_name = model_name
        self.duration = max(2.0, min(12.0, float(duration)))
        self.on_status = on_status or (lambda _text: None)
        self._model = None
        self._model_lock = threading.Lock()

    def _whisper(self):
        with self._model_lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                self.on_status(
                    f"Caricamento Whisper {self.model_name}…"
                )
                self._model = WhisperModel(
                    self.model_name,
                    device="auto",
                    compute_type="int8",
                )
            return self._model

    def record_and_transcribe(self) -> str:
        try:
            import numpy as np
            import soundcard as sc
        except ImportError as exc:
            raise VoiceCommandError(
                "Comandi vocali non installati. "
                "Esegui INSTALL_WINDOWS.bat."
            ) from exc

        microphone = sc.default_microphone()
        if microphone is None:
            raise VoiceCommandError(
                "Nessun microfono predefinito disponibile."
            )
        sample_rate = 16000
        self.on_status(f"Parla ora… ({self.duration:g} secondi)")
        try:
            with microphone.recorder(
                samplerate=sample_rate, channels=1
            ) as recorder:
                audio = recorder.record(
                    numframes=int(sample_rate * self.duration)
                )
        except Exception as exc:
            raise VoiceCommandError(
                f"Registrazione microfono non riuscita: {exc}"
            ) from exc

        mono = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not len(mono) or float(np.max(np.abs(mono))) < 0.003:
            raise VoiceCommandError("Nessuna voce rilevata.")

        self.on_status("Trascrizione comando vocale…")
        segments, _info = self._whisper().transcribe(
            mono,
            language="it",
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ).strip()
        if not text:
            raise VoiceCommandError("Comando vocale non riconosciuto.")
        return text

