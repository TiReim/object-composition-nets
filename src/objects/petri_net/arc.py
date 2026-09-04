from typing import Any, Dict, Generic, TypeVar

from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.place import Place
from src.objects.petri_net.transition import Transition

T = TypeVar("T", bound=Transition)
P = TypeVar("P", bound=Place)


class Arc(Generic[P, T]):
    def __init__(self, source: P | T, target: P | T, weight: int = 1, payload: Dict[str, Any] = None) -> None:
        if (isinstance(source, Place) and isinstance(target, Place)) or (
            isinstance(source, Transition) and isinstance(target, Transition)
        ):
            raise ValueError("The source and target of a Petri net arc must be of a different type")
        self._source = source
        self._target = target
        self._weight = weight
        self._payload = payload if payload is not None else {}

    @property
    def source(self) -> P | T:
        return self._source

    @property
    def target(self) -> P | T:
        return self._target

    @property
    def weight(self) -> int:
        return self._weight

    @property
    def payload(self) -> Dict[str, Any]:
        return self._payload

    @property
    def type(self) -> ArcType:
        return ArcType.NORMAL

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Arc)
            and other.source == self.source
            and other.target == self.target
            and other.weight == self.weight
            and other.payload == self.payload
            and other.type is self.type
        )

    def __ne__(self, other) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return 31 * hash(self.source) + 79 * hash(self.target) + 47 * self.weight

    def __repr__(self):
        return str(self.source.name) + " -> " + str(self.target.name) + "(" + str(self.weight) + ")"
