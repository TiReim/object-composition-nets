from collections import Counter
from dataclasses import dataclass
from typing import Union

from src.objects.data_types.object_reference import ObjectReference


@dataclass(frozen=True)
class HigherOrderObjectType:
    components: frozenset[tuple[Union["HigherOrderObjectType", str], int]]

    @property
    def object_type(self) -> str:
        return "{" + ", ".join(sorted([str(c) + str(i) for c, i in self.components])) + "}"

    def depth(self) -> int:
        max_depth = 0
        for component, _ in self.components:
            if isinstance(component, HigherOrderObjectType):
                max_depth = max(max_depth, component.depth())
        return max_depth + 1

    def base_object_types(self) -> set[str]:
        result = set()
        for component, _ in self.components:
            if isinstance(component, HigherOrderObjectType):
                result.update(component.base_object_types())
            else:
                result.add(component)
        return result

    def decompose(self, scope: int) -> set[Union["HigherOrderObjectType", str]]:
        if scope == 0:
            return {self}
        result: set[Union["HigherOrderObjectType", str]] = set()
        for component, _ in self.components:
            if isinstance(component, HigherOrderObjectType):
                result.update(component.decompose(scope - 1))
            else:
                result.add(component)
        return result

    def contains_other(self, other: "HigherOrderObjectType") -> bool:
        if self == other:
            return True
        # ``self`` contains ``other`` if every component of ``other`` can be assigned to a component of
        # ``self`` whose (higher-)type contains it, without exceeding that component's capacity, while
        # every component of ``self`` receives at least one component of ``other``. A single component
        # of ``self`` may absorb several components of ``other`` (e.g. two packages with different item
        # counts, {Package, Item^3} and {Package, Item^1}, both fitting the slot {Package, Item^3}^2),
        # so this is a capacity-bounded many-to-one assignment rather than a positional comparison.
        self_slots = list(self.components)
        other_components = list(other.components)

        def component_contains(container: "HigherOrderObjectType | str", contained: "HigherOrderObjectType | str") -> bool:
            if isinstance(container, HigherOrderObjectType) and isinstance(contained, HigherOrderObjectType):
                return container.contains_other(contained)
            return container == contained

        remaining = [capacity for _, capacity in self_slots]
        assigned = [False] * len(self_slots)

        def assign(index: int) -> bool:
            if index == len(other_components):
                return all(assigned)
            component, capacity = other_components[index]
            for slot, (slot_component, _) in enumerate(self_slots):
                if remaining[slot] >= capacity and component_contains(slot_component, component):
                    remaining[slot] -= capacity
                    was_assigned = assigned[slot]
                    assigned[slot] = True
                    if assign(index + 1):
                        return True
                    remaining[slot] += capacity
                    assigned[slot] = was_assigned
            return False

        return assign(0)

    def __str__(self):
        return self.object_type

    def __repr__(self):
        return self.object_type


@dataclass(frozen=True)
class HigherOrderObject:
    components: frozenset[Union["HigherOrderObject", ObjectReference]]

    @property
    def higher_order_object_type(self) -> HigherOrderObjectType:
        types_and_capacities: Counter[HigherOrderObjectType | str] = Counter()
        for component in self.components:
            if isinstance(component, ObjectReference):
                types_and_capacities[component.otype] += 1
            else:
                types_and_capacities[component.higher_order_object_type] += 1
        return HigherOrderObjectType(frozenset(types_and_capacities.items()))

    def object_type_structure(self) -> str:
        substructures: set[str] = set()
        for component in self.components:
            if isinstance(component, ObjectReference):
                substructures.add(component.otype)
            else:
                substructures.add(component.object_type_structure())
        return "{" + ", ".join(sorted(substructures)) + "}"

    def contained_objects(self) -> set[str]:
        result = set()
        result.add(str(self))
        for component in self.components:
            if isinstance(component, ObjectReference):
                result.add(component.oid)
            else:
                result.update(component.contained_objects())
        return result

    def decompose(self, depth: int) -> set[Union["HigherOrderObject", ObjectReference]]:
        if depth == 0:
            return {self}
        result: set[Union["HigherOrderObject", ObjectReference]] = set()
        for component in self.components:
            if isinstance(component, ObjectReference):
                result.add(component)
            else:
                result.update(component.decompose(depth - 1))
        return result

    def check_if_valid(self) -> bool:
        result = set()
        for component in self.components:
            if isinstance(component, ObjectReference):
                if component in result:
                    return False
                result.add(component)
            else:
                flattened = component.flatten()
                if result & flattened:
                    return False
                result.update(flattened)
        return True

    def all_contained_objects(self) -> set[Union["HigherOrderObject", ObjectReference]]:
        result: set[Union["HigherOrderObject", ObjectReference]] = set()
        result.add(self)
        for component in self.components:
            if isinstance(component, ObjectReference):
                result.add(component)
            else:
                result.update(component.all_contained_objects())
        return result

    def flatten(self) -> set[ObjectReference]:
        result = set()
        for component in self.components:
            if isinstance(component, ObjectReference):
                result.add(component)
            else:
                result.update(component.flatten())
        return result

    def __str__(self):
        return "{" + ", ".join(sorted([str(c) for c in self.components])) + "}"
