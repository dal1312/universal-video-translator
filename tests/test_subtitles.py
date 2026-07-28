from uvt.subtitles import Cue, collapse_rolling_cues, parse_subtitles, timestamp_seconds


def test_timestamp_seconds() -> None:
    assert timestamp_seconds("01:02:03,500") == 3723.5


def test_parse_srt() -> None:
    content = """1
00:00:01,000 --> 00:00:02,500
Hello <i>world</i>

2
00:00:03,000 --> 00:00:04,000
Second line
"""
    cues = parse_subtitles(content)
    assert [(cue.start, cue.end, cue.text) for cue in cues] == [
        (1.0, 2.5, "Hello world"),
        (3.0, 4.0, "Second line"),
    ]


def test_parse_webvtt() -> None:
    content = """WEBVTT

00:00:01.000 --> 00:00:02.000
Hello
"""
    cues = parse_subtitles(content)
    assert len(cues) == 1
    assert cues[0].text == "Hello"


def test_collapse_youtube_rolling_captions() -> None:
    cues = [
        Cue(0.0, 2.0, "Sono uno strumento per diffondere un messaggio."),
        Cue(1.8, 3.5, "diffondere un messaggio, per diffonderlo"),
        Cue(
            3.2,
            5.5,
            "diffondere un messaggio, per diffondere ideologie, "
            "per essere indottrinati.",
        ),
    ]

    collapsed = collapse_rolling_cues(cues)

    assert len(collapsed) == 1
    assert collapsed[0].text.casefold().count("diffondere un messaggio") == 1
    assert "diffondere ideologie" in collapsed[0].text


def test_unrelated_captions_stay_separate() -> None:
    cues = [
        Cue(0.0, 1.0, "Prima frase."),
        Cue(2.5, 3.5, "Seconda frase."),
    ]

    assert collapse_rolling_cues(cues) == cues
