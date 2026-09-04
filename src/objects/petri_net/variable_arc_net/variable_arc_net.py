from typing import Generic, TypeVar, cast

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.petri_net import PetriNet
from src.objects.petri_net.place import Place
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc

# pylint: disable=invalid-name, too-many-arguments, too-few-public-methods

T = TypeVar("T", bound=Transition)
P = TypeVar("P", bound=Place)
VA = TypeVar("VA", bound=VariableArc)
F = TypeVar("F", bound=Arc | VariableArc)


class VariableArcNet(Generic[P, T, VA, F], PetriNet[P, T, F]):
    """
    A variable arc net extends a general Petri net with a *variable* arc type.
    The arc can take any number of tokens from its input set.
    This class can be seen as a singular instantiation of Object Centric nets.
    """

    @property
    def variable_arcs(self) -> set[VA]:
        return {cast(VA, arc) for arc in self.arcs if arc.type is ArcType.VARIABLE}
