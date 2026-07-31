import json
from pathlib import Path

from uvt.cache import TranslationCache
from uvt.paths import app_paths
from uvt.settings import AppSettings, SettingsStore


def test_app_paths_share_absolute_local_root(tmp_path) -> None:
    paths = app_paths(tmp_path)

    assert paths.settings.parent == tmp_path
    assert paths.translation_cache.parent == tmp_path / "cache"
    assert paths.routing_lease.parent == tmp_path / "state"
    assert paths.browser_requests.parent == tmp_path


def test_settings_roundtrip_and_validation(tmp_path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    expected = AppSettings(
        ollama_model="qwen3:4b",
        language="inglese",
        rate=210,
        routing_browser="chrome",
        dark_mode=False,
        overlay_alpha=0.75,
    )

    store.save(expected)

    assert store.load() == expected
    assert json.loads(store.path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_invalid_settings_values_fall_back_individually(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"schema_version": 1, "rate": 999, "routing_browser": "safari"}),
        encoding="utf-8",
    )

    loaded = SettingsStore(path).load()

    assert loaded.rate == 185
    assert loaded.routing_browser == "firefox"


def test_translation_cache_default_is_not_working_directory(monkeypatch, tmp_path) -> None:
    local = tmp_path / "local"
    working = tmp_path / "working"
    working.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.chdir(working)

    cache = TranslationCache()
    cache.put("model", "auto", "Hello", "Ciao")

    assert cache.path == local / "UniversalVideoTranslator" / "cache" / "translations-v5.json"
    assert cache.path.is_file()
    assert not (working / ".uvt-cache.json").exists()


def test_explicit_translation_cache_path_is_supported(tmp_path) -> None:
    cache = TranslationCache(tmp_path / "custom.json")
    cache.put("model", "auto", "Hello", "Ciao")

    assert cache.get("model", "auto", "Hello") == "Ciao"
    assert cache.path.is_file()
