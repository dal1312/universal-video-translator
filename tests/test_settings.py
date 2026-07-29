import json

from uvt.settings import AppSettings, ConfigStore


def test_settings_round_trip(tmp_path) -> None:
    store = ConfigStore(tmp_path / "settings.json")
    expected = AppSettings(
        ollama_model="qwen3:4b",
        rate=210,
        dark_mode=False,
        minimize_to_tray=False,
    )

    store.save(expected)

    assert store.load() == expected


def test_settings_recover_from_invalid_json(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{invalid", encoding="utf-8")

    assert ConfigStore(path).load() == AppSettings()


def test_settings_clamp_values(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"rate": 999}), encoding="utf-8")

    assert ConfigStore(path).load().rate == 260
