from dataclasses import dataclass, field
from enum import StrEnum
from functools import reduce
from typing import cast
from networkx import DiGraph, MultiDiGraph
import networkx
from .clips import Clip

class Cap(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"


@dataclass(frozen=True)
class LabelNode:
    node_id: str
    cap: Cap


@dataclass(frozen=True)
class FilterNode:
    node_id: str
    filter_str: str
    filter_id: str = ""


GraphNode = LabelNode | FilterNode
IRGraph = MultiDiGraph[GraphNode]

@dataclass
class SubGraph:
    graph: IRGraph = field(default_factory=IRGraph)
    outputs: list[LabelNode] = field(default_factory=list)

    def add_chain(self, *nodes: GraphNode) -> LabelNode:
        for f, t in zip(nodes, nodes[1:]):
            self.graph.add_edge(f, t)
        assert isinstance(nodes[-1], LabelNode), (
            "Last one in the chain must be label node"
        )
        return nodes[-1]

    def get(self, cap: Cap) -> LabelNode:
        for node in self.outputs:
            if node.cap == cap:
                return node
        raise ValueError(f"Cannot find cap: {cap}")

    def has(self, cap: Cap) -> bool:
        for node in self.outputs:
            if node.cap == cap:
                return True
        return False

# "Raw graphs" that can be directly translated to
# FFMpeg filter. FFMpeg have several limitations of filters:
# 1. All label can only be consumed once.
# 2. No free label at the end.

@dataclass(frozen=True)
class RawFilterLabel:
    label: str

@dataclass(frozen=True)
class RawFilter:
    filter: str

RawFilterGraph = MultiDiGraph[RawFilterLabel | RawFilter]

# Transform clip subgraphs into a Low Level Raw Filter Graph
def compile(root_clip: Clip):
    clip_subgraph: dict[str, SubGraph] = {}

    def dfs_clips(clip: Clip) -> SubGraph:
        if clip.id in clip_subgraph:
            return clip_subgraph[clip.id]
        sub_graphs = []
        for c in clip.deps():
            sub_graphs.append(dfs_clips(c))
        clip_subgraph[clip.id] = clip.filter_graph(sub_graphs)
        return clip_subgraph[clip.id] 

    root_sub_graph = dfs_clips(root_clip)

    # Combine all the graphs
    total_graph: IRGraph = networkx.compose_all([s.graph for s in clip_subgraph.values()])
