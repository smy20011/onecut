from abc import ABC, abstractclassmethod, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import time, timedelta, datetime
from typing import ClassVar, Sequence
from argparse import ArgumentParser
from pathlib import Path
from itertools import groupby
import subprocess
import math


def srt_timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    sec = total_sec % 60
    total_min = total_sec // 60
    minutes = total_min % 60
    hours = total_min // 60
    return f"{hours:02}:{minutes:02}:{sec:02},{ms:03}"


@dataclass
class SubTitle:
    start: float
    end: float
    text: str

@dataclass(frozen=True)
class FilterLabel:
    filter_type: str
    id: int

    def __str__(self) -> str:
        return f"{self.filter_type}{self.id}"

@dataclass
class Filter:
    inputs: list[FilterLabel] = field(default_factory=list)
    outputs: list[FilterLabel] = field(default_factory=list)
    text: str = ""

    def __str__(self) -> str:
        inputs = "".join([f"[{l}]" for l in self.inputs])
        outputs = "".join([f"[{l}]" for l in self.outputs])
        return f"{inputs}{self.text}{outputs};"

@dataclass
class Clip(ABC):
    COUNTER: ClassVar[int] = 0
    id: int = field(init=False)

    def __post_init__(self):
        self.id = Clip.COUNTER
        Clip.COUNTER += 1

    @property
    @abstractmethod
    def len(self) -> float:
        pass

    @property
    @abstractmethod
    def subtitles(self) -> list[SubTitle]:
        """Return a list of subtitles respect to the start of the clip."""
        pass

    @property
    @abstractmethod
    def filters(self) -> list[Filter]:
        pass

    @property
    def v(self) -> FilterLabel:
        return FilterLabel("v", self.id)

    @property
    def a(self) -> FilterLabel:
        return FilterLabel("a", self.id)

    @property
    def deps(self) -> Sequence['Clip']:
        return []

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class Movie(Clip):
    filename: str
    length: float = 9999.0
    _subtitles: list[SubTitle] = field(default_factory=list)

    @property
    def len(self) -> float:
        return self.length

    @property
    def subtitles(self) -> list[SubTitle]:
        return self._subtitles

    @property
    def filters(self) -> list[Filter]:
        return [
            Filter([], [self.v], f"movie=filename={self.filename}"),
            Filter([], [self.a], f"amovie=filename={self.filename}"),
        ]

    def clip(
        self, start: float, end: float, subtitle: str | None = None
    ) -> "MovieClip":
        if subtitle:
            self._subtitles.append(SubTitle(start, end, subtitle))
            return MovieClip(self, start, end, [SubTitle(0, end - start, subtitle)])
        return MovieClip(self, start, end)


@dataclass
class MovieClip(Clip):
    movie: Movie
    start: float
    end: float
    _subtitles: list[SubTitle] = field(default_factory=list)

    @property
    def len(self) -> float:
        return self.end - self.start

    @property
    def subtitles(self) -> list[SubTitle]:
        return self._subtitles

    @property
    def filters(self) -> list[Filter]:
        return [
            Filter([self.movie.v], [self.v], f"trim={self.start:.2f}:{self.end:.2f},setpts=PTS-STARTPTS"),
            Filter([self.movie.a], [self.a], f"atrim={self.start:.2f}:{self.end:.2f},asetpts=PTS-STARTPTS")
        ]

    @property
    def deps(self) -> Sequence['Clip']:
        return [self.movie]


@dataclass
class Seq(Clip):
    children: Sequence[Clip]

    @property
    def len(self) -> float:
        return sum([c.len for c in self.children])

    @property
    def subtitles(self) -> list[SubTitle]:
        timestamp = 0
        result = []
        for c in self.children:
            for s in c.subtitles:
                result.append(SubTitle(s.start + timestamp, s.end + timestamp, s.text))
            timestamp += c.len
        return result

    @property
    def filters(self) -> list[Filter]:
        inputs = []
        for c in self.children:
            inputs.extend([c.v, c.a])
        return [Filter(inputs, [self.v, self.a], f"concat=n={len(self.children)}:v=1:a=1")]

    @property
    def deps(self) -> Sequence['Clip']:
        return self.children



def seq(*clips: Clip):
    c: Sequence[Clip] = clips
    return Seq(c)


def ffmpeg_filter(clip: Clip) -> str:
    filters: list[Filter] = []

    visited = set()
    def dfs_clips(clip: Clip):
        if clip.id in visited:
            return
        for dep in clip.deps:
            dfs_clips(dep)
        filters.extend(clip.filters)
        visited.add(clip.id)
    dfs_clips(clip)

    # We need to insert split node if a input label is
    # used more than twice.
    input_labels: dict[FilterLabel, list[Filter]] = defaultdict(list)
    for f in filters:
        for l in f.inputs:
            input_labels[l].append(f)

    result = []
    for f in filters:
        result.append(f)
        for l in f.outputs:
            n = len(input_labels[l])
            if n > 1:
                outputs = [
                    FilterLabel(f"split{idx}_{l.filter_type}", l.id)
                    for idx in range(n)
                ]
                text = "split" if l.filter_type == "v" else "asplit"
                result.append(Filter([l], outputs, f"{text}={n}"))
                # Rewrite all the filter that depends on the label
                for filter_rewrite, new_label in zip(input_labels[l], outputs):
                    for idx, old_label in enumerate(filter_rewrite.inputs):
                        if old_label == l:
                            filter_rewrite.inputs[idx] = new_label
    return "\n".join(str(r) for r in result)

# For AI: If you are editing the subs, you want to edit it
# only by one instead of editing everyting at one time.
# Use remove_subs to remove unnecessary subs, like
# remove_subs(movie.all_subtitles, [SUB_1, SUB_2])
# Feel free to create your own helper function.

# fmt: off
def timeline() -> Clip:
# BEGIN
    movie = Movie("a.mp4")
    return seq(
        movie.clip(0, 1, "Sub1"), 
        movie.clip(2, 3, "Sub2")
    )
# END


def generate_video(dest: str):
    clip = timeline()
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-filter_complex", ffmpeg_filter(clip),
            "-map", f"[{clip.v}]",
            "-map", f"[{clip.a}]",
            "-c:v", "libx264",
            "-crf", "20",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "192k",
            dest,
        ],
        check=True
    )
    # fmt: on


def generate_subtitle(dest: str):
    subtitles = timeline().subtitles
    with open(dest, "w", encoding="utf-8") as f:
        for idx, subtitle in enumerate(subtitles, 1):
            start = srt_timestamp(subtitle.start)
            end = srt_timestamp(subtitle.end)
            print(idx, file=f)
            print(f"{start} --> {end}", file=f)
            print(subtitle.text, file=f)
            print("", file=f)


def print_filters(unused_args):
    print(ffmpeg_filter(timeline()))


def main():
    parser = ArgumentParser(f"Movie Generator")
    parser.set_defaults(func=None)
    sub_parsers = parser.add_subparsers()
    video_parser = sub_parsers.add_parser(
        "video", description="Only generate the video file."
    )
    video_parser.add_argument(
        "--output_file", help="Path of the output video.", default="render.mp4"
    )
    video_parser.set_defaults(func=generate_video)
    subtitle_parser = sub_parsers.add_parser(
        "subtitle", description="Only generate the srt file."
    )
    subtitle_parser.add_argument(
        "--output_file", help="Path of the output srt file.", default="render.srt"
    )
    sub_parsers.add_parser(
        "print_filter", description="Only print out fitlers"
    ).set_defaults(func=print_filters)

    args = parser.parse_args()
    if not args.func:
        generate_video("render.mp4")
        generate_subtitle("render.srt")
    elif args.func == print_filters:
        args.func(args)
    else:
        args.func(args.output_file)


if __name__ == "__main__":
    main()
