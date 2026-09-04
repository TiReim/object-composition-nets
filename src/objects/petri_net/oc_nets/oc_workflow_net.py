from typing import TypeVar

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace
from src.objects.petri_net.oc_nets.oc_petri_net import ObjectCentricPetriNet
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc
from src.objects.petri_net.workflow_net import GeneralizedWorkflowNet

OP = TypeVar("OP", bound=ObjectAwarePlace)
T = TypeVar("T", bound=Transition)
F = TypeVar("F", bound=Arc | VariableArc)
OCN = TypeVar("OCN", bound=ObjectCentricPetriNet)


class ObjectCentricWorkflowNet(GeneralizedWorkflowNet[OCN, OP, T, F]):
    def __init__(self, net: OCN, source_places: set[OP], sink_places: set[OP]) -> None:
        super().__init__(net, source_places, sink_places)
        self._source_place_dict = {place.object_type: place for place in source_places}
        self._sink_place_dict = {place.object_type: place for place in sink_places}

    def get_source_of_object_type(self, object_type: str) -> OP:
        return self._source_place_dict[object_type] if object_type in self._source_place_dict else None

    def get_sink_of_object_type(self, object_type: str) -> OP:
        return self._sink_place_dict[object_type] if object_type in self._sink_place_dict else None
