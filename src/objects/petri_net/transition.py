import uuid
from typing import Any, Hashable, Optional, TypeVar

from src.objects.petri_net.place import Place
from src.objects.petri_net.token import Token
from src.objects.petri_net.transition_guard import TransitionGuard

# pylint: disable=too-many-arguments

P = TypeVar("P", bound=Place)
T = TypeVar("T", bound=Token)


class Transition:
    def __init__(
        self, name: Hashable = None, label: Any = None, guard: TransitionGuard = None, payload: dict[str, Any] = None
    ) -> None:
        self._name = name if name is not None else "t_" + str(uuid.uuid4())
        self._label = label
        self._guard = guard
        self._payload = payload if payload is not None else {}

    @property
    def name(self) -> Hashable:
        return self._name

    @property
    def label(self) -> Any:
        return self._label

    @property
    def payload(self) -> dict[str, Any]:
        return self._payload

    @property
    def guard(self) -> Optional[TransitionGuard]:
        return self._guard

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Transition)
            and other.name == self.name
            and other.label == self.label
            and other.payload == self.payload
            and ((other.guard is None and self.guard is None) or other.guard == self.guard)
        )

    def __ne__(self, other) -> bool:
        return not self == other

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return str(self.name) + " (" + (str(self.label) if self.label is not None else "_") + ")"
