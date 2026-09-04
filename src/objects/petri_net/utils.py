from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Collection, Generic, List, Optional, TypeVar, cast

from src.objects.data_types.object_reference import Identity, ObjectID, ObjectReference
from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace
from src.objects.petri_net.petri_net import PetriNet
from src.objects.petri_net.place import Place
from src.objects.petri_net.token import IdentityToken, Token
from src.objects.petri_net.transition import Transition

# pylint: disable=invalid-name, too-few-public-methods


N = TypeVar("N", bound=PetriNet)
P = TypeVar("P", bound=Place)
T = TypeVar("T", bound=Transition)
F = TypeVar("F", bound=Arc)
IT = TypeVar("IT", bound=IdentityToken)
TO = TypeVar("TO", bound=Token)


@dataclass(frozen=True)
class PetriNetPropertyCache(Generic[N, P, T, F], PetriNet[P, T, F]):

    net: N = field(default_factory=PetriNet)  # type: ignore
    pre_arc_cache: dict[P | T, set[F]] = field(init=False)
    post_arc_cache: dict[P | T, set[F]] = field(init=False)
    arcs_from_to_cache: dict[tuple[P, T], list[F]] = field(init=False)
    transitions_with_arc_type_cache: dict[ArcType, set[T]] = field(init=False)
    transitions_with_unique_arc_type_cache: dict[ArcType, set[T]] = field(init=False)
    transitions_label_lookup_cache: dict[Any, set[T]] = field(init=False)

    def __post_init__(self) -> None:
        nodes: set[P | T] = self.net.transitions | self.net.places
        pre_arc_cache: dict[P | T, set[F]] = {node: PetriNetUtils.get_pre_set_arcs(self.net, node) for node in nodes}
        post_arc_cache: dict[P | T, set[F]] = {node: PetriNetUtils.get_post_set_arcs(self.net, node) for node in nodes}
        arcs_from_to_cache: dict[tuple[P, T], list[F]] = defaultdict(list)
        for arc in self.net.arcs:
            if isinstance(arc.source, Place):
                arcs_from_to_cache[(cast(P, arc.source), cast(T, arc.target))].append(arc)
            else:
                arcs_from_to_cache[(cast(P, arc.target), cast(T, arc.source))].append(arc)
        transitions_with_arc_type_cache: dict[ArcType, set[T]] = {
            a_type: PetriNetUtils.get_transitions_with_arc_type(self.net, a_type) for a_type in ArcType
        }
        transitions_with_unique_arc_type_cache: dict[ArcType, set[T]] = {
            a_type: PetriNetUtils.get_transitions_with_unique_arc_type(self.net, a_type) for a_type in ArcType
        }
        transitions_label_lookup_cache: dict[Any, set[T]] = defaultdict(set)
        for transition in self.net.transitions:
            transitions_label_lookup_cache[transition.label].add(transition)

        object.__setattr__(self, "arcs", self.net.arcs)
        object.__setattr__(self, "payload", self.net.payload)
        object.__setattr__(self, "places", self.net.places)
        object.__setattr__(self, "transitions", self.net.transitions)
        object.__setattr__(self, "pre_arc_cache", pre_arc_cache)
        object.__setattr__(self, "post_arc_cache", post_arc_cache)
        object.__setattr__(self, "arcs_from_to_cache", arcs_from_to_cache)
        object.__setattr__(self, "transitions_with_arc_type_cache", transitions_with_arc_type_cache)
        object.__setattr__(self, "transitions_with_unique_arc_type_cache", transitions_with_unique_arc_type_cache)
        object.__setattr__(self, "transitions_label_lookup_cache", transitions_label_lookup_cache)


class TokenUtils(Generic[TO, P]):
    @staticmethod
    def get_place(token: Token) -> P:
        return token if isinstance(token, Place) else token.place

    @staticmethod
    def get_identity(token: Token) -> ObjectID:
        return None if not isinstance(token, IdentityToken) else token.identity


class MarkingUtils(Generic[P, TO, IT]):
    @staticmethod
    def project_on_places(counter: Counter[TO], retain_zero_elements: bool = False) -> Marking[P]:
        marking: Marking[P] = Marking()
        for token in counter.keys():
            marking[TokenUtils.get_place(token)] += counter[token]
        return (
            marking
            if retain_zero_elements
            else Marking({token: count for token, count in marking.items() if count > 0})
        )

    @staticmethod
    def get_identities_in_marking(counter: Counter[TO]) -> Counter[Identity]:
        ids: Counter[Identity] = Counter()
        for token, count in counter.items():
            ids[TokenUtils.get_identity(token)] += count
        return ids

    @staticmethod
    def get_identities_in_place(counter: Counter[TO], place: P) -> Counter[Identity]:
        ids: Counter[Identity] = Counter()
        for token, count in counter.items():
            if TokenUtils.get_place(token) == place:
                ids[TokenUtils.get_identity(token)] += count
        return ids

    @classmethod
    def get_eligible_transitions(cls, net: N, marking: Marking[TO]) -> set[T]:
        non_zero_places = cls.project_on_places(marking)
        return {
            transition
            for transition in net.transitions
            if all(
                place in non_zero_places.keys() for place in cast(set[P], PetriNetUtils.get_pre_set(net, transition))
            )
        }

    @classmethod
    def get_object_references(cls, marking: Marking[TO]) -> set[ObjectReference]:
        refs: set[ObjectReference] = set()
        for token in marking.keys():
            place: P = TokenUtils.get_place(token)
            refs.add(
                ObjectReference(
                    otype=cast(ObjectAwarePlace, place).object_type if isinstance(place, ObjectAwarePlace) else None,
                    oid=TokenUtils.get_identity(token),
                )
            )
        return refs

    @classmethod
    def is_identity_marking(cls, marking: Marking[TO]) -> bool:
        return isinstance(next(iter(marking.keys())), IdentityToken)


class PetriNetUtils(Generic[N, P, T, F]):
    @classmethod
    def has_unique_arc_type(cls, net: N, node: P | T) -> bool:
        return len(set(map(lambda a: a.type, cls.get_connected_arcs(net, node)))) <= 1

    @classmethod
    def get_pre_set(cls, net: N, node: P | T) -> set[P | T]:
        return set(map(lambda a: a.source, cast(set[F], cls.get_pre_set_arcs(net, node))))

    @staticmethod
    def get_pre_set_arcs(net: N | PetriNetPropertyCache, node: P | T) -> set[F]:
        if isinstance(net, PetriNetPropertyCache):
            return net.pre_arc_cache.get(node, set())
        return {a for a in net.arcs if a.target == node}

    @classmethod
    def get_pre_set_arcs_of_type(cls, net: N, node: P | T, arc_type: ArcType) -> set[F]:
        return {a for a in cls.get_pre_set_arcs(net, node) if a.type is arc_type}

    @classmethod
    def get_post_set(cls, net: N, node: P | T) -> set[P | T]:
        return set(map(lambda a: a.target, cast(set[F], cls.get_post_set_arcs(net, node))))

    @staticmethod
    def get_post_set_arcs(net: N, node: P | T) -> set[F]:
        if isinstance(net, PetriNetPropertyCache):
            return net.post_arc_cache.get(node, set())
        return {a for a in net.arcs if a.source == node}

    @classmethod
    def get_post_set_arcs_of_type(cls, net: N, node: P | T, arc_type: ArcType) -> set[F]:
        return {a for a in cls.get_post_set_arcs(net, node) if a.type is arc_type}

    @classmethod
    def get_neighbors(cls, net: N, node: P | T) -> set[P | T]:
        return cls.get_pre_set(net, node) | cls.get_post_set(net, node)

    @classmethod
    def get_connected_arcs(cls, net: N, node: P | T) -> set[F]:
        return cls.get_pre_set_arcs(net, node) | cls.get_post_set_arcs(net, node)

    @staticmethod
    def get_arcs_from_to(net: N, node_x: P | T, node_y: P | T) -> List[Arc]:
        if isinstance(net, PetriNetPropertyCache):
            if isinstance(node_x, Place):
                return net.arcs_from_to_cache.get((node_x, node_y), [])
            return net.arcs_from_to_cache.get((node_y, node_x), [])
        return [arc for arc in net.arcs if arc.source == node_x and arc.target == node_y]

    @staticmethod
    def get_place_by_name(net: N, name: str) -> Optional[P]:
        return next((place for place in net.places if place.name == name), None)

    @staticmethod
    def get_transition_by_name(net: N, name: Any) -> Optional[T]:
        return next((transition for transition in net.transitions if transition.name == name), None)

    @staticmethod
    def get_transitions_by_label(net: N, label: Any) -> set[T]:
        if isinstance(net, PetriNetPropertyCache):
            return net.transitions_label_lookup_cache.get(label, set())
        return {transition for transition in net.transitions if transition.label == label}

    @staticmethod
    def get_arc_weights(arcs: Collection[F]) -> set[int]:
        return set(map(lambda a: a.weight, arcs))

    @classmethod
    def get_transitions_with_unique_arc_type(cls, net: N, arc_type: ArcType) -> set[T]:
        if isinstance(net, PetriNetPropertyCache):
            return net.transitions_with_unique_arc_type_cache[arc_type]
        return {
            transition
            for transition in net.transitions
            if {arc.type for arc in cls.get_connected_arcs(net, transition)} == {arc_type}
        }

    @classmethod
    def get_connected_arc_types(cls, net: N, node: P | T) -> set[ArcType]:
        return {arc.type for arc in cls.get_connected_arcs(net, node)}

    @classmethod
    def get_transitions_with_arc_type(cls, net: N, arc_type: ArcType) -> set[T]:
        if isinstance(net, PetriNetPropertyCache):
            return net.transitions_with_arc_type_cache[arc_type]
        return {
            transition for transition in net.transitions if arc_type in cls.get_connected_arc_types(net, transition)
        }

    @staticmethod
    def get_connected_transition(arc: F) -> T:
        return arc.source if isinstance(arc.source, Transition) else arc.target

    @staticmethod
    def get_connected_place(arc: F) -> P:
        return arc.source if isinstance(arc.source, Place) else arc.target
