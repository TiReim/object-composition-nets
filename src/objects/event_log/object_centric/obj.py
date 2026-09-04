from typing import Collection, Set

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


class ObjectCentricEventLog:  # pylint: disable=too-many-public-methods
    EVENT_TABLE_COLUMNS = [EVENT_ID_COLUMN, EVENT_NAME_COLUMN, EVENT_TIME_COLUMN]
    EVENT_TO_OBJECT_TABLE_COLUMNS = [EVENT_ID_COLUMN, OBJECT_TYPE_COLUMN, OBJECT_ID_COLUMN]
    OBJECT_TO_OBJECT_TABLE_COLUMNS = [
        OBJECT_ID_COLUMN,
        OBJECT_TYPE_COLUMN,
        OBJECT_ID_TWO_COLUMN,
        OBJECT_TYPE_TWO_COLUMN,
    ]

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

    @classmethod
    def create_from_flattened_table(cls, table: pl.DataFrame) -> "ObjectCentricEventLog":
        for col in cls.EVENT_TABLE_COLUMNS + cls.EVENT_TO_OBJECT_TABLE_COLUMNS:
            if col not in table.columns:
                raise KeyError(f"Missing column {col} in Event Table")

        event_table = table.select(cls.EVENT_TABLE_COLUMNS).unique(subset=[EVENT_ID_COLUMN], maintain_order=True)
        event_to_object_table = table.drop(
            [column for column in table.columns if column not in cls.EVENT_TO_OBJECT_TABLE_COLUMNS]
        )
        return cls(event_table=event_table, event_to_object_table=event_to_object_table)

    @classmethod
    def create_from_event_and_object_to_event_table(
        cls, event_table: pl.DataFrame, event_to_object_table: pl.DataFrame
    ) -> "ObjectCentricEventLog":
        for col in cls.EVENT_TABLE_COLUMNS:
            if col not in event_table.columns:
                raise KeyError(f"Missing column {col} in Event Table")

        for col in cls.EVENT_TO_OBJECT_TABLE_COLUMNS:
            if col not in event_to_object_table:
                raise KeyError(f"Missing column {col} in Event to Object Table")

        return cls(event_table=event_table, event_to_object_table=event_to_object_table)

    @classmethod
    def create_from_event_and_event_to_object_and_object_to_object_table(
        cls, event_table: pl.DataFrame, event_to_object_table: pl.DataFrame, object_to_object_table: pl.DataFrame
    ) -> "ObjectCentricEventLog":
        for col in cls.EVENT_TABLE_COLUMNS:
            if col not in event_table.columns:
                raise KeyError(f"Missing column {col} in Event Table")

        for col in cls.EVENT_TO_OBJECT_TABLE_COLUMNS:
            if col not in event_to_object_table:
                raise KeyError(f"Missing column {col} in Event to Object Table")

        for col in cls.OBJECT_TO_OBJECT_TABLE_COLUMNS:
            if col not in object_to_object_table:
                raise KeyError(f"Missing column {col} in Object to Object Table")

        return cls(
            event_table=event_table,
            event_to_object_table=event_to_object_table,
            object_to_object_table=object_to_object_table,
        )

    def _get_objects_associated_to_events(self, object_type: str) -> pl.DataFrame:
        """
        Given object type it returns event ids with list of associated object ids of object type
        Note that this function will only return events that contain objects of object type
        """
        if object_type not in self.object_types_set:
            raise KeyError(f"Missing object type {object_type} in event to object table.")

        events_with_objects = (
            self.event_to_object_table.filter(pl.col(OBJECT_TYPE_COLUMN) == object_type)
            .groupby(EVENT_ID_COLUMN)
            .agg(pl.col(OBJECT_ID_COLUMN))
        )
        events_with_objects = events_with_objects.rename({OBJECT_ID_COLUMN: object_type})
        return events_with_objects

    def event_table_from_all_objects_perspective(self, filter_empty_rows: bool = True) -> pl.DataFrame:
        """
        Returns event table from perspective of all available objects in OCEL
        """
        return self.event_table_from_objects_perspective(self.object_types_set, filter_empty_rows)

    def event_table_from_objects_perspective(
        self, object_types: Collection[str], filter_empty_rows: bool = True
    ) -> pl.DataFrame:
        """
        Converts the event table to cover object information of form:
        Event_id | Activity | Timestamp | Object_type 1 | Object_type 2 ...
        "e1"     | "a1"     | t1        | []            | ["o2_1", "o2_2"]
        Where each object_type col covers all object ids within that event (list of objects)
        If there is no object related to event we obtain an empty list

        :param object_types: A collection of object types which will be used to get the perspective
        :type object_types: Collection[str]
        :param filter_empty_rows: Whether to filter events that don't contain any objects of types any in object_types
        :type filter_empty_rows: bool
        """
        event_log = self.event_table.clone()
        for object_type in object_types:
            events_with_objects = self._get_objects_associated_to_events(object_type)
            event_log = event_log.join(events_with_objects, on=EVENT_ID_COLUMN, how="left")

        if filter_empty_rows:
            # filter out rows which have no objects for all columns in object types
            event_log = event_log.filter(~pl.fold(True, lambda acc, val: acc & val.is_null(), object_types))

        # fill null values with empty list
        event_log = event_log.with_columns([pl.col(col).fill_null([]) for col in object_types])

        return event_log

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

    @property
    def event_ids(self) -> pl.Series:
        return self._event_table[EVENT_ID_COLUMN]

    @property
    def object_ids_from_event_to_object(self) -> pl.DataFrame:
        return self.event_to_object_table.select([self.object_id_column(), self.object_type_column()]).unique()

    @property
    def object_ids_from_object_to_object(self) -> pl.DataFrame:
        if not self._has_object_table or self.object_to_object_table.is_empty():
            return pl.DataFrame(schema=[(self.object_id_column(), pl.Utf8()), (self.object_type_column(), pl.Utf8())])
        return pl.concat(
            [
                self.object_to_object_table.select([self.object_id_column(), self.object_type_column()]),
                self.object_to_object_table.with_columns(
                    [
                        pl.col(self.object_id_two_column()).alias(self.object_id_column()),
                        pl.col(self.object_type_two_column()).alias(self.object_type_column()),
                    ]
                ).select([self.object_id_column(), self.object_type_column()]),
            ]
        ).unique()

    @property
    def object_ids_intersection(self) -> pl.DataFrame:
        return self.object_ids_from_event_to_object.join(
            self.object_ids_from_object_to_object, on=[self.object_id_column(), self.object_type_column()], how="inner"
        ).unique()

    @property
    def object_ids_all(self) -> pl.DataFrame:
        return pl.concat([self.object_ids_from_event_to_object, self.object_ids_from_object_to_object]).unique()

    @property
    def object_types_set(self) -> Set[str]:
        return set(self.event_to_object_table[OBJECT_TYPE_COLUMN])

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
