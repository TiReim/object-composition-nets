import abc
import pathlib
from io import BytesIO
from typing import BinaryIO

from src.objects.event_log.object_centric.obj import ObjectCentricEventLog


class AbstractOCELImporter(abc.ABC):
    @property
    @abc.abstractmethod
    def allowed_suffixes(self) -> list[str]:
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def import_from_file(cls, file: BytesIO | BinaryIO) -> ObjectCentricEventLog:
        raise NotImplementedError()

    @classmethod
    def import_from_path(cls, file_name: str) -> ObjectCentricEventLog:
        path = pathlib.Path(file_name)
        if path.suffix not in cls.allowed_suffixes:  # type: ignore
            raise SystemError(
                f"The provided file_path '{path.suffix}', "
                f"does not correspond to any of these allowed file types: f{cls.allowed_suffixes}"
            )
        with open(file_name, "rb") as file:
            return cls.import_from_file(file)
