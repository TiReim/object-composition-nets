from dataclasses import dataclass
from enum import Enum
from typing import Counter, Iterable, Optional, TypeVar

from src.objects.petri_net.marking import Marking
from src.objects.petri_net.token import Token
from src.objects.petri_net.transition_guard import TransitionGuard

T = TypeVar("T", bound=Token)


class CompositeOperator(Enum):
    ALL = "all"


operator_lookup = {
    CompositeOperator.ALL: all,
}


@dataclass
class CompositeTransitionGuard(TransitionGuard[T]):
    guards: Iterable[Optional[TransitionGuard]]
    operator: CompositeOperator

    def evaluate(self, marking: Marking[T], consumption: Counter[T]) -> bool:
        return operator_lookup[self.operator](
            [guard.evaluate(marking, consumption) if guard is not None else True for guard in self.guards]
        )

    def __repr__(self) -> str:
        return f"{self.operator.value}({self.guards})"
