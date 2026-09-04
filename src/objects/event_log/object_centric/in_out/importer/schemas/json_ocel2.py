from datetime import datetime

import msgspec

#  pylint: disable=too-few-public-methods


class EventType(msgspec.Struct):
    name: str


class ObjectType(msgspec.Struct):
    name: str


class ObjectRelationship(msgspec.Struct):
    objectId: str


class OCEL2Event(msgspec.Struct):
    id: str
    type: str
    time: datetime
    relationships: list[ObjectRelationship]


class OCEL2Object(msgspec.Struct):
    id: str
    type: str
    relationships: list[ObjectRelationship] = []


class OCEL2JSONModel(msgspec.Struct):
    eventTypes: list[EventType]
    objectTypes: list[ObjectType]
    events: list[OCEL2Event]
    objects: list[OCEL2Object]
