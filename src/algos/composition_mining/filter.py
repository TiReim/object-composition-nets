from abc import ABC, abstractmethod
from collections import Counter, defaultdict

from src.algos.composition_mining.composition_grouping import CompositionalEventLog
from src.algos.composition_mining.compute_object_compositions import ObjectComposition
from src.objects.graphs.object_centric_event_graph.oceg import ObjectCentricEventGraph

# pylint: disable=too-few-public-methods, too-many-locals


class FilterFramework(ABC):
    @classmethod
    @abstractmethod
    def filter(
        cls, event_logs: set[CompositionalEventLog], graph: ObjectCentricEventGraph
    ) -> set[CompositionalEventLog]:
        pass


class HigherTypeCoverageFilter(FilterFramework):
    @classmethod
    def filter(
        cls,
        event_logs: set[CompositionalEventLog],
        graph: ObjectCentricEventGraph,
        theta: float = 1.0,
    ) -> set[CompositionalEventLog]:
        """
        Filter higher-types by how well their compositions cover the events of their activities.

        Implements the higher-type filtering step of the discovery framework: given a threshold
        ``theta`` in ``[0, 1]``, a higher-type (represented by a ``CompositionalEventLog``) is kept
        iff its compositions cover at least a fraction ``theta`` of all events in the graph that
        belong to the activities occurring in those compositions.

        Args:
            event_logs: Set of compositional event logs (one per higher-type) to filter
            graph: The original object-centric event graph
            theta: Minimum required fraction of the involved activities' events to be covered

        Returns:
            The subset of ``event_logs`` whose coverage meets ``theta``, kept unchanged
        """
        # Total number of events per activity in the graph
        activity_event_counts: Counter[str] = Counter()
        for event_node in graph.event_nodes:
            activity_event_counts[event_node.activity] += 1

        result: set[CompositionalEventLog] = set()
        for cel in event_logs:
            # Events covered by the compositions and the activities they involve
            covered_event_ids: set[str] = set()
            covered_activities: set[str] = set()
            for composition in cel.compositions:
                for event in composition.event_sequence:
                    covered_event_ids.add(event.event_id)
                    covered_activities.add(event.activity)

            # Total number of events belonging to the involved activities
            total_events = sum(activity_event_counts.get(activity, 0) for activity in covered_activities)
            coverage = len(covered_event_ids) / total_events if total_events > 0 else 0.0

            if coverage >= theta:
                result.add(cel)

        return result
