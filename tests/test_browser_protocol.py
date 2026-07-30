from pathlib import Path

import pytest

from uvt.browser_protocol import (
    BrowserProtocolError,
    make_translate_uri,
    parse_translate_uri,
    protocol_command,
    register_protocol,
)


def test_translate_uri_roundtrip_preserves_complex_url() -> None:
    url = "https://example.com/watch?v=uno&lang=it#parte"
    assert parse_translate_uri(make_translate_uri(url)) == url


@pytest.mark.parametrize(
    "value",
    (
        "https://example.com",
        "uvt://open?url=https%3A%2F%2Fexample.com",
        "uvt://translate",
        "uvt://translate?url=file%3A%2F%2FC%3A%2Fvideo.mp4",
        "uvt://translate?url=https%3A%2F%2Fa.test&url=https%3A%2F%2Fb.test",
        "uvt://translate?url=https%3A%2F%2Fa.test&extra=1",
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
