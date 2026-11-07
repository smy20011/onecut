from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property
from typing import Self, Any, Callable, Sequence
from uuid import UUID, uuid4
from enum import StrEnum

from networkx.algorithms.flow.maxflow import default_flow_func

from .filter_graph import SubGraph, FilterNode, LabelNode, Cap


class Clip(ABC):
    @cached_property
    def id(self) -> str:
        return str(uuid4())

    @abstractmethod
    def len(self) -> float:
        pass

    @abstractmethod
    def caps(self) -> set[Cap]:
        pass

    @abstractmethod
    def deps(self) -> list[Clip]:
        pass

    @abstractmethod
    def filter_graph(self, inputs: list[SubGraph]) -> SubGraph:
        pass

    def subs(self) -> list[Subtitle]:
        return []

    def filter(self, cap: Cap, filter_str: str) -> Filter[Self]:
        return Filter(self, cap, filter_str)

    def sub(self, start: float, end: float, subtitle: str | None = None) -> SubClip:
        if subtitle:
            return SubClip(self, start, end, [Subtitle(0, end - start, subtitle)])
        else:
            return SubClip(self, start, end, [])


@dataclass
class Filter[T: Clip](Clip):
    source: T
    cap: Cap
    filter_str: str

    def len(self) -> float:
        return self.source.len()

    def caps(self) -> set[Cap]:
        return self.source.caps()

    def deps(self) -> list[Clip]:
        return [self.source]

    def subs(self):
        return self.source.subs()

    def filter_graph(self, inputs: list[SubGraph]) -> SubGraph:
        return filter_subgraph(inputs[0], self.id, {self.cap: self.filter_str})


def filter_subgraph(input: SubGraph, id: str, filter_map: dict[Cap, str]) -> SubGraph:
    r = SubGraph()
    for output in input.outputs:
        if output.cap in filter_map:
            r.outputs.append(
                r.add_chain(
                    output,
                    FilterNode(id, filter_map[output.cap]),
                    LabelNode(id, output.cap),
                )
            )
        else:
            r.outputs.append(output)
    return r


@dataclass
class Movie(Clip):
    source: str
    _len: float
    _caps: set[Cap] = field(default_factory=lambda: {Cap.AUDIO, Cap.VIDEO})

    def len(self) -> float:
        return self._len

    def caps(self) -> set[Cap]:
        return self._caps

    def deps(self) -> list[Clip]:
        return []

    def filter_graph(self, inputs: list[SubGraph]) -> SubGraph:
        result = SubGraph()
        if Cap.VIDEO in self.caps():
            result.outputs.append(
                result.add_chain(
                    FilterNode(self.id, f"movie={self.source}"),
                    LabelNode(self.id, Cap.VIDEO),
                )
            )

        if Cap.AUDIO in self.caps():
            result.outputs.append(
                result.add_chain(
                    FilterNode(self.id, f"amovie={self.source}"),
                    LabelNode(self.id, Cap.AUDIO),
                )
            )
        return result


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
    def gen_srt(subtitles: list['Subtitle']) -> str:
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

    def caps(self) -> set[Cap]:
        return self.source.caps()

    def deps(self) -> list[Clip]:
        return [self.source]

    def filter_graph(self, inputs: list[SubGraph]) -> SubGraph:
        return filter_subgraph(
            inputs[0],
            self.id,
            {
                Cap.VIDEO: f"trim={self.start}:{self.end},setpts=PTS-STARTPTS",
                Cap.AUDIO: f"atrim={self.start}:{self.end},asetpts=PTS-STARTPTS",
            },
        )

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

        for c in clips:
            delta = c.start - first.start
            for sub in c.subtitles:
                subtitles.append(Subtitle(sub.start + delta, sub.end + delta, sub.text))

        return SubClip(first.source, clips[0].start, clips[-1].end, subtitles)


@dataclass
class Concat(Clip):
    inputs: Sequence[Clip] = field(default_factory=list)

    def __post_init__(self):
        for input in self.inputs:
            assert input.caps() == self.inputs[0].caps(), "All caps need to be same."

    def len(self) -> float:
        return sum([i.len() for i in self.inputs])

    def caps(self) -> set[Cap]:
        return self.inputs[0].caps()

    def deps(self) -> list[Clip]:
        return list(self.inputs)

    def filter_graph(self, inputs: list[SubGraph]) -> SubGraph:
        v = int(Cap.VIDEO in self.caps())
        a = int(Cap.AUDIO in self.caps())
        result = SubGraph()
        filter_node = FilterNode(self.id, f"concat=n={len(self.inputs)}:v={v}:a={a}")
        result.graph.add_node(filter_node)
        idx = 0
        for input in inputs:
            for cap in [Cap.VIDEO, Cap.AUDIO]:
                if cap in self.caps():
                    result.graph.add_edge(input.get(cap), filter_node, port=idx)
                    idx += 1
        if v:
            result.outputs.append(
                result.add_chain(filter_node, LabelNode(self.id, Cap.VIDEO))
            )
        if a:
            result.outputs.append(
                result.add_chain(filter_node, LabelNode(self.id, Cap.AUDIO))
            )
        return result

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
    source: Clip
    overlay: Clip
    options: dict[str, str]

    def __post_init__(self):
        assert Cap.VIDEO in self.source.caps(), "Souce must have video"
        assert Cap.VIDEO in self.overlay.caps(), "Overlay must have video"

    def len(self) -> float:
        return self.source.len()

    def caps(self) -> set[Cap]:
        return self.source.caps()

    def deps(self) -> list[Clip]:
        return [self.source, self.overlay]

    def filter_graph(self, inputs: list[SubGraph]) -> SubGraph:
        result = SubGraph()
        params = ":".join([f"{k}={v}" for k, v in self.options.items()])
        if params:
            params = "=" + params
        filter_node = FilterNode(self.id, f"overlay{params}")
        result.graph.add_edge(inputs[0].get(Cap.VIDEO), filter_node, port=0)
        result.graph.add_edge(inputs[1].get(Cap.VIDEO), filter_node, port=1)
        result.outputs.append(result.add_chain(filter_node, LabelNode(self.id, Cap.VIDEO)))
        if Cap.AUDIO in self.source.caps():
            result.outputs.append(inputs[0].get(Cap.AUDIO))
        return result

    def subs(self) -> list[Subtitle]:
        return self.source.subs()
