from collections import Counter
from typing import Generic, Tuple, TypeVar

from src.algos.discovery.inductive_miner.fall_throughs.strict_tau_loop import StrictTauLoop
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class TauLoop(StrictTauLoop, Generic[T]):
    @classmethod
    def _projection(cls, event_log: T, dfg: DirectlyFollowsGraph) -> T:
        projection: T = Counter()  # type: ignore
        for sequence, cnt in event_log.items():
            new_sequence: tuple[str, ...] = tuple()
            for i, _ in enumerate(sequence):
                new_sequence += (sequence[i],)
                if i < len(sequence) - 1 and sequence[i + 1] in list(dfg.start_activities.keys()):
                    projection.update({new_sequence: cnt})
                    new_sequence = tuple()
            if not new_sequence:
                new_sequence = (SILENT_TRANSITION_LABEL,)
            projection.update({new_sequence: cnt})
        return projection
