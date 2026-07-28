from uvt.screen_assistant import normalize_ocr_text


def test_normalize_ocr_text_removes_empty_and_duplicate_spaces() -> None:
    assert normalize_ocr_text("  Riga   uno \r\n\r\n Riga\tdue  ") == (
        "Riga uno\nRiga due"
    )


def test_normalize_ocr_text_empty() -> None:
    assert normalize_ocr_text(" \n\t\r\n ") == ""
