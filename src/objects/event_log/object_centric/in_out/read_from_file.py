import os
from io import BytesIO
from typing import BinaryIO, Optional, cast

from src.objects.event_log.object_centric.in_out.importer.import_json_ocel import OCELJSONImporter
from src.objects.event_log.object_centric.in_out.importer.import_json_ocel2 import OCEL2JSONImporter
from src.objects.event_log.object_centric.obj import ObjectCentricEventLog

IOFile = BytesIO | BinaryIO


def read_from_file_path(file_name: str) -> Optional[ObjectCentricEventLog]:
    _, filetype = os.path.splitext(file_name)

    if not isinstance(file_name, str):
        raise SystemError("The passed file parameter does not correspond to a path string")

    if not filetype:
        raise SystemError(f"The passed path {file_name} does not lead to a file")

    match filetype:
        case ".json" | ".jsonocel":
            try:
                return OCELJSONImporter.import_from_path(file_name)
            except AttributeError:
                try:
                    with open(file_name, "r", encoding="UTF-8") as file:
                        return OCEL2JSONImporter.import_from_file(file)
                except Exception as e:
                    raise SystemError(
                        "You have provided a json / jsonocel file that can't be parsed by OCEL 1 and 2 importers"
                    ) from e

        case _:
            raise SystemError(
                f"The filetype {filetype} is not supported for import into an Object-Centric event log",
            )


def read_from_file(file: IOFile, filetype: str):
    match filetype:
        case ".json" | ".jsonocel":
            try:
                return OCELJSONImporter.import_from_file(file)
            except AttributeError:
                try:
                    file.seek(0)
                    return OCEL2JSONImporter.import_from_file(file)
                except Exception as e:
                    raise SystemError(
                        "You have provided a json / jsonocel file that can't be parsed by OCEL 1 and 2 importers"
                    ) from e

        case _:
            raise SystemError(
                f"The filetype {filetype} is not supported for import into an Object-Centric event log",
            )


def read_from_file_or_path(file_or_path: str | IOFile, **kwargs) -> ObjectCentricEventLog:
    if isinstance(file_or_path, str):
        return read_from_file_path(cast(str, file_or_path))

    if "filetype" not in kwargs:
        raise SystemError("When passing a file-like object, the keyword argument 'filetype' is required.")
    return read_from_file(file_or_path, kwargs["filetype"])
