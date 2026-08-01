from __future__ import annotations

from uvt.ui_theme import palette


def test_theme_palettes_keep_accessible_semantic_roles() -> None:
    dark = palette(True)
    light = palette(False)

    assert dark.background != dark.panel
    assert dark.foreground != dark.background
    assert dark.accent == "#6c8bff"
    assert light.background != light.panel
    assert light.foreground != light.background
    assert light.accent == "#315ef5"
