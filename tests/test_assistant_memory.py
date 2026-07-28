from uvt.assistant_memory import AssistantMemory


def test_assistant_memory_roundtrip(tmp_path) -> None:
    memory = AssistantMemory(tmp_path / "memory.sqlite3")
    memory.add("Browser", "Spiega", "Testo visibile", "Risposta")

    entries = memory.recent()

    assert len(entries) == 1
    assert entries[0].window_title == "Browser"
    assert entries[0].answer == "Risposta"
    assert memory.conversation_context() == [("Spiega", "Risposta")]


def test_assistant_memory_clear(tmp_path) -> None:
    memory = AssistantMemory(tmp_path / "memory.sqlite3")
    memory.add("Editor", "Correggi", "test", "Test")

    memory.clear()

    assert memory.recent() == []
