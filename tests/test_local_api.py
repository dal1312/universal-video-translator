import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from uvt.automation import MacroStore
from uvt.local_api import LocalAPIServer
from uvt.plugins import PluginManager


def test_local_api_health_and_auth(tmp_path) -> None:
    server = LocalAPIServer(
        assistant_handler=lambda *_args: "ok",
        macro_requester=lambda _name: None,
        plugins=PluginManager(tmp_path / "plugins"),
        macros=MacroStore(tmp_path / "macros.json"),
        port=0,
        token_path=tmp_path / "token.txt",
    )
    server.start()
    try:
        with urlopen(f"{server.address}/health") as response:
            assert json.load(response)["status"] == "ok"

        with pytest.raises(HTTPError) as error:
            urlopen(f"{server.address}/v1/plugins")
        assert error.value.code == 401

        request = Request(
            f"{server.address}/v1/plugins",
            headers={"Authorization": f"Bearer {server.token}"},
        )
        with urlopen(request) as response:
            assert json.load(response)["plugins"]
    finally:
        server.stop()
