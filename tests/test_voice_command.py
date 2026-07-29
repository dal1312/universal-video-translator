from uvt.voice_command import VoiceCommandRecorder


def test_voice_duration_is_clamped() -> None:
    assert VoiceCommandRecorder(duration=0.1).duration == 2.0
    assert VoiceCommandRecorder(duration=99).duration == 12.0
