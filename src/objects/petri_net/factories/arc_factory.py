from typing import Any, Generic, TypeVar

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.place import Place
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc

P = TypeVar("P", bound=Place)
T = TypeVar("T", bound=Transition)
A = TypeVar("A", bound=Arc)


# pylint: disable = too-few-public-methods


class ArcFactory(Generic[P, T, A]):
    @staticmethod
    def create_arc(
        arc_type: ArcType, source: P | T, target: P | T, weight: int = None, payload: dict[str, Any] = None
    ) -> Arc | VariableArc:
        match arc_type:
            case ArcType.NORMAL:
                return Arc(source, target, weight, payload)
            case ArcType.VARIABLE:
                return VariableArc(source, target, payload)
