from typing import Counter

from src.algos.discovery.inductive_miner.inductive_miner import InductiveMiner
from src.objects.graphs.object_centric_event_graph.oceg import ObjectCentricEventGraph
from src.objects.petri_net.arc import Arc
from src.objects.petri_net.oc_nets.object_aware_place import ObjectAwarePlace
from src.objects.petri_net.oc_nets.oc_petri_net import ObjectCentricPetriNet
from src.objects.petri_net.oc_nets.oc_workflow_net import ObjectCentricWorkflowNet
from src.objects.petri_net.variable_arc_net.variable_arc import VariableArc
from src.objects.petri_net.workflow_net import WorkflowNet
from src.objects.process_tree.process_tree import SILENT_TRANSITION_LABEL

CCL = Counter[tuple[str, ...]]  # case centric log


class OCPNMiner:
    @classmethod
    def create_logs(cls, oceg: ObjectCentricEventGraph) -> dict[str, CCL]:
        flattened_logs: dict[str, CCL] = {}
        for obj in oceg.object_nodes:
            object_type = obj.object_type
            if object_type not in flattened_logs:
                flattened_logs[object_type] = Counter()
            flattened_logs[object_type][tuple(e.activity for e in oceg.get_events_for_object(obj.object_id))] += 1
        return flattened_logs

    @classmethod
    def generate_case_centric_nets(cls, case_centric_logs: dict[str, CCL]) -> list[WorkflowNet]:
        nets: list[WorkflowNet] = []
        for object_type, log in case_centric_logs.items():
            net = InductiveMiner.apply(log).to_petri_net()
            net.net.payload["object_type"] = object_type
            nets.append(net)
        return nets

    @classmethod
    def merge_nets(cls, case_centric_nets: list[WorkflowNet]) -> ObjectCentricWorkflowNet:
        oc_net: ObjectCentricPetriNet = ObjectCentricPetriNet()
        source_places = set()
        end_places = set()
        # A single activity shared by several object types is discovered as a separate transition in
        # each per-type net, all carrying the same name (visible transitions are named by their label,
        # silent ones by a unique id). Since transitions are set-deduplicated by name, fuse them into a
        # single canonical object per name and reference that object from both the transition set and
        # the arcs; otherwise the arcs and the transition set would reference diverging duplicates.
        canonical_transitions: dict = {}
        for net in case_centric_nets:
            for transition in net.transitions:
                canonical_transitions.setdefault(transition.name, transition)
        for net in case_centric_nets:
            for place in net.places:
                oa_place = ObjectAwarePlace((net.payload["object_type"] + "-" + place.name), net.payload["object_type"])
                if place == net.source_place:
                    source_places.add(oa_place)
                if place == net.sink_place:
                    end_places.add(oa_place)
                oc_net.places.add(oa_place)
                for arc in net.arcs:
                    if place == arc.source:
                        oc_net.arcs.add(Arc(oa_place, canonical_transitions.setdefault(arc.target.name, arc.target)))
                    elif place == arc.target:
                        oc_net.arcs.add(Arc(canonical_transitions.setdefault(arc.source.name, arc.source), oa_place))

        oc_net.transitions.update(canonical_transitions.values())

        return ObjectCentricWorkflowNet(oc_net, source_places, end_places)

    @classmethod
    def calculate_scores(cls, oceg: ObjectCentricEventGraph, types: set[str]) -> dict[tuple[str, str], float]:
        total_activity_frequency: Counter[str] = Counter()
        # mapping of type (activity)-> N
        single_occurrence_frequency: Counter[tuple[str, str]] = Counter()
        # mapping of type (activity, object type)-> N
        scores = {}
        # mapping of type (activity, object type)-> N
        for event_node in oceg.event_nodes:
            total_activity_frequency[event_node.activity] += 1
            object_count: Counter[str] = Counter()
            for obj in oceg.get_neighbors(event_node.event_id):
                object_count[oceg.get_object_node(obj).object_type] += 1
            for object_type, count in object_count.items():
                if count <= 1:
                    single_occurrence_frequency[(event_node.activity, object_type)] += 1
        for act in total_activity_frequency:
            for object_type in types:
                scores[(act, object_type)] = (
                    single_occurrence_frequency[(act, object_type)] / total_activity_frequency[act]
                )
        return scores

    @classmethod
    def recompute_arcs(
        cls, wf_net: ObjectCentricWorkflowNet, scores: dict[tuple[str, str], float], threshold: float
    ) -> ObjectCentricWorkflowNet:
        """
        Given a set of arcs and a scoring function, the corrsponding variable arcs
        are identified. See "Discovering Object Centric Petri Nets".

        A threshold in range [0,1] is defined for the decision.

        Returns the list of variable arcs, and the recomputed set of arcs,
        where corresponding arcs of type VariableArc are casted accordingly in both
        lists.
        """
        for arc in wf_net.arcs.copy():
            source = arc.source
            target = arc.target
            if isinstance(source, ObjectAwarePlace):
                place_type = source.object_type
                transition_label = target.label
            else:
                place_type = target.object_type
                transition_label = source.label

            if transition_label != SILENT_TRANSITION_LABEL and scores[(transition_label, place_type)] < threshold:
                wf_net.arcs.remove(arc)
                wf_net.arcs.add(VariableArc(source, target))

        return wf_net

    @classmethod
    def apply(  # pylint: disable=too-many-arguments
        cls,
        oceg: ObjectCentricEventGraph,
        threshold: float = 0.8,
    ) -> ObjectCentricWorkflowNet:

        # 1: get object types and flattened logs
        flattened_logs: dict[str, Counter[tuple[str, ...]]] = OCPNMiner.create_logs(oceg)
        # 2: discover case centric petri nets
        workflow_nets = OCPNMiner.generate_case_centric_nets(flattened_logs)
        # 3: merge case centric petri nets.
        oc_wf_net = OCPNMiner.merge_nets(workflow_nets)
        # 4: compute variable arcs
        oc_wf_net = OCPNMiner.recompute_arcs(
            oc_wf_net, OCPNMiner.calculate_scores(oceg, set(flattened_logs.keys())), threshold
        )

        return oc_wf_net
