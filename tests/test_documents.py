from __future__ import annotations

import json
import zipfile
from xml.etree import ElementTree

import pytest

from uvt.documents import (
    DocumentTranslationError,
    DocumentTranslator,
    default_document_destination,
)


class _Translator:
    def translate_many(self, texts, _language):
        return [f"IT:{text}" for text in texts]


def test_plain_text_translation_preserves_blank_lines(tmp_path) -> None:
    source = tmp_path / "notes.txt"
    output = tmp_path / "notes.italiano.txt"
    source.write_text("Hello\n\nWorld\n", encoding="utf-8")

    DocumentTranslator(_Translator()).translate(source, output)

    assert output.read_text(encoding="utf-8") == "IT:Hello\n\nIT:World\n"


def test_html_translation_preserves_code_and_markup(tmp_path) -> None:
    source = tmp_path / "page.html"
    output = tmp_path / "page.italiano.html"
    source.write_text(
        "<h1>Hello</h1><p>World</p><code>print('hello')</code>",
        encoding="utf-8",
    )

    DocumentTranslator(_Translator()).translate(source, output)
    rendered = output.read_text(encoding="utf-8")

    assert "<h1>IT:Hello</h1>" in rendered
    assert "<p>IT:World</p>" in rendered
    assert "print('hello')" in rendered


def test_markdown_translation_preserves_structure_and_code(tmp_path) -> None:
    source = tmp_path / "guide.md"
    output = tmp_path / "guide.italiano.md"
    source.write_text(
        "# Heading\n\n- First item\n\n```python\nprint('hello')\n```\n",
        encoding="utf-8",
    )

    DocumentTranslator(_Translator()).translate(source, output)
    rendered = output.read_text(encoding="utf-8")

    assert "# IT:Heading" in rendered
    assert "- IT:First item" in rendered
    assert "print('hello')" in rendered


def test_docx_translation_preserves_package_and_replaces_text(tmp_path) -> None:
    source = tmp_path / "sample.docx"
    output = tmp_path / "sample.italiano.docx"
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(source, "w") as package:
        package.writestr("word/document.xml", document_xml)
        package.writestr("[Content_Types].xml", "<Types/>")

    DocumentTranslator(_Translator()).translate(source, output)

    with zipfile.ZipFile(output) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))
        assert any(node.text == "IT:Hello" for node in root.iter())
        assert package.read("[Content_Types].xml") == b"<Types/>"


def test_document_rejects_unsupported_extension(tmp_path) -> None:
    source = tmp_path / "data.json"
    source.write_text(json.dumps({"text": "Hello"}), encoding="utf-8")

    with pytest.raises(DocumentTranslationError, match="non supportato"):
        DocumentTranslator(_Translator()).translate(source, tmp_path / "out.json")


def test_default_destination_keeps_format(tmp_path) -> None:
    assert default_document_destination(tmp_path / "book.epub").name == (
        "book.italiano.epub"
    )
