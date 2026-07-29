from uvt.screen_assistant import (
    ContinuousOCR,
    GlobalHotkey,
    normalize_ocr_text,
)


def test_normalize_ocr_text_removes_empty_and_duplicate_spaces() -> None:
    assert normalize_ocr_text("  Riga   uno \r\n\r\n Riga\tdue  ") == (
        "Riga uno\nRiga due"
    )


def test_normalize_ocr_text_empty() -> None:
    assert normalize_ocr_text(" \n\t\r\n ") == ""


def test_continuous_ocr_has_minimum_interval() -> None:
    reader = ContinuousOCR(lambda *_args: None, interval=0.1)
    assert reader.interval == 2.0


def test_global_hotkey_can_be_configured() -> None:
    hotkey = GlobalHotkey(
        lambda: None,
        modifiers=6,
        hotkey_id=123,
        label="TEST",
    )
    assert hotkey.modifiers == 6
    assert hotkey.hotkey_id == 123
