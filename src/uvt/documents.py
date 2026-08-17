from __future__ import annotations

import re
import threading
import zipfile
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree


SUPPORTED_DOCUMENT_EXTENSIONS = frozenset(
    {".txt", ".md", ".html", ".htm", ".docx", ".epub", ".pdf"}
)


class DocumentTranslationError(RuntimeError):
    pass


class DocumentTranslator:
    def __init__(self, translator, *, batch_size: int = 16) -> None:
        self.translator = translator
        self.batch_size = max(1, min(40, batch_size))

    def translate(
        self,
        source: str | Path,
        destination: str | Path,
        *,
        source_language: str = "auto",
        cancel: threading.Event | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        source_path = Path(source)
        destination_path = Path(destination)
        extension = source_path.suffix.casefold()
        if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
            raise DocumentTranslationError(f"Formato non supportato: {extension}")
        if not source_path.is_file():
            raise DocumentTranslationError("Documento sorgente non trovato")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        callback = on_progress or (lambda _done, _total: None)
        stop = cancel or threading.Event()
        if extension in {".txt", ".md"}:
            self._translate_plain(
                source_path,
                destination_path,
                source_language,
                stop,
                callback,
                markdown=extension == ".md",
            )
        elif extension in {".html", ".htm"}:
            destination_path.write_text(
                self._translate_html(
                    source_path.read_text(encoding="utf-8"),
                    source_language,
                    stop,
                    callback,
                ),
                encoding="utf-8",
            )
        elif extension == ".docx":
            self._translate_docx(
                source_path, destination_path, source_language, stop, callback
            )
        elif extension == ".epub":
            self._translate_epub(
                source_path, destination_path, source_language, stop, callback
            )
        else:
            self._translate_pdf(
                source_path, destination_path, source_language, stop, callback
            )
        return destination_path

    def _translated(
        self,
        values: list[str],
        language: str,
        stop: threading.Event,
        progress: Callable[[int, int], None],
    ) -> list[str]:
        output: list[str] = []
        total = len(values)
        for offset in range(0, total, self.batch_size):
            if stop.is_set():
                raise DocumentTranslationError("Traduzione documento interrotta")
            batch = values[offset : offset + self.batch_size]
            output.extend(self.translator.translate_many(batch, language))
            progress(min(offset + len(batch), total), total)
        return output

    def _translate_plain(
        self, source, destination, language, stop, progress, *, markdown=False
    ) -> None:
        lines = source.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        positions = []
        prefixes: dict[int, str] = {}
        in_code = False
        for index, line in enumerate(lines):
            stripped = line.strip()
            if markdown and stripped.startswith("```"):
                in_code = not in_code
                continue
            if not stripped or in_code:
                continue
            prefix = ""
            if markdown:
                match = re.match(
                    r"^(\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s+))(.*)$",
                    line.rstrip("\r\n"),
                )
                if match:
                    prefix, stripped = match.group(1), match.group(2).strip()
            positions.append(index)
            prefixes[index] = prefix
        translated = self._translated(
            [lines[index].strip()[len(prefixes[index].strip()) :].strip() for index in positions],
            language,
            stop,
            progress,
        )
        for index, value in zip(positions, translated):
            ending = "\n" if lines[index].endswith(("\n", "\r")) else ""
            lines[index] = prefixes[index] + value + ending
        destination.write_text("".join(lines), encoding="utf-8")

    def _translate_html(self, html, language, stop, progress) -> str:
        from bs4 import BeautifulSoup, NavigableString

        soup = BeautifulSoup(html, "html.parser")
        nodes = [
            node
            for node in soup.find_all(string=True)
            if isinstance(node, NavigableString)
            and node.strip()
            and node.parent
            and node.parent.name not in {"script", "style", "code", "pre"}
        ]
        translated = self._translated(
            [str(node).strip() for node in nodes], language, stop, progress
        )
        for node, value in zip(nodes, translated):
            leading = str(node)[: len(str(node)) - len(str(node).lstrip())]
            trailing = str(node)[len(str(node).rstrip()) :]
            node.replace_with(leading + value + trailing)
        return str(soup)

    def _translate_docx(self, source, destination, language, stop, progress) -> None:
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(
            temporary, "w", zipfile.ZIP_DEFLATED
        ) as outgoing:
            xml_names = {
                name
                for name in incoming.namelist()
                if name.startswith("word/") and name.endswith(".xml")
            }
            all_nodes: list[tuple[str, ElementTree.ElementTree, list[list]]] = []
            for name in xml_names:
                tree = ElementTree.ElementTree(
                    ElementTree.fromstring(incoming.read(name))
                )
                groups = []
                for paragraph in tree.iter():
                    if not paragraph.tag.endswith("}p"):
                        continue
                    nodes = [
                        node
                        for node in paragraph.iter()
                        if node.tag.endswith("}t") and node.text and node.text.strip()
                    ]
                    if nodes:
                        groups.append(nodes)
                all_nodes.append((name, tree, groups))
            texts = [
                "".join(node.text or "" for node in group).strip()
                for _, _, groups in all_nodes
                for group in groups
            ]
            translated = iter(self._translated(texts, language, stop, progress))
            rendered: dict[str, bytes] = {}
            for name, tree, groups in all_nodes:
                for group in groups:
                    original = "".join(node.text or "" for node in group)
                    leading = original[: len(original) - len(original.lstrip())]
                    trailing = original[len(original.rstrip()) :]
                    group[0].text = leading + next(translated) + trailing
                    for node in group[1:]:
                        node.text = ""
                rendered[name] = ElementTree.tostring(
                    tree.getroot(), encoding="utf-8", xml_declaration=True
                )
            for item in incoming.infolist():
                outgoing.writestr(item, rendered.get(item.filename, incoming.read(item)))
        temporary.replace(destination)

    def _translate_epub(self, source, destination, language, stop, progress) -> None:
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(temporary, "w") as outgoing:
            for item in incoming.infolist():
                data = incoming.read(item)
                if item.filename.casefold().endswith((".xhtml", ".html", ".htm")):
                    data = self._translate_html(
                        data.decode("utf-8"), language, stop, progress
                    ).encode("utf-8")
                compression = zipfile.ZIP_STORED if item.filename == "mimetype" else zipfile.ZIP_DEFLATED
                outgoing.writestr(item, data, compress_type=compression)
        temporary.replace(destination)

    def _translate_pdf(self, source, destination, language, stop, progress) -> None:
        from pypdf import PdfReader
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

        pages = [page.extract_text().splitlines() for page in PdfReader(source).pages]
        if not any(line.strip() for page in pages for line in page):
            raise DocumentTranslationError(
                "PDF senza testo rilevabile: è necessario il modulo OCR locale"
            )
        positions = [
            (page_index, line_index)
            for page_index, page in enumerate(pages)
            for line_index, line in enumerate(page)
            if line.strip()
        ]
        translated = iter(
            self._translated(
                [pages[p][line].strip() for p, line in positions],
                language,
                stop,
                progress,
            )
        )
        translated_pages: dict[int, list[str]] = {}
        for page_index, _line_index in positions:
            translated_pages.setdefault(page_index, []).append(next(translated))
        styles = getSampleStyleSheet()
        story = []
        for index in range(len(pages)):
            for paragraph in translated_pages.get(index, []):
                if paragraph.strip():
                    story.append(Paragraph(_xml_escape(paragraph), styles["BodyText"]))
                    story.append(Spacer(1, 3 * mm))
            if index < len(pages) - 1:
                story.append(PageBreak())
        SimpleDocTemplate(
            str(destination), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm
        ).build(story)


def default_document_destination(source: str | Path) -> Path:
    path = Path(source)
    return path.with_name(f"{path.stem}.italiano{path.suffix}")


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
