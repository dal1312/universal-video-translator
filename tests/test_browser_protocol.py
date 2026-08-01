import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from uvt.browser_protocol import (
    BrowserProtocolError,
    browser_request_is_fresh,
    claim_browser_request,
    make_overlay_uri,
    make_control_uri,
    make_translate_uri,
    parse_browser_request,
    parse_translate_request,
    parse_translate_uri,
    protocol_command,
    register_protocol,
)


REQUEST_ID = "123e4567-e89b-42d3-a456-426614174000"


def test_translate_uri_roundtrip_preserves_complex_url() -> None:
    url = "https://example.com/watch?v=uno&lang=it#parte"
    assert parse_translate_uri(make_translate_uri(url)) == url


def test_overlay_request_preserves_browser_and_timestamp_without_url() -> None:
    request = parse_browser_request(
        make_overlay_uri(
            browser="chrome",
            requested_at=1234,
            request_id=REQUEST_ID,
        )
    )

    assert request.url is None
    assert request.action == "overlay"
    assert request.browser == "chrome"
    assert request.requested_at == 1234
    assert request.request_id == REQUEST_ID


def test_overlay_profile_and_control_commands_roundtrip() -> None:
    overlay = parse_browser_request(
        make_overlay_uri(
            browser="edge",
            requested_at=1234,
            request_id=REQUEST_ID,
            profile="rapido",
        )
    )
    stop = parse_browser_request(
        make_control_uri(
            "stop",
            browser="edge",
            requested_at=1234,
            request_id=REQUEST_ID,
        )
    )

    assert overlay.profile == "rapido"
    assert stop.action == "stop"
    assert stop.browser == "edge"


def test_only_recent_explicit_browser_requests_can_autostart() -> None:
    legacy = parse_translate_request(
        "uvt://translate?url=https%3A%2F%2Fexample.com%2Fvideo"
    )
    recent = parse_browser_request(
        make_overlay_uri(
            browser="edge",
            requested_at=1000,
            request_id=REQUEST_ID,
        )
    )

    assert browser_request_is_fresh(legacy, now=1000) is False
    assert browser_request_is_fresh(recent, now=1050) is True
    assert browser_request_is_fresh(recent, now=1121) is False
    assert browser_request_is_fresh(recent, now=984) is False


@pytest.mark.parametrize(
    "value",
    (
        "uvt://overlay?browser=chrome&requested_at=1000"
        f"&request_id={REQUEST_ID}&url=https%3A%2F%2Fexample.com",
        "uvt://overlay?browser=chrome&browser=edge&requested_at=1000"
        f"&request_id={REQUEST_ID}",
        "uvt://overlay?browser=chrome&requested_at=1000&requested_at=1001"
        f"&request_id={REQUEST_ID}",
        "uvt://overlay?browser=chrome&requested_at=1000"
        f"&request_id={REQUEST_ID}&request_id={REQUEST_ID}",
    ),
)
def test_overlay_request_rejects_url_and_duplicate_parameters(value: str) -> None:
    with pytest.raises(BrowserProtocolError):
        parse_browser_request(value)


def test_recent_browser_request_can_only_be_claimed_once(tmp_path) -> None:
    request = parse_browser_request(
        make_overlay_uri(
            browser="chrome",
            requested_at=1000,
            request_id=REQUEST_ID,
        )
    )

    assert claim_browser_request(request, claim_directory=tmp_path, now=1001)
    assert not claim_browser_request(request, claim_directory=tmp_path, now=1001)


def test_request_without_id_cannot_be_claimed(tmp_path) -> None:
    request = parse_browser_request(
        "uvt://overlay?browser=chrome&requested_at=1000"
    )

    assert not claim_browser_request(request, claim_directory=tmp_path, now=1001)


def test_concurrent_request_claim_has_one_winner(tmp_path) -> None:
    request = parse_browser_request(
        make_overlay_uri(
            browser="chrome",
            requested_at=1000,
            request_id=REQUEST_ID,
        )
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _index: claim_browser_request(
                    request, claim_directory=tmp_path, now=1001
                ),
                range(8),
            )
        )

    assert results.count(True) == 1
    assert results.count(False) == 7


def test_claim_storage_error_is_reported(tmp_path) -> None:
    request = parse_browser_request(
        make_overlay_uri(
            browser="chrome",
            requested_at=1000,
            request_id=REQUEST_ID,
        )
    )
    blocked_directory = tmp_path / "claims"
    blocked_directory.write_text("not a directory", encoding="utf-8")

    with pytest.raises(BrowserProtocolError, match="richiesta monouso"):
        claim_browser_request(
            request, claim_directory=blocked_directory, now=1001
        )


@pytest.mark.parametrize(
    "value",
    (
        "https://example.com",
        "uvt://open?url=https%3A%2F%2Fexample.com",
        "uvt://translate",
        "uvt://translate?url=file%3A%2F%2FC%3A%2Fvideo.mp4",
        "uvt://translate?url=https%3A%2F%2Fa.test&url=https%3A%2F%2Fb.test",
        "uvt://translate?url=https%3A%2F%2Fa.test&extra=1",
        "uvt://translate?url=https%3A%2F%2Fa.test&browser=safari",
        "uvt://translate?url=https%3A%2F%2Fa.test&browser=chrome&browser=edge",
        "uvt://translate?url=https%3A%2F%2Fa.test&requested_at=ieri",
        "uvt://translate?url=https%3A%2F%2Fa.test&request_id=not-a-uuid",
    ),
)
def test_translate_uri_rejects_unsafe_or_ambiguous_values(value: str) -> None:
    with pytest.raises(BrowserProtocolError):
        parse_translate_uri(value)


def test_protocol_command_quotes_executable_script_and_uri() -> None:
    command = protocol_command(
        Path("C:/Program Files/UVT/python.exe"),
        Path("C:/Program Files/UVT/universal_video_translator.py"),
    )
    assert '"C:\\Program Files\\UVT\\python.exe"' in command
    assert '"C:\\Program Files\\UVT\\universal_video_translator.py"' in command
    assert command.endswith('"%1"')


def test_protocol_command_for_packaged_executable_has_no_source_script() -> None:
    command = protocol_command(
        Path("C:/Program Files/UVT/UniversalVideoTranslator.exe")
    )
    assert command == (
        '"C:\\Program Files\\UVT\\UniversalVideoTranslator.exe" "%1"'
    )


class _Key:
    def __init__(self, path: str) -> None:
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class _Registry:
    HKEY_CURRENT_USER = object()
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def CreateKey(self, _root, path: str) -> _Key:
        return _Key(path)

    def SetValueEx(self, key: _Key, name: str, _reserved, _kind, value: str) -> None:
        self.values[(key.path, name)] = value


def test_register_protocol_uses_current_user_and_exact_command() -> None:
    registry = _Registry()
    command = '"C:\\UVT\\UniversalVideoTranslator.exe" "%1"'
    assert register_protocol(command, registry) == command
    assert registry.values[(r"Software\Classes\uvt", "URL Protocol")] == ""
    assert registry.values[
        (r"Software\Classes\uvt\shell\open\command", "")
    ] == command


def test_extension_keeps_source_tab_and_uses_minimum_permission() -> None:
    root = Path(__file__).parents[1]
    worker = (root / "browser_extension" / "service-worker.js").read_text(
        encoding="utf-8"
    )
    manifest = json.loads(
        (root / "browser_extension" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert "chrome.tabs.update" not in worker
    assert "tab.url" not in worker
    assert "chrome.tabs.create" in worker
    assert "uvt://${command}" in worker
    assert "uvt://translate" not in worker
    assert "requested_at" in worker
    assert "request_id" in worker
    assert "active: false" in worker
    assert "setTimeout" not in worker
    assert "chrome.alarms" not in worker
    assert "chrome.tabs.remove" not in worker
    assert "MIN_LAUNCH_INTERVAL_MS" in worker
    assert manifest["permissions"] == ["storage"]
    assert manifest["action"]["default_popup"] == "popup.html"
