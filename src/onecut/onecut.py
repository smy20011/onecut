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
    movie_len = max([s.end for s in segments], default=0.0)
    code = f"    movie = Movie({repr(filename)}, {movie_len})\n"
    code += "    return seq(\n"
    for idx, segment in enumerate(segments):
        assert segment.words
        start_time = segment.words[0].start
        end_time = segment.words[-1].end
        code += f"        movie.clip(start={start_time}, end={end_time}, subtitle={repr(segment.text.strip())})\n"
    code += "    )\n"
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input filename")
    parser.add_argument("output", help="Output filename", nargs="?")
    opt = parser.parse_args()

    print(f"Transcribing file: {opt.input}")
    segments = transcribe(opt.input)
    with open(Path(__file__).parent / "example.py", encoding="utf-8") as f:
        example = f.read()
    code = re.sub(
        "# BEGIN.*# END", codegen(opt.input, segments), example, flags=re.DOTALL
    )

    if opt.output:
        output_file = opt.output
    else:
        output_file = Path(opt.input).with_suffix(".py")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Transcribed subtitles & generated code is written to {output_file}")


if __name__ == "__main__":
    main()
