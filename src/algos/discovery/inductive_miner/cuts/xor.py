from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

import networkx as nx
from overrides import override

from src.algos.discovery.inductive_miner.cuts.abstract import Cut
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.process_tree.operator import Operator
from src.objects.process_tree.process_tree import ProcessTree

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class XorCut(Cut, Generic[T]):
    @classmethod
    @override
    def _operator(cls) -> ProcessTree:
        return ProcessTree(operator=Operator.XOR)

    @classmethod
    @override
    def holds(cls, dfg: DirectlyFollowsGraph) -> Optional[List[List[str]]]:
        undirected_graph = dfg.to_undirected()
        partitions = [sorted(list(partition)) for partition in nx.connected_components(undirected_graph)]
        partitions = sorted(partitions, key=lambda x: x[0])
        return partitions if len(partitions) > 1 else None

    @classmethod
    @override
    def _project(cls, event_log: T, partitions: List[List[str]]) -> List[T]:
        projections = []
        for partition in partitions:
            projection: T = Counter()  # type: ignore
            for sequence, cnt in event_log.items():
                if sequence[0] in partition:
                    projection.update({sequence: cnt})
            projections.append(projection)
        return projections
