from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
from pathlib import Path
import re
import argparse


def transcribe(
    file, model_size="small", device="cpu", compute_type="int8"
) -> list[Segment]:
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        file,
        beam_size=5,
        word_timestamps=True,
    )
    return list(segments)


def codegen(filename: str, segments: list[Segment]):
    code = f"movie = Movie({repr(filename)}, [])\n"
    for idx, segment in enumerate(segments):
        assert segment.words
        words = segment.words
        code += f"SUB_{idx + 1} = sub({repr(segment.text.strip())}, {words[0].start}, {words[-1].end})\n"
    code += f"FINAL_CLIPS = [SUB_{1}.to(SUB_{len(segments)})]\n"
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="Input filename")
    parser.add_argument("output", help="Output filename")
    opt = parser.parse_args()

    segments = transcribe(opt.filename)
    example = open(Path(__file__).parent / "example.py").read()
    code = re.sub(
        "# BEGIN.*# END", codegen(opt.filename, segments), example, flags=re.DOTALL
    )

    with open(opt.output, "w") as f:
        f.write(code)


if __name__ == "__main__":
    main()
