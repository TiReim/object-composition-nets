import copy
from dataclasses import dataclass, field
from typing import Collection, Generic, Iterable, Optional, TypeVar, cast

from src.objects.data_types.object_reference import ObjectReference, ObjectReferenceUtils, ObjectType
from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.guards.all_identities_present_guard import AllIdentitiesPresentGuard
from src.objects.petri_net.guards.composite_guard import CompositeOperator, CompositeTransitionGuard
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace
from src.objects.petri_net.oc_nets.oc_petri_net import ObjectCentricPetriNet
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.transition_guard import TransitionGuard
from src.objects.petri_net.utils import PetriNetPropertyCache, PetriNetUtils
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc

ON = TypeVar("ON", bound=ObjectCentricPetriNet)
OP = TypeVar("OP", bound=ObjectAwarePlace)
T = TypeVar("T", bound=Transition)
VA = TypeVar("VA", bound=VariableArc)
F = TypeVar("F", bound=Arc | VariableArc)


# pylint: disable=too-few-public-methods


class GuardUtils:
    @classmethod
    def get_required_objects(cls, guard: TransitionGuard) -> Optional[set[ObjectReference]]:
        if isinstance(guard, AllIdentitiesPresentGuard):
            return ObjectReferenceUtils.setify_dict(guard.allowed_objects)
        if isinstance(guard, CompositeTransitionGuard):
            allowed_objects: set[ObjectReference] = set()
            for sub_guard in guard.guards:
                if sub_guard is None or not isinstance(sub_guard, AllIdentitiesPresentGuard | CompositeTransitionGuard):
                    continue
                sub_result = cls.get_required_objects(sub_guard)
                if guard.operator == CompositeOperator.ALL:
                    allowed_objects = allowed_objects | sub_result
                else:
                    raise NotImplementedError(
                        f"A guard operator of type {guard.operator} was encountered, "
                        "however currently only CompositeOperator.ALL is considered here."
                    )
            return allowed_objects
        if guard is None:
            return None
        raise NotImplementedError(
            f"A transition guard type {type(guard)} was encountered, "
            "however currently only AllIdentitiesPresentGuard and CompositeOperator are considered here."
        )


@dataclass(frozen=True)
class ObjectCentricPetriNetPropertyCache(
    Generic[ON, OP, T, VA, F], PetriNetPropertyCache[ON, OP, T, F], ObjectCentricPetriNet[OP, T, VA, F]
):
    nested: bool = False
    object_types: set[ObjectType] = field(init=False)
    subset_cache: dict[ObjectType, "ObjectCentricPetriNetPropertyCache"] = field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "object_types", ObjectCentricPetriNetUtils.get_object_types(self.net))
        if self.nested:
            object.__setattr__(
                self,
                "subset_cache",
                {
                    o_type: ObjectCentricPetriNetPropertyCache(
                        net=ObjectCentricPetriNetUtils.project_on_object_type(self.net, o_type)
                    )
                    for o_type in self.object_types
                },
            )


class ObjectCentricPetriNetUtils(Generic[ON, OP, T, F]):
    @classmethod
    def get_object_types(cls, obj: ON | ObjectCentricPetriNetPropertyCache | Iterable[OP]) -> set[ObjectType]:
        if isinstance(obj, ObjectCentricPetriNetPropertyCache):
            return obj.object_types
        if isinstance(obj, ObjectCentricPetriNet):
            return cls.get_object_types(obj.places)
        return set(map(lambda p: p.object_type, cast(Iterable[OP], obj)))

    @staticmethod
    def get_object_types_of_transition(net: ON, transition: T) -> set[ObjectType]:
        return {place.object_type for place in cast(set[OP], PetriNetUtils.get_neighbors(net, transition))}

    @classmethod
    def get_object_types_of_transitions(cls, net: ON, transitions: Collection[T]) -> set[ObjectType]:
        return set.union(*[cls.get_object_types_of_transition(net, transition) for transition in transitions])

    @staticmethod
    def get_object_types_of_variable_arcs_of_transition(net: ON, transition: T) -> set[ObjectType]:
        return {
            arc.source.object_type
            for arc in cast(set[F], PetriNetUtils.get_pre_set_arcs_of_type(net, transition, ArcType.VARIABLE))
        } | {
            arc.target.object_type
            for arc in cast(set[F], PetriNetUtils.get_post_set_arcs_of_type(net, transition, ArcType.VARIABLE))
        }

    @staticmethod
    def get_connected_arcs_to_transition_of_type(net: ON, transition: T, object_type: ObjectType) -> set[F]:
        return {  # type: ignore
            arc
            for arc in cast(Iterable[F], PetriNetUtils.get_connected_arcs(net, transition))
            if (arc.source == transition and cast(OP, arc.target).object_type == object_type)
            or (arc.target == transition and cast(OP, arc.source).object_type == object_type)
        }

    @classmethod
    def project_on_object_type(
        cls, net: ON | ObjectCentricPetriNetPropertyCache, object_type: ObjectType
    ) -> ON | ObjectCentricPetriNetPropertyCache:
        if isinstance(net, ObjectCentricPetriNetPropertyCache) and net.nested:
            return net.subset_cache[object_type]
        projection = type(net)()
        projection.places.update({place for place in net.places if place.object_type == object_type})
        projection.transitions.update(
            {
                transition
                for transition in net.transitions
                if any(
                    place.object_type == object_type
                    for place in cast(set[OP], PetriNetUtils.get_neighbors(net, transition))
                )
            }
        )
        projection.arcs.update(
            {
                arc
                for arc in net.arcs
                if (arc.source in projection.places and arc.source.object_type == object_type)
                or (arc.target in projection.places and arc.target.object_type == object_type)
            }
        )
        projection.payload.update(net.payload)
        return projection

    @classmethod
    def get_subnets(
        cls, net: ON | ObjectCentricPetriNetPropertyCache
    ) -> dict[ObjectType, ON | ObjectCentricPetriNetPropertyCache] | dict[
        ObjectType, ObjectCentricPetriNetPropertyCache
    ]:
        if isinstance(net, ObjectCentricPetriNetPropertyCache) and net.nested:
            return net.subset_cache
        return {ot: ObjectCentricPetriNetUtils.project_on_object_type(net, ot) for ot in cls.get_object_types(net)}

    @classmethod
    def regularize(cls, net: ON) -> ON:
        """
        regularizes all variable arcs that are connected to transitions that have a mixture of regular
        and variable arcs (i.e., the arcs randomly adopt an arc weight of a surrounding regular arc).

        :param net:
        :return:
        """
        regularized: ON = copy.deepcopy(net)
        for transition in net.transitions:
            for object_type in cls.get_object_types_of_transition(net, transition):
                type_arcs = cls.get_connected_arcs_to_transition_of_type(net, transition, object_type)
                if len({arc.type for arc in type_arcs}) > 1:
                    weight = {arc.weight for arc in type_arcs if arc.type is ArcType.NORMAL}.pop()
                    for arc in type_arcs:
                        if arc.type is ArcType.VARIABLE:
                            regularized.arcs.remove(arc)
                            regularized.arcs.add(Arc(source=arc.source, target=arc.target, weight=weight))
        return regularized

    @classmethod
    def sanitize_for_synchronizing_semantics(cls, net: ON):
        sanitized: ON = copy.deepcopy(net)
        for transition in net.transitions:
            removed = False
            for object_type in cls.get_object_types_of_transition(net, transition):
                reg_type_arcs: set[F] = {
                    arc
                    for arc in cls.get_connected_arcs_to_transition_of_type(net, transition, object_type)
                    if arc.type is ArcType.NORMAL
                }
                if len({arc.weight for arc in reg_type_arcs}) > 1:
                    sanitized.transitions.remove(transition)
                    for arc in cast(Iterable[F], PetriNetUtils.get_connected_arcs(net, transition)):
                        sanitized.arcs.remove(arc)
                    removed = True
                    break
            if removed:
                continue
        for place in net.places:
            if not PetriNetUtils.get_connected_arcs(sanitized, place):
                sanitized.places.remove(place)
        return sanitized

    @staticmethod
    def filter_places_by_object_type(places: set[OP], object_type: ObjectType) -> set[OP]:
        return set(filter(lambda place: place.object_type == object_type, places))
