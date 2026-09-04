from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

from overrides import override

from src.algos.discovery.inductive_miner.cuts.concurrent import ConcurrentCut
from src.algos.discovery.inductive_miner.cuts.loop import LoopCut
from src.algos.discovery.inductive_miner.cuts.sequence import SequenceCut
from src.algos.discovery.inductive_miner.cuts.xor import XorCut
from src.algos.discovery.inductive_miner.fall_throughs.abstract import FallThrough
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.graphs.directly_follows_graph.directly_follows_graph_factory import (
    DirectlyFollowsGraphFactory,
)
from src.objects.process_tree.operator import Operator
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL, ProcessTree

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class ActivityConcurrent(FallThrough, Generic[T]):
    @classmethod
    def _activity_concurrent_projection(cls, event_log: T, once_activity: str) -> (List[T]):
        projection_once: T = Counter()  # type: ignore
        projection_rest: T = Counter()  # type: ignore
        for sequence, cnt in event_log.items():
            seq = [once_activity for _ in range(sequence.count(once_activity))]
            projection_once.update({tuple(seq): cnt})
            new_sequence: Tuple[str, ...] = tuple(event for event in sequence if event != once_activity)
            if not new_sequence:
                new_sequence = (SILENT_TRANSITION_LABEL,)
            projection_rest.update({new_sequence: cnt})
        return [projection_once, projection_rest]

    @classmethod
    def _get_candidate(cls, event_log: T, dfg: DirectlyFollowsGraph) -> Optional[str]:
        if len(list(dfg.nodes())) > 1:
            min_once_candidates = set(dfg.nodes())
            for sequence in event_log:
                if len(min_once_candidates) > 0:
                    candidates = set(dfg.nodes())
                    min_once_in_seq = set()
                    for event in sequence:
                        if event in candidates:
                            candidates.remove(event)
                            min_once_in_seq.add(event)
                    min_once_candidates = min_once_candidates.intersection(min_once_in_seq)

            for candidate in min_once_candidates:
                proj_rest = cls._activity_concurrent_projection(event_log, candidate)[1]
                proj_dfg = DirectlyFollowsGraphFactory.create_from_event_log(proj_rest)
                if (
                    XorCut.holds(proj_dfg) is not None
                    or SequenceCut.holds(proj_dfg) is not None
                    or ConcurrentCut.holds(proj_dfg) is not None
                    or LoopCut.holds(proj_dfg) is not None
                ):
                    return candidate
        return None

    @classmethod
    @override
    def holds(cls, event_log: T, dfg: DirectlyFollowsGraph) -> bool:
        return cls._get_candidate(event_log, dfg) is not None

    @classmethod
    @override
    def apply(cls, event_log: T, dfg: DirectlyFollowsGraph) -> (Optional[Tuple[ProcessTree, List[T]]]):
        candidate = cls._get_candidate(event_log, dfg)
        if candidate is None:
            return None
        projections = cls._activity_concurrent_projection(event_log, candidate)
        return ProcessTree(operator=Operator.PARALLEL), projections
