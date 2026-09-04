from collections import Counter

from src.objects.graphs.abstract_follows_graph.typing import DirectlyFollowsGraphEdgePayload
from src.objects.graphs.directly_follows_graph.directly_follows_graph import DirectlyFollowsGraph

# pylint: disable = too-few-public-methods


class DirectlyFollowsGraphFactory:
    @staticmethod
    def create_from_event_log(event_log: Counter[tuple[str, ...]]) -> DirectlyFollowsGraph:
        start_activities: Counter[str] = Counter()
        end_activities: Counter[str] = Counter()
        edges: Counter[tuple[str, str]] = Counter()
        activities: set[str] = set()

        for sequence, cnt in event_log.items():
            if sequence:
                start_activities.update({sequence[0]: cnt})
                end_activities.update({sequence[-1]: cnt})
                if sequence:
                    activities.add(sequence[0])
                edges.update(dict(((act_1, act_2), cnt) for act_1, act_2 in zip(sequence[:-1], sequence[1:])))
        edge_list = [(edge[0], edge[1], DirectlyFollowsGraphEdgePayload(count=cnt)) for edge, cnt in edges.items()]
        dfg = DirectlyFollowsGraph(edge_list, start_activities, end_activities)
        for activity in activities:
            if activity not in dfg.nodes:
                dfg.add_node(activity)
        return dfg
