from __future__ import annotations

from dataclasses import dataclass

from .audio_routing import AudioRoutingError
from .browser_protocol import BrowserProtocolError
from .documents import DocumentTranslationError
from .downloader import DownloadError
from .live import LiveCaptureError
from .ollama import OllamaError
from .transcription import TranscriptionError


@dataclass(frozen=True, slots=True)
class ErrorPresentation:
    title: str
    problem: str
    action: str

    @property
    def message(self) -> str:
        return f"{self.problem}\n\nCome risolvere:\n{self.action}"


def present_error(error: Exception) -> ErrorPresentation:
    missing_module = _missing_module(error)
    if missing_module == "faster_whisper":
        return ErrorPresentation(
            "Trascrizione non disponibile",
            "Il componente Faster-Whisper non è installato.",
            "Esegui INSTALL_WINDOWS.bat e riavvia UVT.",
        )
    if missing_module == "kokoro":
        return ErrorPresentation(
            "Voce neurale non disponibile",
            "Il motore vocale Kokoro non è installato.",
            "Esegui INSTALL_WINDOWS.bat e riavvia UVT.",
        )
    if missing_module == "soundcard":
        return ErrorPresentation(
            "Audio Live non disponibile",
            "Il componente di acquisizione SoundCard non è installato.",
            "Esegui INSTALL_WINDOWS.bat e riavvia UVT.",
        )
    if isinstance(error, OllamaError):
        return ErrorPresentation(
            "Traduzione non disponibile",
            "Ollama o il modello di traduzione non risultano pronti.",
            "Avvia Ollama e installa un modello dalle Impostazioni avanzate.",
        )
    if isinstance(error, AudioRoutingError):
        return ErrorPresentation(
            "Routing audio non disponibile",
            "UVT non riesce a collegare il browser a VB-Cable.",
            "Verifica VB-Cable, chiudi eventuali sessioni audio e riprova.",
        )
    if isinstance(error, LiveCaptureError):
        return ErrorPresentation(
            "Acquisizione audio non riuscita",
            "Il dispositivo audio selezionato non è disponibile. Firefox invia l’audio a UVT tramite VB-Cable.",
            "Verifica CABLE Output, chiudi e riapri UVT, poi seleziona di nuovo CABLE Output nelle Impostazioni.",
        )
    if isinstance(error, TranscriptionError):
        return ErrorPresentation(
            "Trascrizione non riuscita",
            "UVT non è riuscito a estrarre o trascrivere l’audio.",
            "Verifica FFmpeg e Faster-Whisper, quindi riprova con il profilo Rapido.",
        )
    if isinstance(error, DownloadError):
        return ErrorPresentation(
            "Download non riuscito",
            "La sorgente online non è stata scaricata.",
            "Controlla il collegamento e, se richiesto, configura i cookie in Avanzate.",
        )
    if isinstance(error, DocumentTranslationError):
        return ErrorPresentation(
            "Documento non tradotto",
            str(error).rstrip("."),
            "Controlla formato e destinazione, poi riprova.",
        )
    if isinstance(error, BrowserProtocolError):
        return ErrorPresentation(
            "Collegamento browser non disponibile",
            str(error).rstrip("."),
            "Ricarica l’estensione dalla cartella browser_extension e riprova.",
        )
    if isinstance(error, FileNotFoundError):
        return ErrorPresentation(
            "File non trovato",
            "Un file necessario non è più disponibile.",
            "Seleziona nuovamente il file e ripeti l’operazione.",
        )
    return ErrorPresentation(
        "Operazione non completata",
        "UVT ha interrotto l’operazione per un errore imprevisto.",
        "Riprova; se l’errore continua, usa Copia diagnostica e consulta i log.",
    )


def _missing_module(error: Exception) -> str | None:
    if isinstance(error, ModuleNotFoundError):
        return error.name
    message = str(error).casefold().replace("-", "_")
    for module in ("faster_whisper", "kokoro", "soundcard"):
        if module in message:
            return module
    return None
