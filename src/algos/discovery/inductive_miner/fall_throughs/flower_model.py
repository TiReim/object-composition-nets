from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

from overrides import override

from src.algos.discovery.inductive_miner.fall_throughs.abstract import FallThrough
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.process_tree.operator import Operator
from src.objects.process_tree.process_tree import ProcessTree

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class FlowerModel(FallThrough, Generic[T]):
    @classmethod
    @override
    def holds(cls, event_log: T, dfg: DirectlyFollowsGraph) -> bool:
        return True

    @classmethod
    @override
    def apply(cls, event_log: T, dfg: DirectlyFollowsGraph) -> (Optional[tuple[ProcessTree, List[T]]]):
        projection_flower: T = Counter()  # type: ignore
        for activity in sorted(list(dfg.nodes())):
            projection_flower.update({(activity,): 1})
        return ProcessTree(operator=Operator.LOOP), [Counter(), projection_flower]  # type: ignore
