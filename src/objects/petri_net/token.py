from dataclasses import dataclass
from typing import Generic, TypeVar

from src.objects.data_types.object_reference import Identity
from src.objects.petri_net.place import Place

P = TypeVar("P", bound=Place)


@dataclass
class IdentityToken(Generic[P]):
    place: P
    identity: Identity

    def __hash__(self) -> int:
        return 37 * self.place.__hash__() + 79 * self.identity.__hash__()

    def __iter__(self):
        return iter((self.place, self.identity))


Token = Place | IdentityToken
