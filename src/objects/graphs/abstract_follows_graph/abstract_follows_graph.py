from abc import ABCMeta, abstractmethod
from typing import Any

from networkx import DiGraph


class AbstractFollowsGraph(DiGraph, metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, nbunch_edges):
        super().__init__(incoming_graph_data=nbunch_edges)

    @property
    @abstractmethod
    def start_activities(self) -> Any:
        pass

    @property
    @abstractmethod
    def end_activities(self) -> Any:
        pass
