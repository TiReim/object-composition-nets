import copy
from typing import Generic, TypeVar, cast

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.utils import PetriNetUtils
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc
from src.objects.petri_net.variable_arc_net.variable_arc_net import VariableArcNet

F = TypeVar("F", bound=Arc | VariableArc)
T = TypeVar("T", bound=Transition)
VN = TypeVar("VN", bound=VariableArcNet)


class VariableArcNetUtils(Generic[VN, F]):
    @staticmethod
    def variability_is_well_formed(net: VN) -> bool:
        return all(PetriNetUtils.has_unique_arc_type(net, t) for t in net.transitions)

    @staticmethod
    def get_regular_arc_weights_of_connected_arcs(net: VN, transition: T) -> set[int]:
        return {
            arc.weight
            for arc in cast(set[F], PetriNetUtils.get_connected_arcs(net, transition))
            if arc.type is not ArcType.VARIABLE
        }

    @classmethod
    def regularize(cls, net: VN) -> VN:
        """
        regularizes all variable arcs that are connected to transitions that have a mixture of regular
        and variable arcs (i.e., the arcs randomly adopt an arc weight of a surrounding regular arc).

        :param net:
        :return:
        """
        regularized: VN = copy.deepcopy(net)
        for transition in net.transitions:
            if len(PetriNetUtils.get_connected_arc_types(net, transition)) > 1:
                weight = cls.get_regular_arc_weights_of_connected_arcs(net, transition).pop()
                for arc in cast(set[F], PetriNetUtils.get_connected_arcs(net, transition)):
                    if arc.type is ArcType.VARIABLE:
                        regularized.arcs.remove(arc)
                        regularized.arcs.add(Arc(source=arc.source, target=arc.target, weight=weight))
        return regularized
