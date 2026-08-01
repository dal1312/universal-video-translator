from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


def normalized_words(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.findall(r"[^\W_]+", plain, flags=re.UNICODE)


def word_error_rate(reference: str, hypothesis: str) -> float:
    expected = normalized_words(reference)
    actual = normalized_words(hypothesis)
    if not expected:
        return 0.0 if not actual else 1.0
    previous = list(range(len(actual) + 1))
    for row, expected_word in enumerate(expected, start=1):
        current = [row]
        for column, actual_word in enumerate(actual, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected_word != actual_word),
                )
            )
        previous = current
    return previous[-1] / len(expected)


def keyword_score(
    value: str,
    required_groups: Iterable[Iterable[str]],
) -> float:
    words = set(normalized_words(value))
    groups = [
        {word for candidate in group for word in normalized_words(candidate)}
        for group in required_groups
    ]
    if not groups:
        return 1.0
    return sum(bool(words.intersection(group)) for group in groups) / len(groups)
