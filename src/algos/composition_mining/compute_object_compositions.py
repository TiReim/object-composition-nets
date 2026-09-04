from dataclasses import dataclass
from datetime import datetime

from src.objects.data_types.higher_order_object_types import HigherOrderObject
from src.objects.graphs.object_centric_event_graph.oceg import (
    EventNode,
    ObjectCentricEventGraph,
    ObjectNode,
)


@dataclass(slots=True)
class ObjectComposition:
    objects: frozenset[ObjectNode]
    event_sequence: tuple[EventNode, ...]
    ho_object: HigherOrderObject | None = None

    @property
    def start_time(self) -> datetime:
        return self.event_sequence[0].timestamp

    @property
    def end_time(self) -> datetime:
        return self.event_sequence[-1].timestamp

    def __hash__(self):
        return hash((self.objects, self.event_sequence))

    def __repr__(self):
        return str(self.objects) + " - " + str(self.event_sequence)


# pylint: disable=too-few-public-methods


class ObjectCompositionMiner:
    @classmethod
    def compute_maximal_object_composition_per_object(cls, graph: ObjectCentricEventGraph) -> set[ObjectComposition]:
        ordered_events = sorted(graph.event_nodes, key=lambda e: (e.timestamp, e.event_id))
        maximal_compositions = set()
        ongoing_compositions: dict[frozenset[str], list[EventNode]] = {}
        extended_flag: dict[frozenset[str], bool] = {}
        for event in ordered_events:
            event_objects = frozenset(graph.get_neighbors(event.event_id))
            # Update ongoing compositions with the current event
            for comp in list(ongoing_compositions):
                if comp <= event_objects:
                    ongoing_compositions[comp].append(event)
                    extended_flag[comp] = True
                elif comp & event_objects:
                    if len(ongoing_compositions[comp]) > 1 and extended_flag[comp]:
                        maximal_compositions.add(
                            ObjectComposition(
                                objects=frozenset(graph.get_object_node(obj_id) for obj_id in comp),
                                event_sequence=tuple(ongoing_compositions[comp]),
                            )
                        )
                    intersection = comp & event_objects
                    if len(intersection) > 1 and intersection not in ongoing_compositions:
                        ongoing_compositions[intersection] = ongoing_compositions[comp] + [event]
                        extended_flag[intersection] = True
                    removed = comp - event_objects
                    if len(removed) > 1 and removed not in ongoing_compositions:
                        ongoing_compositions[removed] = ongoing_compositions[comp]
                        extended_flag[removed] = False
                    del ongoing_compositions[comp]
                    del extended_flag[comp]
            if len(event_objects) > 1 and event_objects not in ongoing_compositions:
                ongoing_compositions[event_objects] = [event]
                extended_flag[event_objects] = True
        for objs, events in ongoing_compositions.items():
            if len(events) > 1 and extended_flag[objs]:
                maximal_compositions.add(
                    ObjectComposition(
                        objects=frozenset(graph.get_object_node(obj_id) for obj_id in objs),
                        event_sequence=tuple(events),
                    )
                )
        return maximal_compositions
