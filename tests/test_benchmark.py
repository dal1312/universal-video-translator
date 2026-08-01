from uvt.benchmark import keyword_score, normalized_words, word_error_rate


def test_normalized_words_remove_case_accents_and_punctuation() -> None:
    assert normalized_words("È già PRONTO, l'audio!") == [
        "e",
        "gia",
        "pronto",
        "l",
        "audio",
    ]


def test_word_error_rate_counts_substitutions_and_insertions() -> None:
    assert word_error_rate("one two three", "one too three now") == 2 / 3
    assert word_error_rate("", "") == 0.0
    assert word_error_rate("", "extra") == 1.0


def test_keyword_score_accepts_alternative_terms() -> None:
    score = keyword_score(
        "Controlla la connessione audio prima di cominciare.",
        (("verifica", "controlla"), ("connessione",), ("iniziare", "cominciare")),
    )
    assert score == 1.0
