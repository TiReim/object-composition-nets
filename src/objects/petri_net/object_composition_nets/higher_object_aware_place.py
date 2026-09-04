from src.objects.data_types.higher_order_object_types import HigherOrderObjectType
from src.objects.data_types.object_reference import ObjectType
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace


class HigherObjectAwarePlace(ObjectAwarePlace):
    @property
    def object_type(self) -> ObjectType:
        return str(self.payload[ObjectAwarePlace.OBJECT_TYPE_PAYLOAD_KEY])

    @property
    def higher_order_object_type(self) -> HigherOrderObjectType:
        return self.payload[ObjectAwarePlace.OBJECT_TYPE_PAYLOAD_KEY]
