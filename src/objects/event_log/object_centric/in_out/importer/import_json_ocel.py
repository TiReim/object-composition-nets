import json
from io import BytesIO
from typing import Any, BinaryIO, List, Tuple

import polars as pl
from overrides import overrides
from polars import DataFrame
from pydantic_core import ValidationError

from src.objects.event_log.object_centric.in_out.importer.ocel_importer import AbstractOCELImporter
from src.objects.event_log.object_centric.in_out.importer.schemas.json_ocel_schema_model import (
    EventType,
    ObjectType,
    OCELJSONModel,
)
from src.objects.event_log.object_centric.obj import ObjectCentricEventLog


class OCELJSONImporter(AbstractOCELImporter):

    allowed_suffixes = [".json", ".jsonocel"]

    @classmethod
    @overrides
    def import_from_file(cls, file: BytesIO | BinaryIO) -> ObjectCentricEventLog:
        json_data = json.load(file)
        object_model = OCELJSONModel.model_validate(json_data)
        if len(object_model.ocel_events.model_dump()) == 0 or len(object_model.ocel_objects.model_dump()) == 0:
            object_model.ocel_events, object_model.ocel_objects = cls._load_data_with_schema_violation_correction(
                json_data
            )
        events, objects = object_model.ocel_events, object_model.ocel_objects
        return cls._create_object_centric_event_log_from_base_models(events, objects)

    @classmethod
    def _load_data_with_schema_violation_correction(cls, json_dict) -> Tuple[List[EventType], List[ObjectType]]:
        def _validate_entries(entries, model: Any) -> List[Any]:

            validated_entries = []
            for oid, val in entries.items():
                try:
                    obj = model.model_validate(val)

                except ValidationError:
                    val |= {
                        "ocel:id": oid
                    }  # Patch the common schema violation of using EID/OID as Key instead of properties
                    obj = model.model_validate(val)

                validated_entries.append(obj)

            return validated_entries

        return _validate_entries(json_dict["ocel:events"], EventType), _validate_entries(
            json_dict["ocel:objects"], ObjectType
        )

    @classmethod
    def _create_object_centric_event_log_from_base_models(
        cls, events: List[EventType], objects: List[ObjectType]
    ) -> ObjectCentricEventLog:
        event_to_object_rows = []
        event_rows = []

        object_mapping = {obj.ocel_oid: obj for obj in objects}

        for event in events:
            for oid in event.ocel_omap:
                event_to_object_rows.append({"ocel_eid": event.ocel_eid, **object_mapping[oid].model_dump()})

            event_rows.append({key: data for key, data in event.model_dump().items() if key != "omap"})

        event_table: DataFrame = pl.from_dicts(event_rows)

        event_table = event_table.rename(
            {
                "ocel_eid": ObjectCentricEventLog.event_id_column(),
                "ocel_activity": ObjectCentricEventLog.event_name_column(),
                "ocel_timestamp": ObjectCentricEventLog.event_time_column(),
            }
        ).sort(ObjectCentricEventLog.event_time_column())

        event_to_object_table: DataFrame = DataFrame(event_to_object_rows)

        event_to_object_table = event_to_object_table.rename(
            {
                "ocel_eid": ObjectCentricEventLog.event_id_column(),
                "ocel_oid": ObjectCentricEventLog.object_id_column(),
                "ocel_type": ObjectCentricEventLog.object_type_column(),
            }
        )
        return ObjectCentricEventLog(event_table, event_to_object_table)
