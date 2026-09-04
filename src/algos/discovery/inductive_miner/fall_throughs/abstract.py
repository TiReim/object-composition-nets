from abc import ABC, abstractmethod
from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.process_tree.process_tree import ProcessTree

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class FallThrough(ABC, Generic[T]):
    @classmethod
    @abstractmethod
    def holds(cls, event_log: T, dfg: DirectlyFollowsGraph) -> bool:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def apply(cls, event_log: T, dfg: DirectlyFollowsGraph) -> (Optional[Tuple[ProcessTree, List[T]]]):
        raise NotImplementedError()
