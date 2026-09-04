from dataclasses import dataclass
from typing import TypeVar

from src.objects.data_types.higher_order_object_types import HigherOrderObject
from src.objects.petri_net.object_composition_nets.higher_object_aware_place import HigherObjectAwarePlace
from src.objects.petri_net.token import IdentityToken

P = TypeVar("P", bound=HigherObjectAwarePlace)


@dataclass
class ObjectCompositionIdentityToken(IdentityToken[P]):
    higher_order_object: HigherOrderObject

    def __init__(self, place: P, identity: HigherOrderObject):
        self.higher_order_object = identity
        super().__init__(place, str(identity))

    def __hash__(self) -> int:
        return 37 * self.place.__hash__() + 79 * self.identity.__hash__()
