import json

from uvt.plugins import PluginManager


def test_builtin_plugin_renders_prompt(tmp_path) -> None:
    manager = PluginManager(tmp_path)
    prompt = manager.render(
        "universal-translate", "italian", text="Hello"
    )
    assert "italiano" in prompt


def test_external_declarative_plugin(tmp_path) -> None:
    (tmp_path / "custom.json").write_text(
        json.dumps(
            {
                "id": "custom-plugin",
                "name": "Custom",
                "commands": [
                    {
                        "id": "inspect-text",
                        "title": "Inspect",
                        "prompt": "Analizza: {text}",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manager = PluginManager(tmp_path)

    assert manager.render(
        "custom-plugin", "inspect-text", text="ABC"
    ) == "Analizza: ABC"
