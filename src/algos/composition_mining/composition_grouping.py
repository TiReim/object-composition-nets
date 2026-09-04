from collections import Counter, defaultdict
from dataclasses import dataclass

from src.algos.composition_mining.compute_object_compositions import ObjectComposition
from src.objects.data_types.higher_order_object_types import HigherOrderObject, HigherOrderObjectType
from src.objects.data_types.object_reference import ObjectReference
from src.objects.graphs.object_centric_event_graph.oceg import ObjectNode


@dataclass(frozen=True)
class CompositionalEventLog:
    ho_object_type: HigherOrderObjectType
    compositions: frozenset[ObjectComposition]

    @property
    def variants(self) -> set[tuple[str, ...]]:
        return set(tuple(e.activity for e in c.event_sequence) for c in self.compositions)


class CompositionGrouper:
    @classmethod
    def compute_compositional_event_logs(cls, compositions: list[ObjectComposition]) -> set[CompositionalEventLog]:
        # Discover the nesting structure of the higher-order objects
        compositions_with_ho_objects = cls.compute_ho_object_of_compositions(compositions)
        # Group compositions by their higher-order object type structure
        grouped_compositions: dict[str, set[ObjectComposition]] = defaultdict(set)
        for composition in compositions_with_ho_objects:
            grouped_compositions[composition.ho_object.object_type_structure()].add(composition)
        # Create compositional event logs for each group
        compositional_event_logs: set[CompositionalEventLog] = set()
        for composition_group in grouped_compositions.values():
            ho_object_type = cls._compute_ho_object_type({c.ho_object for c in composition_group})
            compositional_event_logs.add(
                CompositionalEventLog(ho_object_type=ho_object_type, compositions=frozenset(composition_group))
            )
        return compositional_event_logs

    @classmethod
    def _compute_ho_object_type(cls, ho_objects: set[HigherOrderObject]) -> HigherOrderObjectType:
        # We assume that all objects in ho_objects have an identical object type structure
        components_grouped_by_type: dict[str, set[HigherOrderObject]] = defaultdict(set)
        number_of_components_per_type: dict[str, set[int]] = defaultdict(set)
        for ho_object in ho_objects:
            count_of_types: Counter[str] = Counter()
            for component in ho_object.components:
                otype = component.otype if isinstance(component, ObjectReference) else component.object_type_structure()
                count_of_types[otype] += 1
                if isinstance(component, HigherOrderObject):
                    components_grouped_by_type[otype].add(component)
            for otype, count in count_of_types.items():
                number_of_components_per_type[otype].add(count)
        set_of_components: set[tuple[HigherOrderObjectType | str, int]] = set()
        for otype, counts in number_of_components_per_type.items():
            if components_grouped_by_type[otype]:
                set_of_components.add(
                    (
                        cls._compute_ho_object_type(components_grouped_by_type[otype]),
                        max(counts),
                    )
                )
            else:
                set_of_components.add((otype, max(counts)))
        return HigherOrderObjectType(frozenset(set_of_components))

    @classmethod
    def compute_ho_object_of_compositions(cls, compositions: list[ObjectComposition]) -> list[ObjectComposition]:
        active_compositions: list[ObjectComposition] = []
        compositions = list(sorted(compositions, key=lambda c: (c.start_time.timestamp(), -c.end_time.timestamp())))
        for composition in compositions:
            current_start_time = composition.start_time
            # pylint: disable=cell-var-from-loop
            active_compositions = list(filter(lambda r: current_start_time <= r.end_time, active_compositions))
            maximal_sub_compositions: list[ObjectComposition] = []
            for other_composition in sorted(active_compositions, key=lambda c: len(c.objects), reverse=True):
                if set(composition.objects) >= set(other_composition.objects) and not any(
                    other_composition.objects < max_comp.objects for max_comp in maximal_sub_compositions
                ):
                    maximal_sub_compositions.append(other_composition)
            composed_objects: set[ObjectNode] = set()
            for contained_composition in maximal_sub_compositions:
                composed_objects.update(contained_composition.objects)
            remaining_instances = composition.objects.difference(composed_objects)
            composition.ho_object = HigherOrderObject(
                frozenset(
                    {ObjectReference(o.object_type, o.object_id) for o in remaining_instances}
                    | {c.ho_object for c in maximal_sub_compositions}
                )
            )
            active_compositions.append(composition)
        return compositions
