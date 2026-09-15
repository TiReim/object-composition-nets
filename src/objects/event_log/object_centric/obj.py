import polars as pl

from src.objects.event_log.constants import (
    EVENT_ID_COLUMN,
    EVENT_NAME_COLUMN,
    EVENT_TIME_COLUMN,
    OBJECT_ID_COLUMN,
    OBJECT_ID_TWO_COLUMN,
    OBJECT_TYPE_COLUMN,
    OBJECT_TYPE_TWO_COLUMN,
)


class ObjectCentricEventLog:
    def __init__(
        self,
        event_table: pl.DataFrame,
        event_to_object_table: pl.DataFrame,
        object_to_object_table: pl.DataFrame = None,
    ):
        self._event_table: pl.DataFrame = event_table
        self._event_to_object_table: pl.DataFrame = event_to_object_table
        self._has_object_table: bool = False
        if object_to_object_table is not None:
            self._object_to_object_table = object_to_object_table
            self._has_object_table = True

    @property
    def event_table(self) -> pl.DataFrame:
        return self._event_table

    @property
    def event_to_object_table(self) -> pl.DataFrame:
        return self._event_to_object_table

    @property
    def object_to_object_table(self) -> pl.DataFrame:
        if not self._has_object_table:
            raise KeyError("The Object to Object table is not existing in this Object Centric Event log")
        return self._object_to_object_table

    @staticmethod
    def event_id_column() -> str:
        return EVENT_ID_COLUMN

    @staticmethod
    def event_name_column() -> str:
        return EVENT_NAME_COLUMN

    @staticmethod
    def event_time_column() -> str:
        return EVENT_TIME_COLUMN

    @staticmethod
    def object_id_column() -> str:
        return OBJECT_ID_COLUMN

    @staticmethod
    def object_id_two_column() -> str:
        return OBJECT_ID_TWO_COLUMN

    @staticmethod
    def object_type_column() -> str:
        return OBJECT_TYPE_COLUMN

    @staticmethod
    def object_type_two_column() -> str:
        return OBJECT_TYPE_TWO_COLUMN
