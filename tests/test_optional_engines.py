from __future__ import annotations

import base64
import io
import json

import pytest

from uvt.optional_engines import _update_argos_index


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def test_argos_index_uses_github_api(monkeypatch, tmp_path) -> None:
    index = [{"from_code": "en", "to_code": "it"}]
    encoded = base64.b64encode(json.dumps(index).encode()).decode()
    payload = json.dumps(
        {"content": f"{encoded[:8]}\n{encoded[8:]}\n"}
    ).encode()
    monkeypatch.setattr(
        "uvt.optional_engines.urllib.request.urlopen",
        lambda request, timeout: _Response(payload),
    )
    destination = tmp_path / "argos" / "index.json"

    _update_argos_index(destination)

    assert json.loads(destination.read_text()) == index


def test_argos_index_reports_network_failure(monkeypatch, tmp_path) -> None:
    def fail(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(
        "uvt.optional_engines.urllib.request.urlopen",
        fail,
    )

    with pytest.raises(RuntimeError, match="Indice Argos non raggiungibile"):
        _update_argos_index(tmp_path / "index.json")
