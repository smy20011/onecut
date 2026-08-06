from abc import ABC, abstractclassmethod, abstractmethod
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Sequence
from argparse import ArgumentParser
from pathlib import Path
import subprocess
import math


class ClipLike(ABC):
    @abstractmethod
    def get_start(self) -> float:
        pass

    @abstractmethod
    def get_end(self) -> float:
        pass

    def len(self) -> float:
        return self.get_end() - self.get_start()

    @staticmethod
    def srt_timestamp(seconds: float) -> str:
        (frac, seconds) = math.modf(seconds)
        seconds = int(seconds)
        microseconds = round(frac * 1000)
        minutes = (seconds // 60) % 60
        hours = seconds // 3600
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02},{microseconds:03}"


@dataclass
class Clip(ClipLike):
    # The start of this clip, measured in seconds
    start: float
    # The end of this clip, measured in seconds
    end: float

    def overlap(self, other: ClipLike) -> bool:
        return max(self.start, other.get_start()) < min(self.end, other.get_end())

    def merge(self, other: "Clip") -> "Clip":
        return Clip(min(self.start, other.start), max(self.end, other.end))

    def shift(self, delta: float) -> "Clip":
        return Clip(self.start + delta, self.end + delta)

    def get_start(self) -> float:
        return self.start

    def get_end(self) -> float:
        return self.end


@dataclass
class Subtitle(ClipLike):
    # Index number for this subtitle
    index: int
    # The clip associated with this subtitle
    clip: Clip
    # The text
    text: str

    def get_start(self) -> float:
        return self.clip.get_start()

    def get_end(self) -> float:
        return self.clip.get_end()

    def to(self, other: ClipLike) -> Clip:
        return Clip(
            min(self.get_start(), other.get_start()),
            max(self.get_end(), other.get_end()),
        )


@dataclass
class Movie:
    filename: str
    length: float
    all_subtitles: list[Subtitle]


def ffmpeg_filter(clips: Sequence[ClipLike]) -> str:
    result = ""
    concat_input = ""
    for idx, clip in enumerate(clips):
        start = f"{clip.get_start():.2f}"
        end = f"{clip.get_end():.2f}"
        result += f"[0:v]trim={start}:{end},setpts=PTS-STARTPTS[v{idx}];\n"
        result += f"[0:a]trim={start}:{end},setpts=PTS-STARTPTS[a{idx}];\n"
        concat_input += f"[v{idx}][a{idx}]"
    result += f"{concat_input}concat=n={len(clips)}:v=1:a=1[v][a]"
    return result


def find_subs(clips: Sequence[ClipLike]) -> list[Subtitle]:
    time = 0
    result = []
    for clip in clips:
        subs = [
            Subtitle(s.index, s.clip.shift(-clip.get_start() + time), s.text)
            for s in movie.all_subtitles
            if s.clip.overlap(clip)
        ]
        result.extend(subs)
        time += clip.len()
    return result


movie = Movie("a.txt", 100, [])


def sub(text: str, start: float, end: float):
    subtitle = Subtitle(len(movie.all_subtitles) + 1, Clip(start, end), text)
    movie.all_subtitles.append(subtitle)
    return subtitle


SUB_1 = sub("Sub1", 0, 1)
SUB_2 = sub("Sub2", 1, 2)
SUB_3 = sub("Sub3", 2, 3)

FINAL_CLIPS = [SUB_1.to(SUB_3)]


def generate_video(dest=None):
    if not dest:
        dest = Path(movie.filename).with_suffix(".mp4")

    subprocess.run(
        ["ffmpeg", "-i", movie.filename, "-vf", ffmpeg_filter(FINAL_CLIPS), dest],
    )


def generate_subtitle(dest=None):
    if not dest:
        dest = Path(movie.filename).with_suffix(".srt")

    with open(dest, "w") as f:
        for idx, subtitle in enumerate(find_subs(FINAL_CLIPS)):
            start = ClipLike.srt_timestamp(subtitle.get_start())
            end = ClipLike.srt_timestamp(subtitle.get_end())
            print(idx, file=f)
            print(f"{start} -> {end}", file=f)
            print(subtitle.text, file=f)


def print_filters(unused_args):
    print(ffmpeg_filter(FINAL_CLIPS))


def main():
    parser = ArgumentParser(f"Generator for {movie.filename}")
    parser.set_defaults(func=None)
    sub_parsers = parser.add_subparsers()
    sub_parsers.add_parser(
        "video", description="Only generate the video file."
    ).set_defaults(func=generate_video)
    sub_parsers.add_parser(
        "subtitle", description="Only generate the srt file."
    ).set_defaults(func=generate_subtitle)
    sub_parsers.add_parser(
        "print_filter", description="Only print out fitlers"
    ).set_defaults(func=print_filters)

    args = parser.parse_args()
    if not args.func:
        generate_video()
        generate_subtitle()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
