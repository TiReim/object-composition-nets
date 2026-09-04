from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

from overrides import override

from src.algos.discovery.inductive_miner.cuts.abstract import Cut
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.process_tree.operator import Operator
from src.objects.process_tree.process_tree import ProcessTree

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class LoopCut(Cut, Generic[T]):
    @classmethod
    @override
    def _operator(cls) -> ProcessTree:
        return ProcessTree(operator=Operator.LOOP)

    @classmethod
    def _missing_connection_from_end(cls, dfg: DirectlyFollowsGraph, activity: str) -> bool:
        return any(((end_activity, activity) not in dfg.edges() for end_activity in dfg.end_activities.keys()))

    @classmethod
    def _missing_connection_to_start(cls, dfg: DirectlyFollowsGraph, activity: str) -> bool:
        return any(((activity, start_activity) not in dfg.edges() for start_activity in dfg.start_activities.keys()))

    @classmethod
    def _separate_partition_0(
        cls, dfg: DirectlyFollowsGraph, partitions: List[List[str]]
    ) -> Tuple[List[str], List[List[str]]]:
        ordered_partitions = []
        partition_0 = []
        for partition in partitions:
            part_of_p0 = False
            for activity in partition:
                if activity in dfg.start_activities.keys() or activity in dfg.end_activities.keys():
                    part_of_p0 = True
                for edge in dfg.in_edges(activity):
                    if not part_of_p0 and edge[0] in dfg.end_activities.keys():
                        part_of_p0 = cls._missing_connection_from_end(dfg, activity)
                for edge in dfg.out_edges(activity):
                    if not part_of_p0 and edge[1] in dfg.start_activities.keys():
                        part_of_p0 = cls._missing_connection_to_start(dfg, activity)
            if part_of_p0:
                partition_0 += partition
            else:
                ordered_partitions.append(partition)
        return partition_0, ordered_partitions

    @classmethod
    @override
    def holds(cls, dfg: DirectlyFollowsGraph) -> Optional[List[List[str]]]:
        remaining_activities = list(dfg.nodes())
        partitions = []
        while remaining_activities:
            partition = [remaining_activities[0]]
            activity_check_partition = [remaining_activities[0]]
            remaining_activities.remove(remaining_activities[0])
            while activity_check_partition:

                add_to_partition = set()

                for edge in dfg.out_edges(activity_check_partition):
                    if (
                        edge[0] not in list(dfg.end_activities.keys())
                        and edge[1] not in list(dfg.start_activities.keys())
                        and edge[1] not in partition + activity_check_partition
                        and edge[1] in remaining_activities
                    ):
                        add_to_partition.add(edge[1])
                for edge in dfg.in_edges(activity_check_partition):
                    if (
                        edge[0] not in list(dfg.end_activities.keys())
                        and edge[1] not in list(dfg.start_activities.keys())
                        and edge[0] not in partition + activity_check_partition
                        and edge[0] in remaining_activities
                    ):
                        add_to_partition.add(edge[0])

                for activity in add_to_partition:
                    remaining_activities.remove(activity)
                    partition.append(activity)
                    activity_check_partition.append(activity)

                activity_check_partition.remove(activity_check_partition[0])
            partitions.append(partition)

        partition_0, resulting_partitions = cls._separate_partition_0(dfg, partitions)
        partitions = [partition_0]
        if len(resulting_partitions) > 0:
            partitions.append([activity for partition in resulting_partitions for activity in partition])
        return partitions if len(partitions) > 1 else None

    @classmethod
    @override
    def _project(cls, event_log: T, partitions: List[List[str]]) -> List[T]:
        projections: List[T] = []
        for partition in partitions:
            projection: T = Counter()  # type: ignore
            for sequence, cnt in event_log.items():
                new_sequence: tuple[str, ...] = tuple()
                last_event_in = False
                for j, event in enumerate(sequence):
                    if event in partition:
                        new_sequence += (event,)
                        last_event_in = True
                        if j == len(sequence) - 1:
                            projection.update({new_sequence: cnt})
                    elif last_event_in:
                        projection.update({new_sequence: cnt})
                        last_event_in = False
                        new_sequence = tuple()
            projections.append(projection)
        return projections
