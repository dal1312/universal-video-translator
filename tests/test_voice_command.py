from uvt.voice_command import VoiceCommandRecorder


def test_voice_duration_is_clamped() -> None:
    assert VoiceCommandRecorder(duration=0.1).duration == 2.0
    assert VoiceCommandRecorder(duration=99).duration == 12.0


def test_voice_model_can_be_changed() -> None:
    recorder = VoiceCommandRecorder(model_name="small")
    recorder._model = object()

    recorder.set_model("base")

    assert recorder.model_name == "base"
    assert recorder._model is None
