from typing import Generic, TypeVar

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.petri_net import PetriNet
from src.objects.petri_net.place import Place
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.utils import PetriNetUtils

N = TypeVar("N", bound=PetriNet)
T = TypeVar("T", bound=Transition)
P = TypeVar("P", bound=Place)
F = TypeVar("F", bound=Arc)


class GeneralizedWorkflowNet(Generic[N, P, T, F], PetriNet[P, T, F]):
    def __init__(self, net: N, source_places: set[P], sink_places: set[P]) -> None:
        super().__init__(net.places, net.transitions, net.arcs, net.payload)
        self._net = net
        if any(PetriNetUtils.get_pre_set_arcs(net, source_place) for source_place in source_places):
            raise ValueError(f"invalid: {source_places=} for workflow net as the source place has incoming arcs")
        if any(PetriNetUtils.get_post_set_arcs(net, sink_place) for sink_place in sink_places):
            raise ValueError(f"invalid: {sink_places=} for workflow net as the sink place has outgoing arcs")
        self._source_places = source_places
        self._sink_places = sink_places

    @property
    def net(self) -> N:
        return self._net

    @property
    def source_places(self) -> set[P]:
        return self._source_places

    @property
    def sink_places(self) -> set[P]:
        return self._sink_places


class WorkflowNet(GeneralizedWorkflowNet[N, P, T, F]):
    def __init__(self, net: N, source_place: P, sink_place: P) -> None:
        super().__init__(net, {source_place}, {sink_place})

    @property
    def source_place(self) -> P:
        return next(iter(self._source_places))

    @property
    def sink_place(self) -> P:
        return next(iter(self._sink_places))
