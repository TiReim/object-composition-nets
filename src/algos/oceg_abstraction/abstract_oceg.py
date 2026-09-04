from collections import defaultdict
from datetime import timedelta

from src.algos.composition_mining.composition_grouping import CompositionalEventLog
from src.objects.data_types.higher_order_object_types import HigherOrderObject, HigherOrderObjectType
from src.objects.data_types.object_reference import ObjectReference
from src.objects.graphs.object_centric_event_graph.oceg import ObjectCentricEventGraph

# Offset used to place the artificial boundary events immediately before the first event and
# immediately after the last event of a composition, without colliding with the real events.
_EVENT_TIME_EPSILON = timedelta(microseconds=1)


class OCEGAbstraction:
    @classmethod
    def abstract_oceg(
        cls, oceg: ObjectCentricEventGraph, compositional_event_logs: set[CompositionalEventLog]
    ) -> ObjectCentricEventGraph:
        abstracted_oceg = ObjectCentricEventGraph()
        for event in oceg.event_nodes:
            abstracted_oceg.add_event_node(event.event_id, event.activity, event.timestamp)
        for obj in oceg.object_nodes:
            abstracted_oceg.add_object_node(obj.object_id, obj.object_type)
        for event in oceg.event_nodes:
            for obj_id in oceg.get_neighbors(event.event_id):
                abstracted_oceg.add_edge(event.event_id, obj_id)
        # Insert compositions bottom-up so that a nested composition is already present as a composed
        # object node when a containing composition is inserted.
        for cel in sorted(compositional_event_logs, key=lambda x: x.ho_object_type.depth()):
            abstracted_oceg = cls.insert_object_compositions_into_graph(abstracted_oceg, cel)

        # Enforce that a contained object type never performs a composition activity of a higher-type
        # containing it, by relabeling non-conforming occurrences to fresh, type-specific ones.
        blocked_activities = cls._compute_blocked_activities_per_object_type(compositional_event_logs)
        abstracted_oceg = cls.substitute_violating_event_sequences(abstracted_oceg, blocked_activities)

        return abstracted_oceg

    @classmethod
    def insert_object_compositions_into_graph(
        cls, oceg: ObjectCentricEventGraph, compositional_event_log: CompositionalEventLog
    ) -> ObjectCentricEventGraph:
        ho_type_label = str(compositional_event_log.ho_object_type)
        for composition in compositional_event_log.compositions:
            event_sequence = composition.event_sequence
            first_activity = event_sequence[0].activity
            last_activity = event_sequence[-1].activity
            start_activity, member_activity, end_activity = cls.composition_activities(
                ho_type_label, first_activity, last_activity
            )

            composed_object_id = str(composition.ho_object)
            start_event_id = "start|" + composed_object_id
            member_event_id = "member|" + composed_object_id
            end_event_id = "end|" + composed_object_id

            # 1. Create the composed object node and the three artificial event nodes. The start
            #    event is placed immediately before the first event of the composition, the member
            #    event carries the timestamp of that first event, and the end event is placed
            #    immediately after the last one.
            oceg.add_object_node(composed_object_id, ho_type_label)
            oceg.add_event_node(start_event_id, start_activity, event_sequence[0].timestamp - _EVENT_TIME_EPSILON)
            oceg.add_event_node(member_event_id, member_activity, event_sequence[0].timestamp)
            oceg.add_event_node(end_event_id, end_activity, event_sequence[-1].timestamp + _EVENT_TIME_EPSILON)

            # 2. Connect the composed object to its boundary events and to all events of the composition.
            oceg.add_edge(composed_object_id, start_event_id)
            oceg.add_edge(composed_object_id, end_event_id)
            for event in event_sequence:
                oceg.add_edge(composed_object_id, event.event_id)

            # 3. Reroute each member from the composition events to the single member event.
            for member_id in cls._member_node_ids(composition.ho_object):
                oceg.add_edge(member_event_id, member_id)
                for event in event_sequence:
                    if event.event_id in oceg.get_neighbors(member_id):
                        oceg.remove_edge(member_id, event.event_id)
        return oceg

    @classmethod
    def substitute_violating_event_sequences(
        cls, oceg: ObjectCentricEventGraph, blocked_activities: dict[str, set[str]]
    ) -> ObjectCentricEventGraph:
        for obj in list(oceg.object_nodes):
            if obj.object_type not in blocked_activities:
                continue
            for event in oceg.get_events_for_object(obj.object_id):
                if event.activity in blocked_activities[obj.object_type]:
                    # Relabel this occurrence (same timestamp) to a fresh activity that is specific
                    # to the object type. All objects of that type violating the same event share the
                    # relabeled occurrence, so an event is split per object type, not per object.
                    relabeled_activity = f"{event.activity}'|{obj.object_type}"
                    relabeled_event_id = f"{event.event_id}|{obj.object_type}|nonconforming"
                    oceg.add_event_node(relabeled_event_id, relabeled_activity, event.timestamp)
                    oceg.remove_edge(obj.object_id, event.event_id)
                    oceg.add_edge(obj.object_id, relabeled_event_id)
        return oceg

    @classmethod
    def _compute_blocked_activities_per_object_type(
        cls, compositional_event_logs: set[CompositionalEventLog]
    ) -> dict[str, set[str]]:
        blocked_activities: dict[str, set[str]] = defaultdict(set)
        for cel in compositional_event_logs:
            activities = {e.activity for c in cel.compositions for e in c.event_sequence}
            for contained_type in cls._contained_type_labels(cel.ho_object_type):
                blocked_activities[contained_type].update(activities)
        return blocked_activities

    @classmethod
    def _contained_type_labels(cls, ho_object_type: HigherOrderObjectType) -> set[str]:
        """Labels of every type contained in ``ho_object_type``, at any nesting level.

        A type is blocked from performing the activities of a higher-type that contains it, which
        includes the base object types nested deeper than the direct components.
        """
        labels: set[str] = set()
        for component, _ in ho_object_type.components:
            labels.add(str(component))
            if isinstance(component, HigherOrderObjectType):
                labels |= cls._contained_type_labels(component)
        return labels

    @staticmethod
    def composition_activities(ho_type_label: str, first_activity: str, last_activity: str) -> tuple[str, str, str]:
        """Return the (start, member, end) artificial activity labels for a composition of a higher-type.

        The labels are specific to the higher-type and encode the first/last real activity of the
        composition, matching the notation ``a^{s|a_1}``, ``a^{a_1|a_k}`` and ``a^{e|a_k}``.
        """
        start_activity = f"{ho_type_label}^s|{first_activity}"
        member_activity = f"{ho_type_label}^{first_activity}|{last_activity}"
        end_activity = f"{ho_type_label}^e|{last_activity}"
        return start_activity, member_activity, end_activity

    @staticmethod
    def _member_node_ids(ho_object: HigherOrderObject) -> set[str]:
        member_ids: set[str] = set()
        for component in ho_object.components:
            if isinstance(component, ObjectReference):
                member_ids.add(component.oid)
            else:
                member_ids.add(str(component))
        return member_ids
