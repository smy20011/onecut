from dataclasses import dataclass, field
from enum import StrEnum
from functools import reduce
from typing import TYPE_CHECKING, cast
from networkx import DiGraph, MultiDiGraph, reverse
import networkx as nx

if TYPE_CHECKING:
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
    cap: Cap

@dataclass(frozen=True)
class RawFilter:
    filter: str

RawGraphNode = RawFilterLabel | RawFilter
RawFilterGraph = MultiDiGraph[RawFilterLabel | RawFilter]

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

    filter_graph = RawFilterGraph()
    node_map: dict[GraphNode, RawGraphNode] = {}
    # Create the filter graph node
    for node in nx.topological_sort(reachable):
        match node:
            case LabelNode(id, cap):
                node_map[node] = RawFilterLabel(f"{cap}_{len(node_map)}", cap=cap)
            case FilterNode(_, filter):
                node_map[node] = RawFilter(filter)

        filter_graph.add_node(node_map[node])
        for prev in reachable.predecessors(node):
            filter_graph.add_edge(node_map[prev], node_map[node])

    for node in filter_graph:
        if isinstance(node, RawFilterLabel) and filter_graph.out_degree(node) > 1:
            split_nodes = []
            out_edges = list(filter_graph.out_edges(node))
            for i, (u, v) in enumerate(out_edges):
                filter_graph.remove_edge(u, v)
                new_node = RawFilterLabel(f"{node.label}_{i}", cap=node.cap)
                split_nodes.append(new_node)
                filter_graph.add_edge(new_node, v)

            # Insert split node
            split_filter = RawFilter(f"split={len(split_nodes)}") if node.label.startswith("v") else RawFilter(f"asplit={len(split_nodes)}") 
            filter_graph.add_edge(node, split_filter)
            for s in split_nodes:
                filter_graph.add_edge(split_filter, s)

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
