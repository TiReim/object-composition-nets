from collections import Counter
from typing import Generic, TypeVar

from src.objects.petri_net.token import Token

T = TypeVar("T", bound=Token)


class Marking(Generic[T], Counter[T]):
    _cached_hash: int | None = None

    @classmethod
    def fromkeys(cls, iterable, v=None) -> None:
        # copied from base class as pylint required to override this
        raise NotImplementedError("Counter.fromkeys() is undefined.  Use Counter(iterable) instead.")

    def __add__(self, other):
        return Marking(super().__add__(other))

    def __sub__(self, other):
        return Marking(super().__sub__(other))

    def __or__(self, other):
        return Marking(super().__or__(other))

    def __and__(self, other):
        return Marking(super().__and__(other))

    def __pos__(self):
        return Marking(super().__pos__())

    def __neg__(self):
        return Marking(super().__neg__())

    def __hash__(self) -> int:  # type: ignore
        current_hash = hash(frozenset((k, v) for k, v in self.items() if v > 0))
        if self._cached_hash is None:
            self._cached_hash = current_hash
        elif self._cached_hash != current_hash:
            raise RuntimeError("Marking has been modified after hash computation!")
        return self._cached_hash
