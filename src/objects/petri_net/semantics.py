import itertools
from abc import ABC, abstractmethod
from collections import Counter
from typing import Generic, TypeVar, cast

from src.objects.data_types.object_reference import Identity
from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.factories.token_factory import TokenFactory
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.petri_net import PetriNet
from src.objects.petri_net.place import Place
from src.objects.petri_net.token import Token
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.utils import MarkingUtils, PetriNetUtils, TokenUtils

# pylint: disable=too-many-arguments,too-many-locals, invalid-name

T = TypeVar("T", bound=Transition)
P = TypeVar("P", bound=Place)
N = TypeVar("N", bound=PetriNet)
F = TypeVar("F", bound=Arc)
TO = TypeVar("TO", bound=Token)


class Semantics(Generic[N, P, T, F, TO]):
    """
    Basic class for Petri net semantics.
    Defines the main interfaces of any semantics.
    """

    @staticmethod
    @abstractmethod
    def is_applicable(net: N) -> bool:
        """
        indicates if the semantics is applicable for the input net
        """

    @staticmethod
    @abstractmethod
    def get_consumptions(net: N, transition: T, marking: Marking[TO]) -> list[Counter[TO]]:
        """
        Provides the possible token consumptions for a given transition in a marking.
        If the transition is not enabled, the returned set is empty.
        For a regular Petri net, the consumption of an enabled transition is always a
        singleton (i.e., the preset of the transition).

        :param net: input net
        :param transition: transition to consider
        :param marking: marking to use
        :return: set of possible consumptions
        """

    @staticmethod
    @abstractmethod
    def get_productions(net: N, transition: T, marking: Marking[TO], consumption: Counter[TO]) -> list[Counter[TO]]:
        """
        Provides the possible token productions for a given transition in a marking with a given consumption.
        If the transition is not enabled, the returned set is empty.
        For a regular Petri net, the production of an enabled transition is always a
        singleton (i.e., the postset of the transition).

        :param net: input net
        :param transition: transition to consider
        :param marking: marking to use
        :param consumption: consumption to use for the production
        :return: set of possible consumptions
        """

    @classmethod
    def is_enabled(cls, net: N, transition: T, marking: Marking[TO]) -> bool:
        """
        checks if a transition t is enabled in some marking M.
        equivalent to a non-empty consumption set of the transition and marking.

        :param net: input net
        :param transition: transition to consider
        :param marking:  marking to use
        :return: true iff the transition is enabled in the marking
        """
        return len(cls.get_consumptions(net, transition, marking)) > 0

    @classmethod
    def get_enabled_transitions(cls, net: N, marking: Marking[TO]) -> set[T]:
        """
        returns the set of enabled transitions in the marked net (net,marking)
        :param net:
        :param marking:
        :return:
        """
        return {
            transition
            for transition in cast(
                set[T],
                MarkingUtils.get_eligible_transitions(
                    net,
                    marking,
                ),
            )
            if cls.is_enabled(net, transition, marking)
        }

    @classmethod
    def is_legal(
        cls, net: N, transition: T, marking: Marking[TO], consumption: Counter[TO], production: Counter[TO]
    ) -> bool:
        """
        checks if the given consumption and production pair corresponds to the marking and transition.
        true iff the consumption is one of the available consumptions for the given transition and marking, and,
        iff the production can be derived from the consumption.

        :param net:
        :param transition:
        :param marking:
        :param consumption:
        :param production:
        :return:
        """
        return consumption in cls.get_consumptions(net, transition, marking) and production in cls.get_productions(
            net, transition, marking, consumption
        )

    @classmethod
    def fire(
        cls,
        net: N,
        transition: T,
        marking: Marking[TO],
        consumption: Counter[TO],
        production: Counter[TO],
        sanity_check=True,
    ) -> Marking[TO]:
        if not sanity_check or cls.is_legal(net, transition, marking, consumption, production):
            return (marking - consumption) + production
        raise ValueError(
            f"transition {transition.name} is not enabled in marking {marking} for consumption {consumption} "
            f"and production {production}"
        )


class GuardedSemantics(Semantics[N, P, T, F, TO], ABC):
    """
    Guarded semantics additionally take transition guards into account, i.e., as specified by the
    .guard() function of the GuardedTransition class
    """

    @staticmethod
    def evaluate_guard(transition: T, marking: Marking[TO], consumption: Counter[TO]) -> bool:
        return transition.guard is None or transition.guard.evaluate(marking, consumption)

    @classmethod
    def is_legal(
        cls,
        net: N,
        transition: T,
        marking: Marking[TO],
        consumption: Counter[TO],
        production: Counter[TO],
    ) -> bool:
        return super().is_legal(net, transition, marking, consumption, production) and cls.evaluate_guard(
            transition, marking, consumption
        )


class SynchronizingSemantics(Semantics[N, P, T, F, TO]):
    """
    Synchronizing semantics assume agreement on the number of tokens consumed per arc, upon firing a transition.
    Hence, every regular arc connected to the same transition should have the same weight.
    We additionally assume that, if a transition has a connected arc, it has at least one incoming and one outgoing
    arc, i.e.,, token producers/consumers are not allowed.

    In the code, we 'stub' regular tokens (i.e., places) as identity tokens with a fixed identity; this enhances
    reuse of code.
    """

    @staticmethod
    def is_applicable(net: N) -> bool:
        for transition in net.transitions:
            if not PetriNetUtils.get_connected_arcs(net, transition):
                continue
            if not PetriNetUtils.get_pre_set_arcs(net, transition) or not PetriNetUtils.get_post_set_arcs(
                net, transition
            ):
                return False
            if (
                len(
                    {
                        arc.weight
                        for arc in cast(set[Arc], PetriNetUtils.get_connected_arcs(net, transition))
                        if arc.type is ArcType.NORMAL
                    }
                )
                != 1
            ):
                return False
        return True

    @classmethod
    def _get_min_weight_of_surrounding_arcs(cls, net: N, transition: T) -> float:
        return min(PetriNetUtils.get_arc_weights(PetriNetUtils.get_connected_arcs(net, transition)))

    @classmethod
    def _get_min_available_tokens_in_marking(cls, net: N, transition: T, marking: Marking[TO]) -> int:
        return min(
            (
                sum((marking[token] for token, v in marking.items() if TokenUtils.get_place(token) == place))
                for place in PetriNetUtils.get_pre_set(net, transition)
            )
        )

    @classmethod
    def _get_identities_available_for_marking(cls, net: N, transition: T, marking: Marking[TO]) -> Counter[Identity]:
        identities = MarkingUtils.get_identities_in_marking(marking)
        max_weight: int = cls._get_maximal_available_identities(net, transition, marking)
        for pre_place in cast(set[P], PetriNetUtils.get_pre_set(net, transition)):
            pre_identities: Counter[Identity] = Counter()
            for token, count in marking.items():
                if pre_place == TokenUtils.get_place(token):
                    pre_identities = pre_identities | Counter({TokenUtils.get_identity(token): min(count, max_weight)})
            identities = identities & pre_identities
        return identities

    @classmethod
    def _get_maximal_available_identities(cls, net: N, transition: T, marking: Marking[TO]) -> int:
        return int(
            min(
                cls._get_min_weight_of_surrounding_arcs(net, transition),
                cls._get_min_available_tokens_in_marking(net, transition, marking),
            )
        )

    @classmethod
    def _get_identity_consumptions_up_to_weight(
        cls, net: N, transition: T, marking: Marking[TO]
    ) -> list[Counter[Identity]]:
        consumptions: list[Counter[Identity]] = []
        identities = cls._get_identities_available_for_marking(net, transition, marking)
        max_weight: int = cls._get_maximal_available_identities(net, transition, marking)
        for identity, available in identities.items():
            place_consumptions = []
            for weight in range(min(max_weight, available) + 1):
                place_consumptions.append(Counter({identity: weight}))
            new_members = []
            for consumption, place_consumption in itertools.product(consumptions, place_consumptions):
                combi = Counter(consumption) | place_consumption
                if sum(combi.values()) <= max_weight:
                    new_members.append(combi)
            consumptions.extend(member for member in new_members if member not in consumptions)
            consumptions.extend(member for member in place_consumptions if member not in consumptions)
        return consumptions

    @classmethod
    def get_consumptions(cls, net: N, transition: T, marking: Marking[TO]) -> list[Counter[TO]]:
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
                if sum(c.values()) == cls._get_maximal_available_identities(net, transition, marking)
            ]
        ]

    @classmethod
    def get_productions(
        cls, net: N, transition: T, marking: Marking[TO], consumption: Counter[TO]
    ) -> list[Counter[TO]]:
        production: Counter[TO] = Counter()
        per_place_consumption = MarkingUtils.get_identities_in_place(
            consumption, cast(P, next(iter(PetriNetUtils.get_pre_set(net, transition))))
        )
        for place in cast(set[P], PetriNetUtils.get_post_set(net, transition)):
            for identity, weight in per_place_consumption.items():
                production[cast(TO, TokenFactory.create_token(place, identity))] = weight
        return [production]


class ClassicalSemantics(Semantics[N, P, T, F, P]):
    """
    Semantics for 'classical' weighted nets (i.e., PetriNet class).
    Per marking and enabled transition, there is exactly one consumption and corresponding consumption.
    """

    @staticmethod
    def is_applicable(net: N) -> bool:
        return True

    @staticmethod
    def pre_set_is_sufficiently_marked(net: N, transition: T, marking: Marking[P]):
        return all(
            marking[arc.source] >= arc.weight for arc in cast(set[F], PetriNetUtils.get_pre_set_arcs(net, transition))
        )

    @classmethod
    def get_productions(cls, net: N, transition: T, marking: Marking[P], consumption: Counter[P]) -> list[Counter[P]]:
        return (
            []
            if consumption not in cls.get_consumptions(net, transition, marking)
            else [
                Counter(
                    {arc.target: arc.weight for arc in cast(set[F], PetriNetUtils.get_post_set_arcs(net, transition))}
                )
            ]
        )

    @staticmethod
    def get_consumptions(net: N, transition: T, marking: Marking[P]) -> list[Counter[P]]:
        return (
            []
            if any(
                arc.source not in marking or marking[arc.source] < arc.weight
                for arc in cast(set[F], PetriNetUtils.get_pre_set_arcs(net, transition))
            )
            else [
                Counter(
                    {arc.source: arc.weight for arc in cast(set[F], PetriNetUtils.get_pre_set_arcs(net, transition))}
                )
            ]
        )

    @classmethod
    def fire(
        cls,
        net: N,
        transition: T,
        marking: Marking[P],
        consumption: Counter[P] = None,
        production: Counter[P] = None,
        sanity_check=True,
    ) -> Marking[P]:
        if not cls.is_enabled(net, transition, marking):
            raise ValueError(f"transition {transition.name} is not enabled in marking {marking}")
        consumption = (
            consumption if consumption is not None else next(iter(cls.get_consumptions(net, transition, marking)))
        )
        production = (
            production
            if production is not None
            else next(iter(cls.get_productions(net, transition, marking, consumption)))
        )
        return super().fire(net, transition, marking, consumption, production, sanity_check)


class GuardedClassicalSemantics(ClassicalSemantics[N, P, T, F], GuardedSemantics[N, P, T, F, P]):
    pass


class GuardedSynchronizingSemantics(SynchronizingSemantics[N, P, T, F, TO], GuardedSemantics[N, P, T, F, TO]):
    pass
