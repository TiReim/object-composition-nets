from collections import Counter, defaultdict
from itertools import chain, combinations, product
from typing import TypeVar, cast

from src.objects.data_types.higher_order_object_types import HigherOrderObject, HigherOrderObjectType
from src.objects.data_types.object_reference import ObjectID, ObjectReference
from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.object_composition_nets.object_composition_net import ObjectCompositionNet
from src.objects.petri_net.object_composition_nets.object_composition_tokens import ObjectCompositionIdentityToken
from src.objects.petri_net.object_composition_nets.higher_object_aware_place import HigherObjectAwarePlace
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.oc_nets.semantics import ObjectCentricSemantics
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.utils import PetriNetUtils
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc

# pylint: disable=too-many-arguments, invalid-name, too-many-locals

CN = TypeVar("CN", bound=ObjectCompositionNet)
P = TypeVar("P", bound=HigherObjectAwarePlace)
T = TypeVar("T", bound=Transition)
F = TypeVar("F", bound=Arc | VariableArc)
TO = TypeVar("TO", bound=ObjectCompositionIdentityToken)


class ObjectCompositionSemantics(ObjectCentricSemantics[CN, P, T, F, TO]):
    @classmethod
    def get_consumptions(
        cls,
        net: CN,
        transition: T,
        marking: Marking[TO],
        subnets: dict[ObjectID, CN] = None,
    ) -> list[Counter[TO]]:
        # Save the object from each token in the preset (superclasses only work with identity string)
        id_reference: dict[str, HigherOrderObject] = {}
        pre_set = PetriNetUtils.get_pre_set(net, transition)
        for token in marking.keys():
            if token.place in pre_set:
                id_reference[token.identity] = token.higher_order_object

        # Compute consumption just as for OCPN (the created tokens are objects of the type IdentityToken)
        pre_consumption = super(ObjectCompositionSemantics, cls).get_consumptions(net, transition, marking, subnets)

        # Enrich tokens with MultiObject
        consumption = []
        for c in pre_consumption:
            consumption.append(
                Counter(
                    {
                        cast(TO, ObjectCompositionIdentityToken(token.place, id_reference[token.identity])): k
                        for token, k in c.items()
                    }
                )
            )
        return consumption

    @classmethod
    def get_productions(
        cls,
        net: CN,
        transition: T,
        marking: Marking[TO],
        consumption: Counter[TO],
        subnets: dict[ObjectID, CN] = None,
    ) -> list[Counter[TO]]:
        if "scope" not in transition.payload:
            scope = (0, 0)
        else:
            scope = cast(tuple[int, int], transition.payload["scope"])
        output_places = cast(set[HigherObjectAwarePlace], PetriNetUtils.get_post_set(net, transition))
        # Extract consumed higher-order objects:
        consumed_objects = set(token.higher_order_object for token in consumption.keys())
        # Decompose object by scope
        decomposed_objects = set.union(*[obj.decompose(scope[0]) for obj in consumed_objects])
        # Determine object types of output places
        output_object_types = set(place.higher_order_object_type for place in output_places)
        # Compute possible compositions of decomposed objects that fit the output object types
        per_type_compositions: dict[HigherOrderObjectType, set[HigherOrderObject]] = {}
        for output_object_type in output_object_types:
            per_type_compositions[output_object_type] = cls._compute_compositions_for_object_type(
                decomposed_objects, output_object_type, scope[1]
            )
        # For each object type, determine how many output tokens are allowed by the weights
        per_type_weight = cls._compute_weights_per_object_type(net, transition)
        # For each object type, determine which decomposed must be covered by the produced tokens
        per_type_coverage = {
            output_object_type: cls._compute_coverage_per_type(decomposed_objects, output_object_type, scope[1])
            for output_object_type in output_object_types
        }
        # For each object type, compute all valid combinations of output tokens, i.e.,
        # all combinations of compositions that satisfy the weight and coverage constraints
        per_type_production = cls._compute_all_valid_productions_per_object_type(
            per_type_compositions, per_type_weight, per_type_coverage
        )
        # If some output type admits no valid composition, the consumed higher-objects cannot be
        # (re)assembled into every required output token: the transition deadlocks for this
        # consumption and produces nothing (cf. the (1,1)/(2,1) deadlocks in the paper).
        if any(output_object_type not in per_type_production for output_object_type in output_object_types):
            return []
        # Combine the valid combinations for each object type to get the final productions
        productions = []
        for prod in product(*per_type_production.values()):
            combined = dict(zip(per_type_production.keys(), prod))
            productions.append(
                Counter(
                    {
                        cast(TO, ObjectCompositionIdentityToken(place, obj)): 1
                        for place in output_places
                        for obj in combined[place.higher_order_object_type]
                    }
                )
            )

        return productions

    @classmethod
    def _compute_all_valid_productions_per_object_type(
        cls,
        possible_compositions: dict[HigherOrderObjectType, set[HigherOrderObject]],
        type_weight_map,
        type_coverage_map,
    ) -> dict[HigherOrderObjectType, list[set[HigherOrderObject]]]:
        all_valid_productions_per_type = defaultdict(list)
        for object_type, compositions in possible_compositions.items():
            if type_weight_map[object_type]:
                for weight in type_weight_map[object_type]:
                    for combination in combinations(compositions, weight):
                        if type_coverage_map[object_type] <= set.union(
                            *[obj.all_contained_objects() for obj in combination]
                        ):
                            all_valid_productions_per_type[object_type].append(set(combination))
            else:
                for combination in chain.from_iterable(
                    combinations(compositions, r) for r in range(1, len(compositions) + 1)
                ):
                    if type_coverage_map[object_type] <= set.union(
                        *[obj.all_contained_objects() for obj in combination]
                    ):
                        all_valid_productions_per_type[object_type].append(set(combination))
        return all_valid_productions_per_type

    @classmethod
    def _compute_weights_per_object_type(cls, net: CN, transition: T) -> dict[HigherOrderObjectType, set[int]]:
        weights_per_object_type: dict[HigherOrderObjectType, set[int]] = defaultdict(set)
        for arc in cast(set[Arc], PetriNetUtils.get_post_set_arcs(net, transition)):
            if arc.type == ArcType.NORMAL:
                if weights_per_object_type[arc.target.higher_order_object_type]:
                    weights_per_object_type[
                        cast(HigherObjectAwarePlace, arc.target).higher_order_object_type
                    ].difference_update({arc.weight})
                else:
                    weights_per_object_type[cast(HigherObjectAwarePlace, arc.target).higher_order_object_type].add(
                        arc.weight
                    )
        return weights_per_object_type

    @classmethod
    def _compute_coverage_per_type(
        cls, objects: set[HigherOrderObject | ObjectReference], object_type: HigherOrderObjectType, scope: int
    ) -> set[HigherOrderObject | ObjectReference]:
        coverage_per_type: set[HigherOrderObject | ObjectReference] = set()
        subtypes = set()
        for i in range(scope, -1, -1):
            subtypes.update(object_type.decompose(i))
        # Base object types that must be covered. A base type shows up either as a bare string (from
        # decomposing a composite higher-type) or as a single-component higher-type (a place typed
        # directly with a base type, since {T} corresponds to the object type T).
        base_subtypes: set[str] = {subtype for subtype in subtypes if isinstance(subtype, str)}
        for subtype in subtypes:
            if isinstance(subtype, HigherOrderObjectType) and len(subtype.components) == 1:
                ((component, _),) = subtype.components
                if isinstance(component, str):
                    base_subtypes.add(component)
        for obj in objects:
            if isinstance(obj, ObjectReference):
                if obj.otype in base_subtypes:
                    coverage_per_type.add(obj)
            elif isinstance(obj, HigherOrderObject):
                # Base objects are carried as single-reference higher-order tokens; reduce them to the
                # underlying reference so they match the bare references contained in produced objects.
                base_reference = cls._as_base_reference(obj)
                if base_reference is not None and base_reference.otype in base_subtypes:
                    coverage_per_type.add(base_reference)
                else:
                    for subtype in subtypes:
                        if isinstance(subtype, HigherOrderObjectType) and subtype.contains_other(
                            obj.higher_order_object_type
                        ):
                            coverage_per_type.add(obj)
        return coverage_per_type

    @classmethod
    def _compute_compositions_for_object_type(
        cls, objects: set[HigherOrderObject | ObjectReference], object_type: HigherOrderObjectType, scope: int
    ) -> set[HigherOrderObject]:
        if scope == 0:
            # No further composition: keep the objects that already have the requested type. A bare
            # object reference (e.g. produced by decomposing a higher-order object down to the base
            # level) is wrapped into a single-component higher-order object so that it can populate a
            # base-typed output place.
            result: set[HigherOrderObject] = set()
            for obj in objects:
                if isinstance(obj, HigherOrderObject) and object_type.contains_other(obj.higher_order_object_type):
                    result.add(obj)
                elif isinstance(obj, ObjectReference):
                    wrapped = HigherOrderObject(frozenset({obj}))
                    if object_type.contains_other(wrapped.higher_order_object_type):
                        result.add(wrapped)
            return result
        components = objects.copy()
        for i in range(min(scope, object_type.depth()) - 1, -1, -1):
            for subtype in object_type.decompose(i):
                if isinstance(subtype, HigherOrderObjectType):
                    new_objects = cls._compute_compositions_for_one_level(components, subtype)
                    components.update(new_objects)
        resulting_compositions = set()
        for obj in components:
            if isinstance(obj, HigherOrderObject) and object_type.contains_other(obj.higher_order_object_type):
                resulting_compositions.add(obj)

        return resulting_compositions

    @staticmethod
    def _as_base_reference(obj: HigherOrderObject) -> ObjectReference | None:
        """Returns the single base reference of a higher-order object wrapping exactly one reference."""
        if len(obj.components) != 1:
            return None
        (only,) = tuple(obj.components)
        return only if isinstance(only, ObjectReference) else None

    @classmethod
    def _compute_compositions_for_one_level(
        cls, components: set[HigherOrderObject | ObjectReference], object_type: HigherOrderObjectType
    ) -> set[HigherOrderObject]:
        new_objects = set()
        components_by_type: dict[HigherOrderObjectType | str, set[HigherOrderObject | ObjectReference]] = defaultdict(
            set
        )
        for component in components:
            for subtype, _ in object_type.components:
                if isinstance(component, ObjectReference) and subtype == component.otype:
                    components_by_type[subtype].add(component)
                elif (
                    isinstance(component, HigherOrderObject)
                    and isinstance(subtype, HigherOrderObjectType)
                    and subtype.contains_other(component.higher_order_object_type)
                ):
                    components_by_type[subtype].add(component)
                elif isinstance(component, HigherOrderObject) and isinstance(subtype, str):
                    # A base object carried as a single-reference higher-order object (the token
                    # representation of a base object) matches a base-type component; unwrap it to the
                    # underlying reference so it composes at the base level.
                    inner = cls._as_base_reference(component)
                    if inner is not None and inner.otype == subtype:
                        components_by_type[subtype].add(inner)

        # For each subtype, get all possible selections of the required capacity
        combinations_per_type: dict[
            HigherOrderObjectType | str, list[set[HigherOrderObject | ObjectReference]]
        ] = defaultdict(list)
        for subtype, capacity in object_type.components:
            if not components_by_type[subtype]:
                return set()
            for i in range(1, max(capacity, len(components_by_type[subtype])) + 1):
                for combination in combinations(components_by_type[subtype], i):
                    combinations_per_type[subtype].append(set(combination))
        for combination in product(*combinations_per_type.values()):
            # combination is a tuple with one element selected from each subtype's list
            new_object = HigherOrderObject(
                frozenset(set.union(*cast(tuple[set[HigherOrderObject | ObjectReference]], combination)))
            )
            if new_object.check_if_valid():
                new_objects.add(new_object)
        return new_objects
