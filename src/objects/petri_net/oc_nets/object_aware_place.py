from typing import Any, Hashable

from src.objects.data_types.object_reference import ObjectType
from src.objects.petri_net.place import Place


class ObjectAwarePlace(Place):
    OBJECT_TYPE_PAYLOAD_KEY = "object_type"

    def __init__(self, name: Any = None, object_type: Hashable = None, payload: dict[str, Any] = None) -> None:
        payload = {} if payload is None else payload
        payload[ObjectAwarePlace.OBJECT_TYPE_PAYLOAD_KEY] = object_type
        super().__init__(name, payload)

    @property
    def object_type(self) -> ObjectType:
        return self.payload[ObjectAwarePlace.OBJECT_TYPE_PAYLOAD_KEY]

    def __eq__(self, other) -> bool:
        return isinstance(other, ObjectAwarePlace) and super().__eq__(other) and other.object_type == self.object_type

    def __hash__(self) -> int:
        return hash(self.name) + 31 * hash(self.object_type)

    def __repr__(self) -> str:
        return f"{self.name}({self.object_type})"
