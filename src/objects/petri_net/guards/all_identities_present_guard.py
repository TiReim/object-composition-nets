from collections import Counter
from dataclasses import dataclass
from typing import Generic, Hashable, TypeVar

from src.objects.data_types.object_reference import ObjectReferenceDict
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.token import IdentityToken
from src.objects.petri_net.transition_guard import TransitionGuard

# pylint: disable=unnecessary-dict-index-lookup

H = TypeVar("H", bound=Hashable)  # needs to be TypeVar since set[Hashable] is invariant


@dataclass
class AllIdentitiesPresentGuard(Generic[H], TransitionGuard[IdentityToken]):
    """
    This guard only allows for an exact set of objects in the consumption.
    """

    allowed_objects: ObjectReferenceDict

    def evaluate(self, marking: Marking[IdentityToken], consumption: Counter[IdentityToken]) -> bool:
        all_consumed_ids = {
            obj_id for place, obj_id in consumption.keys() if consumption[IdentityToken(place, obj_id)] > 0
        }
        allowed_ids = set().union(*list(self.allowed_objects.values()))
        if all_consumed_ids != allowed_ids:
            return False
        for object_type, _ in self.allowed_objects.items():
            all_places_of_type = {
                place
                for place, obj_id in consumption.keys()
                if consumption[IdentityToken(place, obj_id)] > 0 and place.object_type == object_type
            }
            places_with_required_objects = {
                place
                for place, obj_id in consumption.keys()
                if consumption[IdentityToken(place, obj_id)] > 0 and obj_id in self.allowed_objects[object_type]
            }
            if all_places_of_type != places_with_required_objects:
                return False
        return True

    def __repr__(self) -> str:
        return str(self.allowed_objects)
