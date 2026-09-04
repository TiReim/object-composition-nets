from abc import ABC, abstractmethod
from collections import Counter
from typing import Generic, List, Optional, Tuple, TypeVar

from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph
from src.objects.process_tree.process_tree import ProcessTree

T = TypeVar("T", bound=Counter[Tuple[str, ...]])


class Cut(ABC, Generic[T]):
    @classmethod
    @abstractmethod
    def _operator(cls) -> ProcessTree:
        raise NotImplementedError()

    # Holds method is not private because it is used in the activity concurrent fallthrough case
    @classmethod
    @abstractmethod
    def holds(cls, dfg: DirectlyFollowsGraph) -> Optional[List[List[str]]]:
        raise NotImplementedError()

    @classmethod
    def apply(cls, event_log: T, dfg: DirectlyFollowsGraph) -> (Optional[Tuple[ProcessTree, List[T]]]):
        partitions = cls.holds(dfg)
        if partitions is not None:
            return cls._operator(), cls._project(event_log, partitions)
        return None

    @classmethod
    @abstractmethod
    def _project(cls, event_log: T, partitions: List[List[str]]) -> List[T]:
        raise NotImplementedError()
