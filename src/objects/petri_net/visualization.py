from typing import Any, Counter, Optional

import pydot

from src.objects.data_types.object_reference import Identity
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace
from src.objects.petri_net.petri_net import PetriNet
from src.objects.petri_net.utils import MarkingUtils
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL
from src.utils.color import get_object_type_color_map, rgb_to_hex

# pylint: disable=too-many-arguments


def _stringify_place_marking(token: int | Counter[Identity]) -> str:
    return str(token if isinstance(token, int) else dict(token))


class PetriNetVisualization:
    def __init__(self, graph: pydot.Dot):
        self.graph = graph

    @staticmethod
    def _construct_places(
        graph: pydot.Dot,
        net: PetriNet,
        show_names: bool,
        current_marking: Marking,
        final_marking: Marking,
        fontname: str,
        color_mapping: Optional[dict[Any, Any]],
    ) -> pydot.Dot:
        object_types = {place.object_type for place in net.places if isinstance(place, ObjectAwarePlace)}
        if object_types and color_mapping is None:
            color_mapping = get_object_type_color_map(object_types)
        for place in net.places:
            if isinstance(color_mapping[place.object_type], str):
                # Assume that the color mapping already contains hex codes
                fill_color = color_mapping[place.object_type]
            else:
                fill_color = (
                    rgb_to_hex(*color_mapping[place.object_type]) if isinstance(place, ObjectAwarePlace) else "white"
                )
            label = (
                _stringify_place_marking(MarkingUtils.get_identities_in_place(current_marking, place))
                if place in MarkingUtils.project_on_places(current_marking)
                else ""
            ) + (
                f"[{_stringify_place_marking(MarkingUtils.get_identities_in_place(final_marking, place))}]"
                if place in MarkingUtils.project_on_places(final_marking)
                else ""
            )
            shape = "doublecircle" if place in MarkingUtils.project_on_places(final_marking) else "circle"
            xlabel = str(place.name) if show_names else ""
            graph.add_node(
                pydot.Node(
                    str(place.name),
                    label=label,
                    shape=shape,
                    fillcolor=fill_color,
                    style="filled",
                    xlabel=xlabel,
                    fontname=fontname,
                    fontsize=11,
                )
            )
        return graph

    @staticmethod
    def _construct_transitions(graph: pydot.Dot, net: PetriNet, fontname: str, show_guards: bool) -> pydot.Dot:
        for transition in net.transitions:
            xlabel = str(transition.guard) if show_guards and transition.guard is not None else ""
            if "scope" in transition.payload:
                xlabel = f"sc={transition.payload['scope']}"
            if transition.label is None or transition.label == SILENT_TRANSITION_LABEL:
                graph.add_node(
                    pydot.Node(
                        str(transition.name),
                        label="",
                        shape="rectangle",
                        style="filled",
                        fillcolor="black",
                        width=0.15,
                        fontname=fontname,
                        fontsize=13,
                        xlabel=xlabel,
                    )
                )
            else:
                graph.add_node(
                    pydot.Node(
                        str(transition.name),
                        label=str(transition.label),
                        shape="rectangle",
                        fontname=fontname,
                        fontsize=13,
                        xlabel=xlabel,
                    )
                )
        return graph

    @staticmethod
    def _construct_arcs(graph: pydot.Dot, net: PetriNet) -> pydot.Dot:
        for arc in net.arcs:
            match arc.type:
                case ArcType.NORMAL:
                    label = "" if arc.weight == 1 else str(arc.weight)
                    graph.add_edge(pydot.Edge(str(arc.source.name), str(arc.target.name), color="black", label=label))
                case ArcType.VARIABLE:
                    graph.add_edge(
                        pydot.Edge(
                            str(arc.source.name),
                            str(arc.target.name),
                            color="black",
                            style="dashed",
                        )
                    )
                case _:
                    raise NotImplementedError(f"Arc type {arc.type} is unsupported")
        return graph

    @classmethod
    def _construct_graph_viz_petri_net(
        cls,
        net: PetriNet,
        show_place_names: bool,
        show_guards: bool,
        current_marking: Marking,
        final_marking: Marking,
        fontname: str,
        color_mapping: Optional[dict[Any, Any]],
    ) -> pydot.Dot:
        graph = pydot.Dot("my_graph", graph_type="digraph", bgcolor="white", rankdir="LR")

        graph = cls._construct_places(
            graph, net, show_place_names, current_marking, final_marking, fontname, color_mapping
        )
        graph = cls._construct_transitions(graph, net, fontname, show_guards)
        graph = cls._construct_arcs(graph, net)

        return graph

    @classmethod
    def visualize_petri_net(
        cls,
        net: PetriNet,
        show_place_names: bool = False,
        show_guards: bool = True,
        current_marking: Optional[Marking] = None,
        final_marking: Optional[Marking] = None,
        fontname: str = "cantarell",
        color_mapping: Optional[dict[Any, Any]] = None,
    ) -> "PetriNetVisualization":
        if current_marking is None:
            current_marking = Marking()
        if final_marking is None:
            final_marking = Marking()
        return cls(
            cls._construct_graph_viz_petri_net(
                net, show_place_names, show_guards, current_marking, final_marking, fontname, color_mapping
            )
        )

    def get_image_svg(self, prog: str | list = "dot"):
        return self.graph.create_svg(prog=prog)

    def get_dot_string(self) -> str:
        return self.graph.to_string()

    def store_image_svg(self, filename: str, prog: str | list = "dot"):
        return self.graph.write_svg(filename, prog=prog)

    def store_doc_file(self, filename: str):
        return self.graph.write_dot(filename)
