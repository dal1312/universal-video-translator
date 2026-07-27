from pathlib import Path

import pytest

from uvt.export import export_italian_audio


def test_export_rejects_empty_cues(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Nessuna battuta"):
        export_italian_audio(
            [],
            tmp_path / "output.wav",
            translator=object(),  # type: ignore[arg-type]
            cache=object(),  # type: ignore[arg-type]
        )
