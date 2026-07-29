import pytest

from uvt.documents import DocumentError, load_document


def test_load_plain_text_document(tmp_path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Testo del documento", encoding="utf-8")

    document = load_document(source)

    assert document.title == "notes.txt"
    assert document.text == "Testo del documento"
    assert document.kind == "Testo"


def test_reject_unsupported_document(tmp_path) -> None:
    source = tmp_path / "archive.bin"
    source.write_bytes(b"data")

    with pytest.raises(DocumentError, match="Formato non supportato"):
        load_document(source)
