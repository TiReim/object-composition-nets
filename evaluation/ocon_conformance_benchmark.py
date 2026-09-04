"""Fitness/precision comparison of the plain OCPN vs the compositional OCoN.

For every dataset that discovers at least one higher-type at theta = 1.0, this benchmark:

  1. mines a plain object-centric net (OCPNMiner) and a compositional net (OCoNMiner, theta=1.0)
     on the full log,
  2. determines the relevant object types = the base object types of the higher-types discovered
     at theta = 1.0,
  3. projects both nets and the log onto those relevant object types,
  4. computes fitness and precision of each net against the projected log, once with the normal
     (activity-level) measure and once with the binding-level measure.

The OCPN is replayed with the plain object-centric semantics, the OCoN with the compositional
semantics. Projection of a net keeps only the places whose object type is relevant, the
transitions adjacent to such a place, and the arcs incident to a kept place.
"""

from src.algos.composition_mining.composition_grouping import CompositionGrouper
from src.algos.composition_mining.compute_object_compositions import ObjectCompositionMiner
from src.algos.composition_mining.filter import HigherTypeCoverageFilter
from src.algos.composition_mining.postprocessing import postprocess_compositions_remove
from src.algos.conformance.object_centric.precision_and_fitness import (
    ObjectCentricBindingPrecisionFitness,
    ObjectCentricPrecisionFitness,
    PrecisionFitnessResult,
)
from src.algos.discovery.ocon_miner.ocon_miner import OCoNMiner
from src.algos.discovery.ocpn_miner.ocpn_miner import OCPNMiner
from src.objects.graphs.object_centric_event_graph.oceg import ObjectCentricEventGraph
from src.objects.petri_net.object_composition_nets.semantics import ObjectCompositionSemantics
from src.objects.petri_net.oc_nets.oc_workflow_net import ObjectCentricWorkflowNet
from src.objects.petri_net.oc_nets.semantics import GuardedObjectCentricSemantics
from src.objects.petri_net.utils import PetriNetUtils

from evaluation.ocon_theta_benchmark import EVENT_LOGS, load_event_graph

THETA = 1.0


def relevant_base_types(oceg: ObjectCentricEventGraph) -> set[str]:
    """Base object types of the higher-types discovered at theta = 1.0."""
    object_compositions = ObjectCompositionMiner.compute_maximal_object_composition_per_object(oceg)
    processed = postprocess_compositions_remove(object_compositions)
    cels = CompositionGrouper.compute_compositional_event_logs(processed)
    filtered = HigherTypeCoverageFilter.filter(cels, oceg, theta=THETA)
    base_types: set[str] = set()
    for cel in filtered:
        base_types |= cel.ho_object_type.base_object_types()
    return base_types


def project_log(oceg: ObjectCentricEventGraph, keep_base_types: set[str]) -> ObjectCentricEventGraph:
    """Restrict the log to objects of the relevant types (and events touching such an object)."""
    projected = ObjectCentricEventGraph()
    kept_object_ids: set[str] = set()
    for obj in oceg.object_nodes:
        if obj.object_type in keep_base_types:
            projected.add_object_node(obj.object_id, obj.object_type)
            kept_object_ids.add(obj.object_id)
    for event in oceg.event_nodes:
        kept_neighbors = [oid for oid in oceg.get_neighbors(event.event_id) if oid in kept_object_ids]
        if kept_neighbors:
            projected.add_event_node(event.event_id, event.activity, event.timestamp)
            for oid in kept_neighbors:
                projected.add_edge(event.event_id, oid)
    return projected


def project_net(model: ObjectCentricWorkflowNet, keep_types: set[str]) -> ObjectCentricWorkflowNet:
    """Project a workflow net onto the places whose object type is in ``keep_types``."""
    net = model.net
    kept_places = {place for place in net.places if place.object_type in keep_types}
    kept_transitions = {
        transition
        for transition in net.transitions
        if any(neighbor in kept_places for neighbor in PetriNetUtils.get_neighbors(net, transition))
    }
    kept_arcs = {arc for arc in net.arcs if arc.source in kept_places or arc.target in kept_places}

    projected_net = type(net)()
    projected_net.places.update(kept_places)
    projected_net.transitions.update(kept_transitions)
    projected_net.arcs.update(kept_arcs)
    projected_net.payload.update(net.payload)

    source_places = {place for place in model.source_places if place in kept_places}
    sink_places = {place for place in model.sink_places if place in kept_places}
    return type(model)(projected_net, source_places, sink_places)


def ocon_keep_types(model: ObjectCentricWorkflowNet, keep_base_types: set[str]) -> set[str]:
    """The higher-type place labels of an OCoN whose base object types are all relevant."""
    keep: set[str] = set()
    for place in model.net.places:
        base_types = place.higher_order_object_type.base_object_types()
        if base_types and base_types <= keep_base_types:
            keep.add(place.object_type)
    return keep


def fmt(result: PrecisionFitnessResult) -> str:
    return (
        f"fitness={result.fitness:.4f}  precision={result.precision:.4f}  "
        f"skipped={result.skipped_events:.3f}  events={result.num_events}"
    )


def evaluate_dataset(file_name: str) -> None:
    print(f"\n===== {file_name} =====", flush=True)
    oceg = load_event_graph(file_name)

    base_types = relevant_base_types(oceg)
    print(f"relevant base object types ({len(base_types)}): {sorted(base_types)}", flush=True)
    if not base_types:
        print("no higher-types at theta=1.0; conformance comparison skipped", flush=True)
        return

    print("mining OCPN and OCoN...", flush=True)
    ocpn_model = OCPNMiner.apply(oceg)
    ocon_model = OCoNMiner().apply(oceg, theta=THETA)

    projected_log = project_log(oceg, base_types)
    projected_ocpn = project_net(ocpn_model, base_types)
    projected_ocon = project_net(ocon_model, ocon_keep_types(ocon_model, base_types))
    print(
        f"projected log: {sum(1 for _ in projected_log.event_nodes)} events, "
        f"{sum(1 for _ in projected_log.object_nodes)} objects", flush=True
    )

    results: dict[tuple[str, str], PrecisionFitnessResult] = {}
    configs = [
        ("OCPN", "normal", projected_ocpn, GuardedObjectCentricSemantics, ObjectCentricPrecisionFitness),
        ("OCPN", "binding", projected_ocpn, GuardedObjectCentricSemantics, ObjectCentricBindingPrecisionFitness),
        ("OCoN", "normal", projected_ocon, ObjectCompositionSemantics, ObjectCentricPrecisionFitness),
        ("OCoN", "binding", projected_ocon, ObjectCompositionSemantics, ObjectCentricBindingPrecisionFitness),
    ]
    for model_name, measure, model, semantics, evaluator in configs:
        print(f"  computing {model_name} / {measure}...", flush=True)
        results[(model_name, measure)] = evaluator.apply(projected_log, model, semantics=semantics)

    print(f"\nResults for {file_name}:")
    print(f"{'model':<6}{'measure':<10}{'fitness':>10}{'precision':>12}{'skipped':>10}")
    print("-" * 48)
    for model_name in ("OCPN", "OCoN"):
        for measure in ("normal", "binding"):
            r = results[(model_name, measure)]
            print(f"{model_name:<6}{measure:<10}{r.fitness:>10.4f}{r.precision:>12.4f}{r.skipped_events:>10.3f}")


def main() -> None:
    for file_name in EVENT_LOGS:
        evaluate_dataset(file_name)


if __name__ == "__main__":
    main()
