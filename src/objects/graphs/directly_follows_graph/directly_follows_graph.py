import warnings
from collections import Counter
from typing import Iterable, Tuple

from src.objects.graphs.abstract_follows_graph.abstract_follows_graph import AbstractFollowsGraph
from src.objects.graphs.abstract_follows_graph.typing import DirectlyFollowsGraphEdgePayload
from src.objects.graphs.multi_object_directly_follows_graph.multi_object_directly_follows_graph import (
    MultiObjectDirectlyFollowsGraph,
)


class DirectlyFollowsGraph(AbstractFollowsGraph):
    def __init__(
        self,
        nbunch_edges: Iterable[Tuple[str, str, DirectlyFollowsGraphEdgePayload]],
        start_activities: Counter[str],
        end_activities: Counter[str],
    ):
        """
        :param nbunch_edges: An iterable of edges in the form of (Activity1, Activity2, Directly Follows Edge Data
        Dict), where the activities are strings and data dict is a direct follows edge payload dict. :param
        start_activities: A set of activities  representing the start activities :param end_activities: A set of
        activities representing the end activities
        """
        super().__init__(nbunch_edges)
        self._start_activities: Counter[str] = start_activities
        self._end_activities: Counter[str] = end_activities

    @property
    def start_activities(self) -> Counter[str]:
        return self._start_activities

    @property
    def end_activities(self) -> Counter[str]:
        return self._end_activities

    @classmethod
    def create_by_projection_on_object(cls, modfg: MultiObjectDirectlyFollowsGraph, otype: str):
        if otype not in modfg.object_types:
            warnings.warn(
                "Selected object type does not exist on the passed multi-object directly follows graph",
                category=UserWarning,
            )

        edge_list: Iterable[Tuple[str, str, DirectlyFollowsGraphEdgePayload]] = (
            (uid, vid, DirectlyFollowsGraphEdgePayload.model_validate(data[otype]))
            for uid, vid, data in modfg.edges(data=True)
            if otype in data
        )

        start_activities = modfg.start_activities[otype]
        end_activities = modfg.end_activities[otype]

        return DirectlyFollowsGraph(edge_list, start_activities=start_activities, end_activities=end_activities)
