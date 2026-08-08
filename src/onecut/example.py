from abc import ABC, abstractclassmethod, abstractmethod
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Sequence
from argparse import ArgumentParser
from pathlib import Path
from itertools import groupby
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
    all_subtitles: list[Subtitle]


def ffmpeg_filter(clips: Sequence[ClipLike]) -> str:
    result = ""
    concat_input = ""
    for idx, clip in enumerate(clips):
        start = f"{clip.get_start():.2f}"
        end = f"{clip.get_end():.2f}"
        result += f"[0:v]trim={start}:{end},setpts=PTS-STARTPTS[v{idx}];\n"
        result += f"[0:a]atrim={start}:{end},asetpts=PTS-STARTPTS[a{idx}];\n"
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


def sub(text: str, start: float, end: float):
    subtitle = Subtitle(len(movie.all_subtitles), Clip(start, end), text)
    movie.all_subtitles.append(subtitle)
    return subtitle


def remove_subs(subtitles: list[Subtitle], to_remove: list[Subtitle]) -> list[Clip]:
    idx_set = set([s.index for s in to_remove])
    subtitle_grouped = groupby(subtitles, lambda s: s.index not in idx_set)
    result = []
    for keep, subs in subtitle_grouped:
        if keep:
            subs = list(subs)
            result.append(subs[0].to(subs[-1]))
    return result


# For AI: If you are editing the subs, you want to edit it
# only by one instead of editing everyting at one time.
# Use remove_subs to remove unnecessary subs, like
# remove_subs(movie.all_subtitles, [SUB_1, SUB_2])
# Feel free to create your own helper function.

# BEGIN
movie = Movie("a.txt", [])
SUB_1 = sub("Sub1", 0, 1)
SUB_2 = sub("Sub2", 1, 2)
SUB_3 = sub("Sub3", 2, 3)

FINAL_CLIPS = [SUB_1.to(SUB_3)]
# END


def generate_video(dest=None):
    if not dest:
        dest = Path(movie.filename).with_suffix(".cut.mp4")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            movie.filename,
            "-filter_complex",
            ffmpeg_filter(FINAL_CLIPS),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-crf",
            "20",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            dest,
        ],
    )


def generate_subtitle(dest=None):
    if not dest:
        dest = Path(movie.filename).with_suffix(".srt")

    with open(dest, "w") as f:
        for idx, subtitle in enumerate(find_subs(FINAL_CLIPS)):
            start = ClipLike.srt_timestamp(subtitle.get_start())
            end = ClipLike.srt_timestamp(subtitle.get_end())
            print(idx, file=f)
            print(f"{start} --> {end}", file=f)
            print(subtitle.text, file=f)
            print("", file=f)


def print_filters(unused_args):
    print(ffmpeg_filter(FINAL_CLIPS))


def main():
    parser = ArgumentParser(f"Generator for {movie.filename}")
    parser.set_defaults(func=None)
    sub_parsers = parser.add_subparsers()
    video_parser = sub_parsers.add_parser(
        "video", description="Only generate the video file."
    )
    video_parser.add_argument(
        "--output_file", help="Path of the output video.", required=False
    )
    video_parser.set_defaults(func=generate_video)
    subtitle_parser = sub_parsers.add_parser(
        "subtitle", description="Only generate the srt file."
    )
    subtitle_parser.add_argument(
        "--output_file", help="Path of the output srt file.", required=False
    )
    subtitle_parser.set_defaults(func=generate_subtitle)
    sub_parsers.add_parser(
        "print_filter", description="Only print out fitlers"
    ).set_defaults(func=print_filters)

    args = parser.parse_args()
    if not args.func:
        generate_video()
        generate_subtitle()
    else:
        args.func(getattr(args, "output_file", ""))


if __name__ == "__main__":
    main()
