from collections import defaultdict
from typing import NamedTuple, Optional

# pylint: disable=too-few-public-methods
Identity = Optional[str]
ObjectID = Identity
ObjectType = str


class ObjectReference(NamedTuple):
    otype: ObjectType
    oid: ObjectID


ObjectReferenceDict = dict[ObjectType, set[ObjectID]]


class ObjectReferenceUtils:
    @staticmethod
    def dictify_set(object_references: set[ObjectReference]) -> ObjectReferenceDict:
        result = defaultdict(set)
        for object_type, object_id in object_references:
            result[object_type].add(object_id)
        return result

    @staticmethod
    def setify_dict(object_reference_dict: ObjectReferenceDict) -> set[ObjectReference]:
        return {ObjectReference(o_type, o_id) for o_type, o_ids in object_reference_dict.items() for o_id in o_ids}
