import uuid
from collections import defaultdict
from typing import cast

from src.algos.composition_mining.composition_grouping import CompositionalEventLog, CompositionGrouper
from src.algos.composition_mining.compute_object_compositions import ObjectCompositionMiner
from src.algos.composition_mining.filter import HigherTypeCoverageFilter
from src.algos.composition_mining.postprocessing import postprocess_compositions_remove
from src.algos.discovery.ocpn_miner.ocpn_miner import OCPNMiner
from src.algos.oceg_abstraction.abstract_oceg import OCEGAbstraction
from src.objects.data_types.higher_order_object_types import HigherOrderObjectType
from src.objects.graphs.object_centric_event_graph.oceg import ObjectCentricEventGraph
from src.objects.petri_net.arc import Arc
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.object_composition_nets.object_composition_net import (
    ObjectCompositionNet,
    ObjectCompositionWorkflowNet,
)
from src.objects.petri_net.object_composition_nets.higher_object_aware_place import HigherObjectAwarePlace
from src.objects.petri_net.factories.arc_factory import ArcFactory
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace
from src.objects.petri_net.oc_nets.oc_workflow_net import ObjectCentricWorkflowNet
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.utils import PetriNetUtils
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL


class OCoNMiner:
    def apply(self, oceg: ObjectCentricEventGraph, theta: float = 1.0) -> ObjectCompositionWorkflowNet:
        object_compositions = ObjectCompositionMiner.compute_maximal_object_composition_per_object(oceg)
        processed_object_compositions = postprocess_compositions_remove(object_compositions)
        compositional_event_logs = CompositionGrouper.compute_compositional_event_logs(processed_object_compositions)
        filtered_compositional_event_logs = HigherTypeCoverageFilter.filter(
            compositional_event_logs, oceg, theta=theta
        )
        abstracted_oceg = OCEGAbstraction.abstract_oceg(oceg, filtered_compositional_event_logs)
        mined_ocpn = OCPNMiner.apply(abstracted_oceg)
        initial_ocon = self.transform_ocpn_into_ocon(mined_ocpn, filtered_compositional_event_logs)
        ocon = self.replace_transitions(initial_ocon, filtered_compositional_event_logs)
        return ocon

    def replace_transitions(
        self, ocon: ObjectCompositionWorkflowNet, compositional_event_logs: set[CompositionalEventLog]
    ) -> ObjectCompositionWorkflowNet:
        start_labels, end_labels, member_boundaries = self._compute_composition_activity_labels(
            compositional_event_logs
        )

        # Step 1: relabel the start transitions to silent, drop their (discovered) preset, and give
        # each a fresh unique input place typed with the higher-type.
        start_input_places: dict[str, set[HigherObjectAwarePlace]] = defaultdict(set)
        for start_label, ho_object_type in start_labels.items():
            for transition in self._transitions_with_label(ocon, start_label):
                start_input_places[start_label].add(
                    self._make_boundary_silent(ocon, transition, ho_object_type, is_start=True)
                )

        # Step 2: symmetrically for the end transitions, giving each a fresh unique output place.
        end_output_places: dict[str, set[HigherObjectAwarePlace]] = defaultdict(set)
        for end_label, ho_object_type in end_labels.items():
            for transition in self._transitions_with_label(ocon, end_label):
                end_output_places[end_label].add(
                    self._make_boundary_silent(ocon, transition, ho_object_type, is_start=False)
                )

        # Step 3: replace every member transition with a pair of silent (0,1)/(1,0) transitions that
        # compose and decompose the higher-object around the discovered control flow.
        for member_label, (start_label, end_label) in member_boundaries.items():
            for transition in self._transitions_with_label(ocon, member_label):
                t_start = Transition(label=SILENT_TRANSITION_LABEL, payload={"scope": (0, 1)})
                t_end = Transition(label=SILENT_TRANSITION_LABEL, payload={"scope": (1, 0)})
                for arc in cast(set[Arc], PetriNetUtils.get_pre_set_arcs(ocon, transition)):
                    ocon.arcs.remove(arc)
                    ocon.arcs.add(ArcFactory.create_arc(arc.type, arc.source, t_start, arc.weight, arc.payload))
                for arc in cast(set[Arc], PetriNetUtils.get_post_set_arcs(ocon, transition)):
                    ocon.arcs.remove(arc)
                    ocon.arcs.add(ArcFactory.create_arc(arc.type, t_end, arc.target, arc.weight, arc.payload))
                for input_place in start_input_places[start_label]:
                    ocon.arcs.add(ArcFactory.create_arc(ArcType.NORMAL, t_start, input_place, 1))
                for output_place in end_output_places[end_label]:
                    ocon.arcs.add(ArcFactory.create_arc(ArcType.NORMAL, output_place, t_end, 1))
                ocon.transitions.remove(transition)
                ocon.transitions.add(t_start)
                ocon.transitions.add(t_end)

        ocon = self._postprocess_ocon(ocon)
        # The discovered source/sink places of the higher-types were removed, so the higher-object is
        # created and destroyed solely by the composition. Drop them from the workflow boundaries.
        source_places = {place for place in ocon.source_places if place in ocon.places}
        sink_places = {place for place in ocon.sink_places if place in ocon.places}
        return ObjectCompositionWorkflowNet(ocon.net, source_places, sink_places)

    @staticmethod
    def _compute_composition_activity_labels(
        compositional_event_logs: set[CompositionalEventLog],
    ) -> tuple[dict[str, HigherOrderObjectType], dict[str, HigherOrderObjectType], dict[str, tuple[str, str]]]:
        start_labels: dict[str, HigherOrderObjectType] = {}
        end_labels: dict[str, HigherOrderObjectType] = {}
        member_boundaries: dict[str, tuple[str, str]] = {}
        for cel in compositional_event_logs:
            ho_type_label = str(cel.ho_object_type)
            for composition in cel.compositions:
                first_activity = composition.event_sequence[0].activity
                last_activity = composition.event_sequence[-1].activity
                start_label, member_label, end_label = OCEGAbstraction.composition_activities(
                    ho_type_label, first_activity, last_activity
                )
                start_labels[start_label] = cel.ho_object_type
                end_labels[end_label] = cel.ho_object_type
                member_boundaries[member_label] = (start_label, end_label)
        return start_labels, end_labels, member_boundaries

    @staticmethod
    def _transitions_with_label(ocon: ObjectCompositionWorkflowNet, label: str) -> list[Transition]:
        return [transition for transition in ocon.transitions if transition.label == label]

    @staticmethod
    def _make_boundary_silent(
        ocon: ObjectCompositionWorkflowNet,
        transition: Transition,
        ho_object_type: HigherOrderObjectType,
        is_start: bool,
    ) -> HigherObjectAwarePlace:
        """Relabel a start/end boundary transition to silent, detach its discovered preset (start) or
        postset (end), and attach a fresh unique input/output place typed with the higher-type."""
        silent_transition = Transition(label=SILENT_TRANSITION_LABEL)
        # Keep the arcs that connect to the discovered control flow of the higher-type.
        kept_arcs = (
            PetriNetUtils.get_post_set_arcs(ocon, transition)
            if is_start
            else PetriNetUtils.get_pre_set_arcs(ocon, transition)
        )
        for arc in cast(set[Arc], kept_arcs):
            ocon.arcs.remove(arc)
            if is_start:
                ocon.arcs.add(ArcFactory.create_arc(arc.type, silent_transition, arc.target, arc.weight, arc.payload))
            else:
                ocon.arcs.add(ArcFactory.create_arc(arc.type, arc.source, silent_transition, arc.weight, arc.payload))
        # Detach the discovered preset (start) / postset (end) and drop the now-orphaned boundary places.
        detached_arcs = (
            PetriNetUtils.get_pre_set_arcs(ocon, transition)
            if is_start
            else PetriNetUtils.get_post_set_arcs(ocon, transition)
        )
        for arc in cast(set[Arc], detached_arcs):
            ocon.arcs.remove(arc)
            place = PetriNetUtils.get_connected_place(arc)
            if not PetriNetUtils.get_connected_arcs(ocon, place):
                ocon.places.discard(place)
        # Add the fresh unique place typed with the higher-type.
        boundary_place = HigherObjectAwarePlace(("in|" if is_start else "out|") + str(uuid.uuid4()), ho_object_type)
        ocon.places.add(boundary_place)
        if is_start:
            ocon.arcs.add(ArcFactory.create_arc(ArcType.NORMAL, boundary_place, silent_transition, 1))
        else:
            ocon.arcs.add(ArcFactory.create_arc(ArcType.NORMAL, silent_transition, boundary_place, 1))
        ocon.transitions.remove(transition)
        ocon.transitions.add(silent_transition)
        return boundary_place

    def transform_ocpn_into_ocon(
        self, ocpn: ObjectCentricWorkflowNet, compositional_event_logs: set[CompositionalEventLog]
    ) -> ObjectCompositionWorkflowNet:
        type_mapping = {str(cel.ho_object_type): cel.ho_object_type for cel in compositional_event_logs}
        places: dict[ObjectAwarePlace, HigherObjectAwarePlace] = {}
        for place in ocpn.places:
            if place.object_type in type_mapping:
                places[place] = HigherObjectAwarePlace(place.name, type_mapping[place.object_type])
            else:
                places[place] = HigherObjectAwarePlace(
                    place.name, HigherOrderObjectType(frozenset({(place.object_type, 1)}))
                )
        arcs: set[Arc] = set()
        for arc in ocpn.arcs:
            if arc.source in places:
                if arc.type == ArcType.NORMAL:
                    arcs.add(ArcFactory.create_arc(ArcType.NORMAL, places[arc.source], arc.target, arc.weight))
                else:
                    arcs.add(ArcFactory.create_arc(ArcType.VARIABLE, places[arc.source], arc.target, arc.weight))
            elif arc.target in places:
                if arc.type == ArcType.NORMAL:
                    arcs.add(ArcFactory.create_arc(ArcType.NORMAL, arc.source, places[arc.target], arc.weight))
                else:
                    arcs.add(ArcFactory.create_arc(ArcType.VARIABLE, arc.source, places[arc.target], arc.weight))
            else:
                raise ValueError("Arc does not connect to any place in the mapping.")
        ocon: ObjectCompositionNet = ObjectCompositionNet(
            places=set(places.values()), transitions=ocpn.transitions, arcs=arcs
        )
        source_places = {places[place] for place in ocpn.source_places}
        sink_places = {places[place] for place in ocpn.sink_places}
        return ObjectCompositionWorkflowNet(ocon, source_places, sink_places)

    def _postprocess_ocon(self, ocon: ObjectCompositionWorkflowNet):
        for place in ocon.places.copy():
            in_arcs: set[Arc] = PetriNetUtils.get_pre_set_arcs(ocon, place)
            out_arcs: set[Arc] = PetriNetUtils.get_post_set_arcs(ocon, place)
            if len(in_arcs) == 1 and len(out_arcs) == 1:
                in_arc = next(iter(in_arcs))
                out_arc = next(iter(out_arcs))
                if (
                    len(PetriNetUtils.get_post_set_arcs(ocon, in_arc.source)) == 1
                    and in_arc.type == ArcType.NORMAL
                    and in_arc.source.label == SILENT_TRANSITION_LABEL
                ):
                    ocon.arcs.remove(in_arc)
                    ocon.arcs.remove(out_arc)
                    for arc in cast(set[Arc], PetriNetUtils.get_pre_set_arcs(ocon, in_arc.source)):
                        ocon.arcs.remove(arc)
                        # Collapsing ``arc.source -> silent -> place -> out_arc.target`` must keep a
                        # variable consumption/production anywhere on the path variable; otherwise a
                        # composing transition that folded a variable number of objects (out_arc) would
                        # be rewired to fold exactly one.
                        merged_type = ArcType.VARIABLE if ArcType.VARIABLE in (arc.type, out_arc.type) else arc.type
                        ocon.arcs.add(ArcFactory.create_arc(merged_type, arc.source, out_arc.target, arc.weight))
                    if "scope" in in_arc.source.payload:
                        if "scope" in out_arc.target.payload:
                            out_arc.target.payload["scope"] = (
                                in_arc.source.payload["scope"][0] + out_arc.target.payload["scope"][0],
                                in_arc.source.payload["scope"][1] + out_arc.target.payload["scope"][1],
                            )
                        else:
                            out_arc.target.payload["scope"] = in_arc.source.payload["scope"]
                    ocon.transitions.remove(in_arc.source)
                    ocon.places.remove(place)
                elif (
                    len(PetriNetUtils.get_pre_set_arcs(ocon, out_arc.target)) == 1
                    and out_arc.type == ArcType.NORMAL
                    and out_arc.target.label == SILENT_TRANSITION_LABEL
                ):
                    ocon.arcs.remove(in_arc)
                    ocon.arcs.remove(out_arc)
                    for arc in cast(set[Arc], PetriNetUtils.get_post_set_arcs(ocon, out_arc.target)):
                        ocon.arcs.remove(arc)
                        # Symmetric to the branch above: keep a variable arc anywhere along the
                        # collapsed ``in_arc.source -> place -> silent -> arc.target`` path variable.
                        merged_type = ArcType.VARIABLE if ArcType.VARIABLE in (arc.type, in_arc.type) else arc.type
                        ocon.arcs.add(ArcFactory.create_arc(merged_type, in_arc.source, arc.target, arc.weight))
                    if "scope" in out_arc.target.payload:
                        if "scope" in in_arc.source.payload:
                            in_arc.source.payload["scope"] = (
                                in_arc.source.payload["scope"][0] + out_arc.target.payload["scope"][0],
                                in_arc.source.payload["scope"][1] + out_arc.target.payload["scope"][1],
                            )
                        else:
                            in_arc.source.payload["scope"] = out_arc.target.payload["scope"]
                    ocon.transitions.remove(out_arc.target)
                    ocon.places.remove(place)
        return ocon
