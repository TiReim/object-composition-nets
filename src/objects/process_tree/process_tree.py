from typing import List

from PrettyPrint import PrettyPrintTree  # type: ignore
from typing_extensions import Self

from src.objects.petri_net.arc import Arc
from src.objects.petri_net.petri_net import PetriNet
from src.objects.petri_net.place import Place
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.workflow_net import WorkflowNet
from src.objects.process_tree.operator import Operator

SILENT_TRANSITION_LABEL = "\u03C4"


class ProcessTree:
    def __init__(self, operator: Operator = None, label: str = None, parent: Self = None):
        self._operator = operator
        self._label = label
        self._parent = parent
        self._children: List[Self] = []

    @property
    def parent(self) -> Self:
        return self._parent

    @parent.setter
    def parent(self, parent: Self):
        self._parent = parent

    @property
    def children(self) -> List[Self]:
        return self._children

    @property
    def operator(self) -> Operator:
        return self._operator

    @property
    def label(self) -> str:
        return self._label

    def print_tree(self):  # pragma: no cover
        printer = PrettyPrintTree(
            lambda tree: tree.children, lambda tree: tree.operator.value if tree.operator is not None else tree.label
        )
        printer(self)

    def to_petri_net(self) -> WorkflowNet:
        net: PetriNet = PetriNet()
        initial_place = Place()
        final_place = Place()
        net.places.add(initial_place)
        net.places.add(final_place)
        net, _, _ = self.convert_tree_to_net(net, initial_place, final_place)
        return WorkflowNet(net, initial_place, final_place)

    def convert_tree_to_net(
        self, net: PetriNet, initial_node: Place | Transition, final_node: Place | Transition
    ) -> tuple[PetriNet, Place, Place]:
        if isinstance(initial_node, Transition):
            initial_place = Place()
            net.places.add(initial_place)
            net.arcs.add(Arc(initial_node, initial_place))
        else:
            initial_place = initial_node
        if isinstance(final_node, Transition):
            final_place = Place()
            net.places.add(final_place)
            net.arcs.add(Arc(final_place, final_node))
        else:
            final_place = final_node
        if len(self.children) == 0:
            transition = Transition(
                name=self.label if self.label != SILENT_TRANSITION_LABEL else None, label=self.label
            )
            net.transitions.add(transition)
            net.arcs.update({Arc(initial_place, transition), Arc(transition, final_place)})
        elif self.operator == Operator.SEQUENCE:
            net = self._convert_sequence_cut(net, initial_place, final_place)
        elif self.operator == Operator.XOR:
            net = self._convert_xor_cut(net, initial_place, final_place)
        elif self.operator == Operator.PARALLEL:
            net = self._convert_parallel_cut(net, initial_place, final_place)
        elif self.operator == Operator.LOOP:
            net = self._convert_loop_cut(net, initial_place, final_place)

        return net, initial_place, final_place

    def _convert_sequence_cut(self, net: PetriNet, initial_place: Place, final_place: Place) -> PetriNet:
        end_place = initial_place
        for i, child in enumerate(self.children):
            start_place = end_place
            if i == len(self.children) - 1:
                end_place = final_place
            else:
                end_place = Place()
                net.places.add(end_place)
            net, _, start_place = child.convert_tree_to_net(net, start_place, end_place)
        return net

    def _convert_xor_cut(self, net: PetriNet, initial_place: Place, final_place: Place) -> PetriNet:
        for child in self.children:
            net, _, _ = child.convert_tree_to_net(net, initial_place, final_place)
        return net

    def _convert_parallel_cut(self, net: PetriNet, initial_place: Place, final_place: Place) -> PetriNet:
        initial_silent = Transition(label=SILENT_TRANSITION_LABEL)
        final_silent = Transition(label=SILENT_TRANSITION_LABEL)
        net.transitions.update({initial_silent, final_silent})
        net.arcs.update({Arc(initial_place, initial_silent), Arc(final_silent, final_place)})
        for child in self.children:
            net, _, _ = child.convert_tree_to_net(net, initial_silent, final_silent)
        return net

    def _convert_loop_cut(self, net: PetriNet, initial_place: Place, final_place: Place) -> PetriNet:
        initial_silent = Transition(label=SILENT_TRANSITION_LABEL)
        final_silent = Transition(label=SILENT_TRANSITION_LABEL)
        loop_start = Place()
        loop_end = Place()
        net.transitions.update({initial_silent, final_silent})
        net.places.update({loop_start, loop_end})
        net.arcs.update(
            {
                Arc(initial_place, initial_silent),
                Arc(initial_silent, loop_start),
                Arc(loop_end, final_silent),
                Arc(final_silent, final_place),
            }
        )
        for i, child in enumerate(self.children):
            if i == 0:
                net, _, _ = child.convert_tree_to_net(net, loop_start, loop_end)
            else:
                net, _, _ = child.convert_tree_to_net(net, loop_end, loop_start)
        return net

    def __repr__(self):
        if self.operator:
            return f"{self.operator.value}({','.join(str(child) for child in self.children)})"
        return f"'{self.label}'"
