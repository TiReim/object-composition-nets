from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

import networkx as nx
from overrides import override

from src.algos.discovery.inductive_miner.cuts.abstract import Cut
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.process_tree.operator import Operator
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL, ProcessTree

# pylint:disable=duplicate-code


T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class SequenceCut(Cut, Generic[T]):
    @classmethod
    @override
    def _operator(cls) -> ProcessTree:
        return ProcessTree(operator=Operator.SEQUENCE)

    @classmethod
    def _skippable(cls, pivot: int, partitions: List[List[str]], dfg: DirectlyFollowsGraph) -> bool:
        activities_before = []
        activities_after = []

        for i in range(len(partitions) - pivot - 1):
            activities_after += partitions[pivot + i + 1]
            for activity in partitions[pivot + i + 1]:
                if activity in dfg.start_activities.keys():
                    return True

        for i in range(pivot):
            activities_before += partitions[i]
            for activity in partitions[i]:
                if activity in dfg.end_activities.keys():
                    return True

        for relation in list(dfg.edges()):
            if relation[0] in activities_before and relation[1] in activities_after:
                return True

        return False

    @classmethod
    def _prep_min_from_max_to(cls, partitions: List[List[str]], dfg: DirectlyFollowsGraph) -> Tuple[dict, dict]:
        min_from = {}
        max_to = {}

        for i in range(len(partitions)):
            min_from[i] = len(partitions)
            max_to[i] = -1

        for i, partition in enumerate(partitions):
            for activity in partition:
                if activity in dfg.start_activities.keys():
                    min_from[i] = -1
                if activity in dfg.end_activities.keys():
                    max_to[i] = len(partitions)

        for i, partition_i in enumerate(partitions):
            for j, partition_j in enumerate(partitions):
                for relation in dfg.edges():
                    if relation[0] in partition_i and relation[1] in partition_j:
                        min_from[j] = min(min_from[j], i)
                        max_to[i] = max(max_to[i], j)
        return min_from, max_to

    @classmethod
    def _strict_sequence_cut(cls, partitions: List[List[str]], dfg: DirectlyFollowsGraph) -> List[List[str]]:
        min_from, max_to = cls._prep_min_from_max_to(partitions, dfg)

        for pivot, _ in enumerate(partitions):
            if cls._skippable(pivot, partitions, dfg):
                q_check = pivot - 1
                while q_check >= 0 and max_to[q_check] <= pivot:
                    partitions[pivot] += partitions[q_check]
                    partitions[q_check] = []
                    q_check = q_check - 1

                q_check = pivot + 1
                while q_check < len(partitions) and min_from[q_check] >= pivot:
                    partitions[pivot] += partitions[q_check]
                    partitions[q_check] = []
                    q_check = q_check + 1

        partitions = list(filter(None, partitions))

        return partitions

    @classmethod
    @override
    def holds(cls, dfg: DirectlyFollowsGraph) -> Optional[List[List[str]]]:
        transitive_closure_graph = nx.transitive_closure(dfg.to_directed())
        transitive_closure = transitive_closure_graph.edges()
        partitions = [[activity] for activity in dfg.nodes()]
        for act_a in dfg.nodes():
            for act_b in dfg.nodes():
                if ((act_a, act_b) in transitive_closure and (act_b, act_a) in transitive_closure) or (
                    (act_a, act_b) not in transitive_closure and (act_b, act_a) not in transitive_closure
                ):
                    partition_a = []
                    partition_b = []
                    for partition in partitions:
                        if act_a in partition:
                            partition_a = partition
                        if act_b in partition:
                            partition_b = partition
                    partitions = [
                        partition for partition in partitions if act_a not in partition and act_b not in partition
                    ]
                    partitions.append(list(set(partition_a).union(set(partition_b))))
        partitions = sorted(
            partitions,
            key=lambda p: len([(x, y) for (x, y) in transitive_closure if x == p[0] and x != y]),
            reverse=True,
        )
        partitions = cls._strict_sequence_cut(partitions, dfg)
        return partitions if len(partitions) > 1 else None

    @classmethod
    @override
    def _project(cls, event_log: T, partitions: List[List[str]]) -> List[T]:
        projections: List[T] = []
        for partition in partitions:
            projection: T = Counter()  # type: ignore
            for sequence, cnt in event_log.items():
                new_sequence: Tuple[str, ...] = tuple(event for event in sequence if event in partition)
                if not new_sequence:
                    new_sequence = (SILENT_TRANSITION_LABEL,)
                projection.update({new_sequence: cnt})
            projections.append(projection)
        return projections
