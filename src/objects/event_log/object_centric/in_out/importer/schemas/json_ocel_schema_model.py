"""
Schema created using Data Model Code Generator for Pydantic Version 2.0
https://docs.pydantic.dev/latest/integrations/datamodel_code_generator/
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Union

from pydantic import BaseModel, Field


class OcelEvents(BaseModel):
    pass


class OcelObjects(BaseModel):
    pass


class ObjectMappingType(BaseModel):
    pass


class ValueMappingType(BaseModel):
    pass


class OcelVmap(BaseModel):
    pass


class EventType(BaseModel):
    ocel_eid: str = Field(..., alias="ocel:id")
    ocel_activity: str = Field(..., alias="ocel:activity")
    ocel_timestamp: datetime = Field(..., alias="ocel:timestamp")
    ocel_vmap: Union[List[ValueMappingType], OcelVmap] = Field(..., alias="ocel:vmap")
    ocel_omap: List[str] = Field(..., alias="ocel:omap")


class OcelOvmap(BaseModel):
    pass


class ObjectType(BaseModel):
    ocel_oid: str = Field(..., alias="ocel:id")
    ocel_type: str = Field(..., alias="ocel:type")
    ocel_ovmap: Union[List[ValueMappingType], OcelOvmap] = Field(..., alias="ocel:ovmap")


class OCELJSONModel(BaseModel):
    class Config:
        extra = "allow"

    ocel_events: Union[List[EventType], OcelEvents] = Field(None, alias="ocel:events")
    ocel_objects: Union[List[ObjectMappingType], OcelObjects] = Field(None, alias="ocel:objects")
