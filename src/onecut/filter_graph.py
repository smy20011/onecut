from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import StrEnum
from functools import reduce
from typing import TYPE_CHECKING, cast
from uuid import uuid4
from networkx import DiGraph, MultiDiGraph, reverse
import networkx as nx

if TYPE_CHECKING:
    from .clips import Clip

class Cap(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"

    def filter_prefix(self):
        if self == Cap.AUDIO:
            return "a"
        return ""


@dataclass(frozen=True)
class LabelNode:
    node_id: str
    cap: Cap


@dataclass(frozen=True)
class FilterNode:
    node_id: str
    filter_str: str


type GraphNode = LabelNode | FilterNode
type IRGraph = MultiDiGraph[GraphNode]

@dataclass
class SubGraph:
    graph: IRGraph = field(default_factory=MultiDiGraph)
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
    cap: Cap

@dataclass(frozen=True)
class RawFilter:
    filter: str
    id: str = field(default_factory=lambda: str(uuid4()))

type RawGraphNode = RawFilterLabel | RawFilter
type RawFilterGraph = MultiDiGraph[RawFilterLabel | RawFilter]

# Transform clip subgraphs into a Low Level Raw Filter Graph
def compile(root_clip: Clip) -> RawFilterGraph:
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
    total_graph: IRGraph = nx.compose_all([s.graph for s in clip_subgraph.values()])
    reachable_nodes = set(root_sub_graph.outputs)
    for node in root_sub_graph.outputs:
        reachable_nodes |= nx.ancestors(total_graph, node)
    reachable = total_graph.subgraph(reachable_nodes)

    filter_graph: RawFilterGraph = MultiDiGraph()
    node_map: dict[LabelNode, RawFilterLabel] = {}
    for_consume: dict[LabelNode, deque[RawFilterLabel]] = defaultdict(deque)
    # Create raw filter graph label nodes.
    for node in list(reachable):
        if isinstance(node, LabelNode):
            u = RawFilterLabel(f"{node.cap}_{len(node_map)}", node.cap)
            node_map[node] = u
            filter_graph.add_node(u)
            # Create splitted nodes
            if reachable.out_degree(node) > 1:
                split_filter = RawFilter(f"{node.cap.filter_prefix()}split={reachable.out_degree(node)}")
                filter_graph.add_edge(u, split_filter)
                for i in range(reachable.out_degree(node)):
                    for_consume[node].append(RawFilterLabel(f"{u.label}_{i}", u.cap))
                    filter_graph.add_edge(split_filter, for_consume[node][-1])
            else:
                for_consume[node].append(u)

    # Create all filter nodes
    for f in nx.topological_sort(reachable):
        if isinstance(f, FilterNode):
            node = RawFilter(f.filter_str)
            for u in reachable.predecessors(f):
                filter_graph.add_edge(for_consume[cast(LabelNode, u)].popleft(), node)
            for v in reachable.successors(f):
                filter_graph.add_edge(node, node_map[cast(LabelNode, v)])

    return filter_graph

def to_ffmpeg_filter(filter_graph: RawFilterGraph) -> str:
    result = ""
    for node in nx.topological_sort(filter_graph):
        if isinstance(node, RawFilter):
            prev_str = ""
            for prev in filter_graph.predecessors(node):
                assert isinstance(prev, RawFilterLabel)
                prev_str += f"[{prev.label}]"

            succ_str = ""
            for succ in filter_graph.successors(node):
                assert isinstance(succ, RawFilterLabel)
                succ_str += f"[{succ.label}]"

            result += f"{prev_str}{node.filter}{succ_str};\n"
    return result
