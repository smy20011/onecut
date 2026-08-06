from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment


def transcribe(
    file, model_size="small", device="cpu", compute_type="int8"
) -> list[Segment]:
    model_size = "small"
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(file, beam_size=5)
    return list(segments)


def codegen(segments: list[Segment]):
    pass
