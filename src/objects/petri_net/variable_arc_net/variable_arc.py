from typing import Any, Dict, TypeVar

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.place import Place
from src.objects.petri_net.transition import Transition

T = TypeVar("T", bound=Transition)
P = TypeVar("P", bound=Place)


class VariableArc(Arc[P, T]):
    def __init__(self, source: P | T, target: P | T, payload: Dict[str, Any] = None) -> None:
        super().__init__(source, target, 1, payload)

    @property
    def type(self) -> ArcType:
        return ArcType.VARIABLE
