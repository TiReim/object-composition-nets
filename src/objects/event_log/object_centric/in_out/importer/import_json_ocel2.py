from io import BytesIO
from typing import BinaryIO

import msgspec
import polars as pl
from overrides import overrides

from src.objects.event_log.object_centric.in_out.importer.ocel_importer import AbstractOCELImporter
from src.objects.event_log.object_centric.in_out.importer.schemas.json_ocel2 import OCEL2JSONModel
from src.objects.event_log.object_centric.obj import ObjectCentricEventLog


class OCEL2JSONImporter(AbstractOCELImporter):
    allowed_suffixes = [".json", ".jsonocel"]

    @classmethod
    @overrides
    def import_from_file(cls, file: BytesIO | BinaryIO) -> ObjectCentricEventLog:
        data = msgspec.json.decode(file.read(), type=OCEL2JSONModel)

        event_table = pl.DataFrame(
            [(event.id, event.type, event.time) for event in data.events],
            schema=[
                ObjectCentricEventLog.event_id_column(),
                ObjectCentricEventLog.event_name_column(),
                ObjectCentricEventLog.event_time_column(),
            ],
            orient="row",
        ).sort(ObjectCentricEventLog.event_time_column())

        object_id_to_type_mapping = {obj.id: obj.type for obj in data.objects}

        event_to_object_table = pl.DataFrame(
            [
                (event.id, obj.objectId, object_id_to_type_mapping[obj.objectId])
                for event in data.events
                for obj in event.relationships
                if obj.objectId in object_id_to_type_mapping
            ],
            schema=[
                ObjectCentricEventLog.event_id_column(),
                ObjectCentricEventLog.object_id_column(),
                ObjectCentricEventLog.object_type_column(),
            ],
            orient="row",
        )
        object_to_object_table = pl.DataFrame(
            [
                (obj.id, obj.type, obj2.objectId, object_id_to_type_mapping[obj2.objectId])
                for obj in data.objects
                for obj2 in obj.relationships
                if obj2.objectId in object_id_to_type_mapping
            ],
            schema=[
                ObjectCentricEventLog.object_id_column(),
                ObjectCentricEventLog.object_type_column(),
                ObjectCentricEventLog.object_id_two_column(),
                ObjectCentricEventLog.object_type_two_column(),
            ],
            orient="row",
        )
        if object_to_object_table.is_empty():
            return ObjectCentricEventLog(event_table, event_to_object_table)

        return ObjectCentricEventLog(event_table, event_to_object_table, object_to_object_table)
