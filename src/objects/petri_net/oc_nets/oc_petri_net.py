from typing import TypeVar

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace
from src.objects.petri_net.token import IdentityToken
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc
from src.objects.petri_net.variable_arc_net.variable_arc_net import VariableArcNet

# pylint: disable=too-few-public-methods

OP = TypeVar("OP", bound=ObjectAwarePlace)
T = TypeVar("T", bound=Transition)
VA = TypeVar("VA", bound=VariableArc)
F = TypeVar("F", bound=Arc | VariableArc)

ObjectCentricMarking = Marking[ObjectAwarePlace]
ObjectCentricIdentityMarking = Marking[IdentityToken[ObjectAwarePlace]]


class ObjectCentricPetriNet(VariableArcNet[OP, T, VA, F]):
    pass
