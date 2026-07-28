from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TIMING = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{3})"
)
_TAG = re.compile(r"<[^>]+>")
_WORD = re.compile(r"\w+(?:['’]\w+)*", re.UNICODE)


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


def _word_data(text: str):
    matches = list(_WORD.finditer(text))
    return [match.group(0).casefold() for match in matches], matches


def _common_prefix(left: list[str], right: list[str]) -> int:
    size = 0
    for left_word, right_word in zip(left, right):
        if left_word != right_word:
            break
        size += 1
    return size


def _suffix_prefix(left: list[str], right: list[str]) -> int:
    for size in range(min(len(left), len(right)), 0, -1):
        if left[-size:] == right[:size]:
            return size
    return 0


def _contains_words(container: list[str], candidate: list[str]) -> bool:
    if not candidate or len(candidate) > len(container):
        return False
    return any(
        container[index : index + len(candidate)] == candidate
        for index in range(len(container) - len(candidate) + 1)
    )


def _append_text(base: str, tail: str) -> str:
    tail = tail.strip()
    if not base:
        return tail.lstrip(" ,;:")
    if not tail:
        return base
    if tail[0] in ",.;:!?”:
        return base.rstrip(" ,.;:!?") + tail
    return f"{base.rstrip()} {tail}"


def _replace_trailing_words(
    chain: str, previous_words: list[str], current: str
) -> str:
    chain_words, matches = _word_data(chain)
    if (
        previous_words
        and len(chain_words) >= len(previous_words)
        and chain_words[-len(previous_words) :] == previous_words
    ):
        cut = matches[-len(previous_words)].start()
        return _append_text(chain[:cut].rstrip(), current)
    return current


def _merge_rolling_text(
    chain: str, previous: str, current: str
) -> tuple[str, bool]:
    previous_words, _previous_matches = _word_data(previous)
    current_words, current_matches = _word_data(current)
    if not previous_words or not current_words:
        return current, False
    if previous_words == current_words:
        return chain, True
    if _contains_words(previous_words, current_words):
        return chain, True

    overlap = _suffix_prefix(previous_words, current_words)
    if overlap >= 3 or (
        overlap >= 2
        and overlap / min(len(previous_words), len(current_words)) >= 0.5
    ):
        tail = current[current_matches[overlap - 1].end() :]
        return _append_text(chain, tail), True

    common = _common_prefix(previous_words, current_words)
    if common >= 3 and common / min(
        len(previous_words), len(current_words)
    ) >= 0.5:
        if not chain:
            tail = current[current_matches[common - 1].end() :]
            return _append_text("", tail), True
        return _replace_trailing_words(chain, previous_words, current), True

    if _contains_words(current_words, previous_words):
        return _replace_trailing_words(chain, previous_words, current), True
    return current, False


def collapse_rolling_cues(
    cues: list[Cue], max_duration: float = 12.0, max_words: int = 60
) -> list[Cue]:
    if not cues:
        return []

    collapsed: list[Cue] = []
    chain = cues[0].text
    chain_start = cues[0].start
    chain_end = cues[0].end
    previous = cues[0].text

    for cue in cues[1:]:
        related = cue.start <= chain_end + 1.25
        merged = cue.text
        if related:
            merged, related = _merge_rolling_text(chain, previous, cue.text)

        if not related:
            if chain.strip():
                collapsed.append(Cue(chain_start, chain_end, chain.strip()))
            chain = cue.text
            chain_start = cue.start
            chain_end = cue.end
        else:
            was_empty = not chain.strip()
            chain = merged
            if was_empty and chain.strip():
                chain_start = cue.start
            chain_end = max(chain_end, cue.end)
        previous = cue.text

        word_count = len(_word_data(chain)[0])
        if chain.strip() and (
            chain_end - chain_start >= max_duration
            or word_count >= max_words
        ):
            collapsed.append(Cue(chain_start, chain_end, chain.strip()))
            chain = ""
            chain_start = chain_end

    if chain.strip():
        collapsed.append(Cue(chain_start, chain_end, chain.strip()))
    return collapsed


def load_subtitles(path: str | Path) -> list[Cue]:
    source = Path(path)
    if source.suffix.lower() not in {".srt", ".vtt"}:
        raise ValueError("Formato non supportato: usa un file .srt o .vtt")
    return parse_subtitles(source.read_text(encoding="utf-8-sig"))
