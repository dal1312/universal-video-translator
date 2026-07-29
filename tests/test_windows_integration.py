from pathlib import Path

from uvt.windows_integration import launch_command


def test_frozen_launch_command() -> None:
    command = launch_command(
        executable=Path("C:/Program Files/UVT/UVT.exe"),
        frozen=True,
    )

    assert command.endswith('" --minimized')
    assert "UVT.exe" in command


def test_development_launch_command_contains_script() -> None:
    command = launch_command(
        executable=Path("C:/Python/python.exe"),
        script=Path("C:/UVT/universal_video_translator.py"),
        frozen=False,
    )

    assert "pythonw" in command.casefold()
    assert "universal_video_translator.py" in command
