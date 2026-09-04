from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

from overrides import override

from src.algos.discovery.inductive_miner.fall_throughs.abstract import FallThrough
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.process_tree.operator import Operator
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL, ProcessTree

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class StrictTauLoop(FallThrough, Generic[T]):
    @classmethod
    @override
    def holds(cls, event_log: T, dfg: DirectlyFollowsGraph) -> bool:
        return sum(cls._projection(event_log, dfg).values()) > sum(event_log.values())

    @classmethod
    def _projection(cls, event_log: T, dfg: DirectlyFollowsGraph) -> T:
        projection: T = Counter()  # type: ignore
        for sequence, cnt in event_log.items():
            new_sequence: tuple[str, ...] = tuple()
            for i, _ in enumerate(sequence):
                new_sequence += (sequence[i],)
                if (
                    i < len(sequence) - 1
                    and sequence[i] in dfg.end_activities.keys()
                    and sequence[i + 1] in dfg.start_activities.keys()
                ):
                    projection.update({new_sequence: cnt})
                    new_sequence = tuple()
            if not new_sequence:
                new_sequence = (SILENT_TRANSITION_LABEL,)
            projection.update({new_sequence: cnt})
        return projection

    @classmethod
    @override
    def apply(cls, event_log: T, dfg: DirectlyFollowsGraph) -> (Optional[Tuple[ProcessTree, List[T]]]):
        projection: T = cls._projection(event_log, dfg)  # type: ignore
        if sum(projection.values()) > sum(event_log.values()):
            return ProcessTree(operator=Operator.LOOP), [projection, Counter()]  # type: ignore
        return None
