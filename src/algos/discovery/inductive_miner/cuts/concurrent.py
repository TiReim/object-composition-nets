from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

from overrides import override

from src.algos.discovery.inductive_miner.cuts.abstract import Cut
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.process_tree.operator import Operator
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL, ProcessTree

# pylint:disable=duplicate-code


T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class ConcurrentCut(Cut, Generic[T]):
    @classmethod
    @override
    def _operator(cls) -> ProcessTree:
        return ProcessTree(operator=Operator.PARALLEL)

    # This method checks if the partitions have a start and end activity. If not the partition is not a real one, and
    # we merge the partition with a real partition.
    @classmethod
    def _get_real_partitions(cls, partitions: List[List[str]], dfg: DirectlyFollowsGraph) -> List[List[str]]:
        real_partitions: List[List[str]] = []
        merge_partition = []
        for i, partition in enumerate(partitions):
            if (
                len(set(partition).intersection(set(dfg.start_activities.keys()))) == 0
                or len(set(partition).intersection(set(dfg.end_activities.keys()))) == 0
            ):
                if i < len(partitions) - 1:
                    merge_partition += partition
                elif len(real_partitions) > 0:
                    real_partitions[0] += partition
                # There is no real partition and all partitions are merged in merge_partitions (Case no cut found)
                else:
                    real_partitions.append(merge_partition)
            else:
                real_partitions.append(partition + merge_partition)
                merge_partition = []
        return real_partitions

    @classmethod
    @override
    def holds(cls, dfg: DirectlyFollowsGraph) -> Optional[List[List[str]]]:
        remaining_activities = sorted(list(dfg.nodes()))
        partitions = []
        while remaining_activities:
            activity = remaining_activities[0]
            remaining_activities.remove(activity)
            partition = [activity]
            activity_check_partition = [activity]

            # After this loop all activities are in a partition that have only one edge in one direction
            while activity_check_partition:
                check_activity = activity_check_partition[0]
                for edge in dfg.out_edges(check_activity):
                    if (
                        (edge[1], edge[0]) not in dfg.in_edges(check_activity)
                        and edge[1] not in partition + activity_check_partition
                        and edge[1] in remaining_activities
                    ):
                        remaining_activities.remove(edge[1])
                        partition.append(edge[1])
                        activity_check_partition.append(edge[1])
                activity_check_partition.remove(check_activity)
            partitions.append(partition)

        partitions = cls._get_real_partitions(partitions, dfg)
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
