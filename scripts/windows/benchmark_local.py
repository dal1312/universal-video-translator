from __future__ import annotations

import argparse
import base64
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from uvt.benchmark import keyword_score, word_error_rate  # noqa: E402
from uvt.ollama import OllamaTranslator  # noqa: E402
from uvt.transcription import transcribe_media  # noqa: E402
from uvt.tts import create_speech_engine  # noqa: E402


TRANSCRIPT = (
    "The meeting starts tomorrow morning. Please check the audio connection "
    "before the presentation."
)
TRANSLATION_CASES = (
    (
        "The meeting starts tomorrow morning.",
        (("riunione",), ("domani",), ("mattina",)),
    ),
    (
        "El sistema funciona correctamente después de la última prueba.",
        (
            ("sistema",),
            ("funziona",),
            ("correttamente", "bene", "perfettamente", "perfezione"),
            ("prova", "test"),
        ),
    ),
    (
        "Le fichier vidéo est prêt pour l'exportation.",
        (
            ("file", "video"),
            ("pronto",),
            ("esportazione", "esportato", "esportare"),
        ),
    ),
    (
        "Bitte überprüfen Sie die Audioverbindung, bevor Sie beginnen.",
        (
            ("verifica", "verificate", "controlla", "controllate"),
            ("connessione",),
            ("audio",),
            ("iniziare", "inizia", "cominciare"),
        ),
    ),
)


def _generate_fixture(destination: Path) -> None:
    escaped_path = str(destination).replace("'", "''")
    escaped_text = TRANSCRIPT.replace("'", "''")
    command = f"""
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $speaker.GetInstalledVoices() |
    Where-Object {{ $_.VoiceInfo.Culture.Name -like 'en-*' }} |
    Select-Object -First 1
if (-not $voice) {{ throw 'Voce Windows inglese non disponibile.' }}
$speaker.SelectVoice($voice.VoiceInfo.Name)
$speaker.SetOutputToWaveFile('{escaped_path}')
$speaker.Speak('{escaped_text}')
$speaker.Dispose()
"""
    encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-EncodedCommand",
            encoded,
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


def run(model: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="uvt-benchmark-") as directory:
        fixture = Path(directory) / "speech.wav"
        _generate_fixture(fixture)
        started = time.perf_counter()
        cues = transcribe_media(fixture, model="base", language="en")
        whisper_seconds = time.perf_counter() - started
    transcript = " ".join(cue.text for cue in cues)
    wer = word_error_rate(TRANSCRIPT, transcript)

    translator = OllamaTranslator(model=model, timeout=120.0)
    warmup_started = time.perf_counter()
    translator.warmup()
    warmup_seconds = time.perf_counter() - warmup_started
    translations: list[dict[str, object]] = []
    translation_times: list[float] = []
    for source, required in TRANSLATION_CASES:
        started = time.perf_counter()
        translated = translator.translate_realtime(source)
        elapsed = time.perf_counter() - started
        translation_times.append(elapsed)
        translations.append(
            {
                "source": source,
                "translation": translated,
                "seconds": round(elapsed, 3),
                "keyword_score": round(keyword_score(translated, required), 3),
            }
        )

    speech = create_speech_engine("kokoro", "if_sara", 200)
    spoken_text = " ".join(str(item["translation"]) for item in translations)
    started = time.perf_counter()
    audio, sample_rate = speech.render(spoken_text)  # type: ignore[attr-defined]
    tts_seconds = time.perf_counter() - started
    audio_seconds = len(audio) / sample_rate
    speech.stop()

    translation_score = statistics.mean(
        float(item["keyword_score"]) for item in translations
    )
    translation_p95 = max(translation_times)
    tts_realtime_factor = tts_seconds / max(audio_seconds, 0.001)
    passed = (
        wer <= 0.15
        and translation_score >= 0.80
        and translation_p95 <= 6.0
        and tts_realtime_factor <= 1.0
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "thresholds": {
            "whisper_wer_max": 0.15,
            "translation_keyword_score_min": 0.80,
            "translation_worst_seconds_max": 6.0,
            "tts_realtime_factor_max": 1.0,
        },
        "whisper": {
            "model": "base",
            "seconds": round(whisper_seconds, 3),
            "word_error_rate": round(wer, 3),
            "transcript": transcript,
        },
        "translation": {
            "model": model,
            "warmup_seconds": round(warmup_seconds, 3),
            "median_seconds": round(statistics.median(translation_times), 3),
            "worst_seconds": round(translation_p95, 3),
            "keyword_score": round(translation_score, 3),
            "cases": translations,
        },
        "speech": {
            "engine": "kokoro",
            "generation_seconds": round(tts_seconds, 3),
            "audio_seconds": round(audio_seconds, 3),
            "realtime_factor": round(tts_realtime_factor, 3),
        },
        "scope": (
            "Benchmark locale controllato dei componenti; la latenza browser "
            "end-to-end include anche cattura, VAD e code della sessione reale."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark locale UVT")
    parser.add_argument("--model", default="translategemma:latest")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.model)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
