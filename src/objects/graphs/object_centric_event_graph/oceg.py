from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from src.objects.event_log.constants import (
    EVENT_ID_COLUMN,
    EVENT_NAME_COLUMN,
    EVENT_TIME_COLUMN,
    OBJECT_ID_COLUMN,
    OBJECT_TYPE_COLUMN,
)
from src.objects.event_log.object_centric.obj import ObjectCentricEventLog


@dataclass(slots=True, frozen=True)
class EventNode:
    event_id: str
    activity: str
    timestamp: datetime


@dataclass(slots=True, frozen=True)
class ObjectNode:
    object_id: str
    object_type: str


class ObjectCentricEventGraph:
    __slots__ = ("_event_nodes", "_object_nodes", "_adjacency")

    def __init__(self):
        self._event_nodes: dict[str, EventNode] = {}
        self._object_nodes: dict[str, ObjectNode] = {}
        self._adjacency: dict[str, set[str]] = {}

    @classmethod
    def from_object_centric_event_log(cls, ocel: ObjectCentricEventLog) -> "ObjectCentricEventGraph":
        graph = cls()

        # Add event nodes from event table
        for row in ocel.event_table.iter_rows(named=True):
            graph.add_event_node(
                event_id=row[EVENT_ID_COLUMN],
                activity=row[EVENT_NAME_COLUMN],
                timestamp=row[EVENT_TIME_COLUMN],
            )

        # Add object nodes and edges from event_to_object table
        for row in ocel.event_to_object_table.iter_rows(named=True):
            event_id = row[EVENT_ID_COLUMN]
            object_id = row[OBJECT_ID_COLUMN]
            object_type = row[OBJECT_TYPE_COLUMN]

            # Add object node if not already present
            if graph.get_object_node(object_id) is None:
                graph.add_object_node(object_id, object_type)

            # Add edge between event and object
            graph.add_edge(event_id, object_id)

        return graph

    def add_event_node(self, event_id: str, activity: str, timestamp: datetime) -> EventNode:
        node = EventNode(event_id, activity, timestamp)
        self._event_nodes[event_id] = node
        self._adjacency.setdefault(event_id, set())
        return node

    def add_object_node(self, object_id: str, object_type: str) -> ObjectNode:
        node = ObjectNode(object_id, object_type)
        self._object_nodes[object_id] = node
        self._adjacency.setdefault(object_id, set())
        return node

    def add_edge(self, node_id_1: str, node_id_2: str) -> None:
        if node_id_1 not in self._adjacency or node_id_2 not in self._adjacency:
            raise ValueError("Both nodes must exist in the graph")
        self._adjacency[node_id_1].add(node_id_2)
        self._adjacency[node_id_2].add(node_id_1)

    def remove_edge(self, node_id_1: str, node_id_2: str) -> None:
        if node_id_1 not in self._adjacency or node_id_2 not in self._adjacency:
            raise ValueError("Both nodes must exist in the graph")
        self._adjacency[node_id_1].remove(node_id_2)
        self._adjacency[node_id_2].remove(node_id_1)

    def get_neighbors(self, node_id: str) -> set[str]:
        if node_id not in self._adjacency:
            raise KeyError(f"Node {node_id} not found")
        return self._adjacency[node_id]

    def get_events_for_object(self, object_id: str) -> list[EventNode]:
        if object_id not in self._object_nodes:
            raise KeyError(f"Object node {object_id} not found")

        neighbor_ids = self._adjacency.get(object_id, set())
        events = [self._event_nodes[nid] for nid in neighbor_ids if nid in self._event_nodes]
        events.sort(key=lambda e: (e.timestamp, e.event_id))
        return events

    def get_event_node(self, event_id: str) -> EventNode | None:
        return self._event_nodes.get(event_id)

    def get_object_node(self, object_id: str) -> ObjectNode | None:
        return self._object_nodes.get(object_id)

    @property
    def event_nodes(self) -> Iterator[EventNode]:
        return iter(self._event_nodes.values())

    @property
    def object_nodes(self) -> Iterator[ObjectNode]:
        return iter(self._object_nodes.values())
