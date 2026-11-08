from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property
from typing import Self, Any, Callable, Sequence
from uuid import UUID, uuid4
import tempfile


@dataclass(frozen=True)
class Filter:
    name: str
    start: float | None = None
    end: float | None = None
    args: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def subtitle(
        clip: Clip,
        font="Source Han Sans CN",
        font_size=28,
        primary_color="&H00E8E8E8",
        outline_color="&H00000000",
        border_style="1",
        outline=1.8,
        margin_v=38,
    ):
        style = f"FontName={font},FontSize={font_size},PrimaryColour={primary_color},OutlineColour={outline_color},BorderStyle={border_style},Outline={outline},MarginV={margin_v}"
        subs = Subtitle.gen_srt(clip.subs())
        with tempfile.NamedTemporaryFile("w", prefix="subtitle", delete=False) as f:
            f.write(subs)
        return Filter(
            name="avfilter.subtitles",
            args={"av.filename": f.name, "position": "filter", "av.force_style": style},
        )


@dataclass(frozen=True)
class Transition:
    name: str
    start: float | None = None
    end: float | None = None
    args: dict[str, str] = field(default_factory=dict)


@dataclass
class Clip(ABC):
    """A clip maps a producer node(producer, playlist, tractor) in MLT framework"""

    filters: list[Filter] = field(default_factory=list, kw_only=True)

    @cached_property
    def id(self) -> str:
        return str(uuid4())

    @abstractmethod
    def len(self) -> float:
        pass

    @abstractmethod
    def deps(self) -> list[Clip]:
        pass

    def subs(self) -> list[Subtitle]:
        return []

    def filter(self, filter: Filter) -> Self:
        self.filters.append(filter)
        return self

    def sub_clip(
        self, start: float, end: float, subtitle: str | None = None
    ) -> SubClip:
        if subtitle:
            return SubClip(self, start, end, [Subtitle(0, end - start, subtitle)])
        else:
            return SubClip(self, start, end, [])

    def overlay(self, overlay: Clip):
        return Overlay(source=self, _overlay=overlay)


@dataclass
class Source(Clip):
    filename: str
    length: float

    def deps(self) -> list[Clip]:
        return []

    def len(self):
        return self.length


@dataclass
class Subtitle:
    start: float
    end: float
    text: str

    @staticmethod
    def srt_timestamp(seconds: float) -> str:
        total_ms = round(seconds * 1000)
        ms = total_ms % 1000
        total_sec = total_ms // 1000
        sec = total_sec % 60
        total_min = total_sec // 60
        minutes = total_min % 60
        hours = total_min // 60
        return f"{hours:02}:{minutes:02}:{sec:02},{ms:03}"

    @staticmethod
    def gen_srt(subtitles: list["Subtitle"]) -> str:
        result = ""
        for idx, subtitle in enumerate(subtitles, 1):
            start = Subtitle.srt_timestamp(subtitle.start)
            end = Subtitle.srt_timestamp(subtitle.end)
            result += f"{idx}\n"
            result += f"{start} --> {end}\n"
            result += f"{subtitle.text}\n\n"
        return result


@dataclass
class SubClip[T: Clip](Clip):
    """A clip with subtitle data."""

    source: T
    start: float
    end: float
    subtitles: list[Subtitle] = field(default_factory=list)

    def len(self) -> float:
        return self.end - self.start

    def deps(self) -> list[Clip]:
        return [self.source]

    def subs(self) -> list[Subtitle]:
        return self.subtitles

    def combine(*clips: SubClip) -> SubClip:
        """Combine all small clips together without jump cut"""
        subtitles = []
        first = clips[0]
        # make sure all the clips are sorted and have same source
        for f, t in zip(clips, clips[1:]):
            assert t.source.id == first.source.id
            assert f.start <= f.end <= t.start <= t.end
            assert t.filters == first.filters

        for c in clips:
            delta = c.start - first.start
            for sub in c.subtitles:
                subtitles.append(Subtitle(sub.start + delta, sub.end + delta, sub.text))

        return SubClip(
            first.source,
            clips[0].start,
            clips[-1].end,
            subtitles,
            filters=first.filters,
        )


@dataclass
class Concat(Clip):
    inputs: Sequence[Clip] = field(default_factory=list)

    def len(self) -> float:
        return sum([i.len() for i in self.inputs])

    def deps(self) -> list[Clip]:
        return list(self.inputs)

    def subs(self) -> list[Subtitle]:
        subs = []
        timestamp = 0
        for input in self.inputs:
            for s in input.subs():
                subs.append(Subtitle(s.start + timestamp, s.end + timestamp, s.text))
            timestamp += input.len()
        return subs


@dataclass
class Overlay(Clip):
    DEFAULT_TRANSITION = Transition("affine", args={"a_track": "0", "b_track": "1"})
    source: Clip
    _overlay: Clip
    transitions: list[Transition] = field(
        default_factory=lambda: [Overlay.DEFAULT_TRANSITION]
    )

    def len(self) -> float:
        return self.source.len()

    def subs(self) -> list[Subtitle]:
        return self.source.subs()

    def deps(self) -> list[Clip]:
        return [self.source, self._overlay]

    def transition(self, transition: Transition):
        self.transitions.append(transition)
        return self
