from __future__ import annotations

import json

from uvt.glossary import TranslationGlossary


def test_glossary_matches_only_terms_present_in_text(tmp_path) -> None:
    path = tmp_path / "glossary.json"
    path.write_text(
        json.dumps({"machine learning": "apprendimento automatico", "GPU": "GPU"}),
        encoding="utf-8",
    )
    glossary = TranslationGlossary(path)

    assert glossary.matched(["A machine learning system"]) == {
        "machine learning": "apprendimento automatico"
    }


def test_glossary_revision_changes_cache_fingerprint(tmp_path) -> None:
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps({"cloud": "cloud"}), encoding="utf-8")
    first = TranslationGlossary(path).fingerprint
    path.write_text(json.dumps({"cloud": "nuvola"}), encoding="utf-8")
    second = TranslationGlossary(path).fingerprint

    assert first != second


def test_glossary_template_is_created_once(tmp_path) -> None:
    glossary = TranslationGlossary(tmp_path / "glossary.json")
    path = glossary.ensure_template()
    original = path.read_text(encoding="utf-8")

    glossary.ensure_template()

    assert path.read_text(encoding="utf-8") == original
