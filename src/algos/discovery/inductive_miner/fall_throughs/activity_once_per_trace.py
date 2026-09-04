from collections import Counter
from typing import Generic, Optional, Tuple, TypeVar

from src.algos.discovery.inductive_miner.fall_throughs.activity_concurrent import ActivityConcurrent
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class ActivityOncePerTrace(ActivityConcurrent, Generic[T]):
    @classmethod
    def _get_candidate(cls, event_log: T, dfg: DirectlyFollowsGraph) -> Optional[str]:
        if len(list(dfg.nodes())) > 1:
            once_candidates = list(dfg.nodes())
            while once_candidates:
                candidate = once_candidates[0]
                removed = False
                for sequence in event_log:
                    if not removed and list(sequence).count(candidate) != 1:
                        removed = True
                        once_candidates.remove(candidate)
                        break
                if not removed:
                    return candidate
        return None
