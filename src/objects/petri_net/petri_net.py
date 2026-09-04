from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.place import Place
from src.objects.petri_net.transition import Transition

T = TypeVar("T", bound=Transition)
P = TypeVar("P", bound=Place)
F = TypeVar("F", bound=Arc)


@dataclass(frozen=True)
class PetriNet(Generic[P, T, F]):
    places: set[P] = field(default_factory=set)
    transitions: set[T] = field(default_factory=set)
    arcs: set[F] = field(default_factory=set)
    payload: dict[str, Any] = field(default_factory=dict)
