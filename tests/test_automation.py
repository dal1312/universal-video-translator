import pytest

from uvt.automation import (
    AutomationError,
    AutomationPlan,
    MacroStore,
)


def test_plan_validates_and_describes_actions() -> None:
    plan = AutomationPlan.from_payload(
        {
            "title": "Apri editor",
            "actions": [
                {"type": "open_app", "app": "notepad"},
                {"type": "wait", "seconds": 1},
                {"type": "type_text", "text": "Ciao"},
            ],
        }
    )
    assert len(plan.actions) == 3
    assert "Apri applicazione: notepad" in plan.description()


def test_plan_rejects_shell_actions() -> None:
    with pytest.raises(AutomationError, match="non consentita"):
        AutomationPlan.from_payload(
            {
                "title": "Pericolosa",
                "actions": [{"type": "shell", "text": "dir"}],
            }
        )


def test_macro_store_roundtrip(tmp_path) -> None:
    store = MacroStore(tmp_path / "macros.json")
    plan = AutomationPlan.from_payload(
        {
            "title": "Browser",
            "actions": [
                {"type": "open_url", "url": "https://example.com"}
            ],
        }
    )
    store.save("Apri esempio", plan)

    assert store.names() == ["Apri esempio"]
    assert store.load("Apri esempio") == plan
