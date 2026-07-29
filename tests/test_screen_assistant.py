from uvt.screen_assistant import ContinuousOCR, normalize_ocr_text


def test_normalize_ocr_text_removes_empty_and_duplicate_spaces() -> None:
    assert normalize_ocr_text("  Riga   uno \r\n\r\n Riga\tdue  ") == (
        "Riga uno\nRiga due"
    )


def test_normalize_ocr_text_empty() -> None:
    assert normalize_ocr_text(" \n\t\r\n ") == ""


def test_continuous_ocr_has_minimum_interval() -> None:
    reader = ContinuousOCR(lambda *_args: None, interval=0.1)
    assert reader.interval == 2.0
