import abc
from typing import Counter, Generic, TypeVar

from src.objects.petri_net.marking import Marking
from src.objects.petri_net.token import Token

T = TypeVar("T", bound=Token)


class TransitionGuard(abc.ABC, Generic[T]):
    @abc.abstractmethod
    def evaluate(self, marking: Marking[T], consumption: Counter[T]) -> bool:
        pass

    @abc.abstractmethod
    def __repr__(self) -> str:
        pass
