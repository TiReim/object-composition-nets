import itertools
from collections import Counter
from typing import TypeVar, cast

from src.objects.data_types.object_reference import (
    ObjectID,
    ObjectReference,
    ObjectReferenceUtils,
    ObjectType,
)
from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace
from src.objects.petri_net.oc_nets.oc_petri_net import ObjectCentricPetriNet
from src.objects.petri_net.oc_nets.utils import GuardUtils, ObjectCentricPetriNetUtils
from src.objects.petri_net.semantics import GuardedSemantics
from src.objects.petri_net.token import IdentityToken, Token
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.utils import MarkingUtils, PetriNetUtils, TokenUtils
from src.objects.petri_net.variable_arc_net.semantics import VariableArcNetSemantics
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc
from src.utils.counter import CounterUtils

# pylint: disable=too-many-arguments, invalid-name

ON = TypeVar("ON", bound=ObjectCentricPetriNet)
OP = TypeVar("OP", bound=ObjectAwarePlace)
T = TypeVar("T", bound=Transition)
F = TypeVar("F", bound=Arc | VariableArc)
TO = TypeVar("TO", bound=Token)


class ObjectCentricSemantics(VariableArcNetSemantics[ON, OP, T, F, TO]):
    @classmethod
    def get_consumptions(
        cls,
        net: ON,
        transition: T,
        marking: Marking[TO],
        subnets: dict[ObjectID, ON] = None,
    ) -> list[Counter[TO]]:
        required_object_types = {
            place.object_type for place in cast(set[OP], PetriNetUtils.get_pre_set(net, transition))
        }
        subnets = (
            subnets
            if subnets is not None
            else {
                ot: ObjectCentricPetriNetUtils.project_on_object_type(net, ot)  # type: ignore
                for ot in required_object_types
            }
        )
        type_consumptions = {
            ot: super(ObjectCentricSemantics, cls).get_consumptions(subnet, transition, marking)
            for (ot, subnet) in subnets.items()
            if ot in required_object_types
        }
        consumptions: list[Counter[TO]] = [Counter()]
        for type_consumption in type_consumptions.values():
            if len(type_consumption) == 0:
                return []
            consumptions = [a | b for (a, b) in itertools.product(type_consumption, consumptions)]
        return consumptions if consumptions != [Counter()] else []

    @classmethod
    def get_productions(
        cls,
        net: ON,
        transition: T,
        marking: Marking[TO],
        consumption: Counter[TO],
        subnets: dict[ObjectID, ON] = None,
    ) -> list[Counter[TO]]:
        relevant_types = {place.object_type for place in cast(set[OP], PetriNetUtils.get_neighbors(net, transition))}
        subnets = (
            subnets
            if subnets is not None
            else {
                ot: ObjectCentricPetriNetUtils.project_on_object_type(net, ot) for ot in relevant_types  # type: ignore
            }
        )
        type_consumption = {
            ot: Counter(
                {
                    token: k
                    for (token, k) in consumption.items()
                    if cast(OP, TokenUtils.get_place(token)).object_type == ot
                }
            )
            for ot in relevant_types
        }
        production: Counter[TO] = Counter()
        for object_type in relevant_types:
            type_production = super(ObjectCentricSemantics, cls).get_productions(
                subnets[object_type], transition, marking, type_consumption[object_type]
            )
            if len(type_production) > 0:
                production |= type_production[0]
        return [production]

    @staticmethod
    def compute_min_allowed_ids(net: ON, transition: T) -> Counter[ObjectType]:
        result: Counter[ObjectType] = Counter()
        result.update(
            {
                cast(OP, arc.source).object_type: 1
                for arc in cast(set[F], PetriNetUtils.get_pre_set_arcs(net, transition))
                if arc.type == ArcType.VARIABLE
            }
        )
        result.update(
            {
                cast(OP, arc.source).object_type: 1 if arc.weight is None else arc.weight
                for arc in cast(set[F], PetriNetUtils.get_pre_set_arcs(net, transition))
                if arc.type == ArcType.NORMAL
            }
        )
        return result

    @staticmethod
    def compute_max_allowed_ids(net: ON, transition: T) -> Counter[ObjectType]:
        result: Counter[ObjectType] = Counter()
        result.update(
            {
                cast(OP, arc.source).object_type: 1000000
                for arc in cast(set[F], PetriNetUtils.get_pre_set_arcs(net, transition))
                if arc.type == ArcType.VARIABLE
            }
        )
        result.update(
            {
                cast(OP, arc.source).object_type: 1 if arc.weight is None else arc.weight
                for arc in cast(set[F], PetriNetUtils.get_pre_set_arcs(net, transition))
                if arc.type == ArcType.NORMAL
            }
        )
        return result


class GuardedObjectCentricSemantics(ObjectCentricSemantics[ON, OP, T, F, TO], GuardedSemantics[ON, OP, T, F, TO]):
    @classmethod
    def get_consumptions(
        cls,
        net: ON,
        transition: T,
        marking: Marking[TO],
        subnets: dict[ObjectID, ON] = None,
    ) -> list[Counter[TO]]:
        required_objects = GuardUtils.get_required_objects(transition.guard)
        if required_objects and MarkingUtils.is_identity_marking(marking):
            return cls._calculate_consumption_based_on_guard(net, transition, marking, required_objects)  # type: ignore
        return super().get_consumptions(net, transition, marking, subnets)

    @classmethod
    def _calculate_consumption_based_on_guard(
        cls, net: ON, transition: T, marking: Marking[TO], required_objects: set[ObjectReference]
    ) -> list[Counter[IdentityToken]]:
        object_reference_dict = ObjectReferenceUtils.dictify_set(required_objects)
        con = Counter[IdentityToken](
            {
                IdentityToken(place, identity): 1
                for place in cast(set[OP], PetriNetUtils.get_pre_set(net, transition))
                for identity in object_reference_dict[place.object_type]
            }
        )
        if CounterUtils.is_empty(con - marking):  # type: ignore
            return [con]
        return []
