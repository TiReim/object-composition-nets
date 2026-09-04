import itertools
from collections import Counter
from typing import TypeVar, cast

from overrides import override

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.factories.token_factory import TokenFactory
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.place import Place
from src.objects.petri_net.semantics import SynchronizingSemantics
from src.objects.petri_net.token import Token
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.utils import PetriNetUtils
from src.objects.petri_net.variable_arc_net.utils import VariableArcNetUtils
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc
from src.objects.petri_net.variable_arc_net.variable_arc_net import VariableArcNet

# pylint: disable=too-many-arguments, invalid-name


T = TypeVar("T", bound=Transition)
P = TypeVar("P", bound=Place)
N = TypeVar("N", bound=VariableArcNet)
F = TypeVar("F", bound=VariableArc | Arc)
TO = TypeVar("TO", bound=Token)


class VariableArcNetSemantics(SynchronizingSemantics[N, P, T, F, TO]):
    @classmethod
    @override
    def _get_min_weight_of_surrounding_arcs(cls, net: N, transition: T) -> float:
        regular_arcs = {
            a.weight
            for a in cast(set[F], PetriNetUtils.get_connected_arcs(net, transition))
            if a.type is ArcType.NORMAL
        }
        return min(regular_arcs) if len(regular_arcs) > 0 else float("inf")

    @classmethod
    def get_consumptions(cls, net: N, transition: T, marking: Marking[TO]) -> list[Counter[TO]]:
        regular_arc_weights = VariableArcNetUtils.get_regular_arc_weights_of_connected_arcs(net, transition)
        regular_arc_weight = regular_arc_weights.pop() if regular_arc_weights else None
        lower_bound = regular_arc_weight if regular_arc_weight is not None else 1
        return [
            Counter(
                {
                    cast(TO, TokenFactory.create_token(place, identity)): weight
                    for (identity, weight), place in itertools.product(
                        consumption.items(), cast(set[P], PetriNetUtils.get_pre_set(net, transition))
                    )
                }
            )
            for consumption in [
                c
                for c in cls._get_identity_consumptions_up_to_weight(net, transition, marking)
                if lower_bound <= sum(c.values()) <= cls._get_maximal_available_identities(net, transition, marking)
            ]
        ]
