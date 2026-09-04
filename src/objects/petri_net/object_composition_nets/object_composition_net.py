from typing import TypeVar

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.object_composition_nets.higher_object_aware_place import HigherObjectAwarePlace
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.oc_nets.oc_petri_net import ObjectCentricPetriNet
from src.objects.petri_net.oc_nets.oc_workflow_net import ObjectCentricWorkflowNet
from src.objects.petri_net.token import IdentityToken
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc

# pylint: disable=too-few-public-methods

OP = TypeVar("OP", bound=HigherObjectAwarePlace)
T = TypeVar("T", bound=Transition)
VA = TypeVar("VA", bound=VariableArc)
F = TypeVar("F", bound=Arc | VariableArc)

ObjectCompositionMarking = Marking[HigherObjectAwarePlace]
ObjectCompositionIdentityMarking = Marking[IdentityToken[HigherObjectAwarePlace]]


class ObjectCompositionNet(ObjectCentricPetriNet[OP, T, VA, F]):
    pass


CN = TypeVar("CN", bound=ObjectCompositionNet)


class ObjectCompositionWorkflowNet(ObjectCentricWorkflowNet[CN, OP, T, F]):
    pass
