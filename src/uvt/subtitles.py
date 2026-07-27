from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TIMING = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{3})"
)
_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True, slots=True)
class Cue:
    start: float
    end: float
    text: str


def timestamp_seconds(value: str) -> float:
    hours, minutes, rest = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(rest)


def parse_subtitles(content: str) -> list[Cue]:
    lines = content.replace("\ufeff", "").replace("\r\n", "\n").split("\n")
    cues: list[Cue] = []
    index = 0

    while index < len(lines):
        match = _TIMING.search(lines[index])
        if not match:
            index += 1
            continue

        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index].strip())
            index += 1

        text = _TAG.sub("", " ".join(text_lines)).strip()
        if text:
            cues.append(
                Cue(
                    start=timestamp_seconds(match.group("start")),
                    end=timestamp_seconds(match.group("end")),
                    text=text,
                )
            )
    return cues


def load_subtitles(path: str | Path) -> list[Cue]:
    source = Path(path)
    if source.suffix.lower() not in {".srt", ".vtt"}:
        raise ValueError("Formato non supportato: usa un file .srt o .vtt")
    return parse_subtitles(source.read_text(encoding="utf-8-sig"))
