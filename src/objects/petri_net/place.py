import uuid
from collections.abc import Hashable
from typing import Any, Dict


class Place(Hashable):
    def __init__(self, name: Any = None, payload: Dict[str, Any] = None) -> None:
        self._name = name if name is not None else "p_" + str(uuid.uuid4())
        self._payload = payload if payload is not None else {}

    @property
    def name(self) -> Any:
        return self._name

    @property
    def payload(self) -> Dict[str, Any]:
        return self._payload

    def __eq__(self, other) -> bool:
        return isinstance(other, Place) and other.name == self.name and other.payload == self.payload

    def __ne__(self, other) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash(self.name)

    def __repr__(self) -> str:
        return str(self.name)
