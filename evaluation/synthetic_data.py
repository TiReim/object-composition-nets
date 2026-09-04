"""Generate reproducible stochastic synthetic OCELs.

Every base object type arrives through an independent homogeneous Poisson stream into one shared
marking. At each service epoch an enabled transition is selected uniformly and variable arcs
consume a random capacity-bounded subset. No objects are preassigned to cases and no transition
weights stage the execution order.

The finite arrival horizon naturally leaves right-censored work. The written logs contain the
complete-lifecycle projection of each raw simulation; the manifest records arrival, sink, and
censoring counts.
"""

import argparse
import hashlib
import json
import os
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from src.objects.data_types.higher_order_object_types import HigherOrderObject
from src.objects.data_types.object_reference import ObjectReference
from src.objects.graphs.object_centric_event_graph.oceg import ObjectCentricEventGraph
from src.objects.petri_net.object_composition_nets.object_composition_net import ObjectCompositionWorkflowNet
from src.objects.petri_net.object_composition_nets.object_composition_tokens import ObjectCompositionIdentityToken
from src.objects.petri_net.object_composition_nets.higher_object_aware_place import HigherObjectAwarePlace
from src.objects.petri_net.object_composition_nets.semantics import ObjectCompositionSemantics
from src.objects.petri_net.arc_type import ArcType
from src.objects.petri_net.marking import Marking
from src.objects.petri_net.transition import Transition
from src.objects.petri_net.utils import PetriNetUtils

from evaluation.ocon_theta_benchmark import EVENT_LOG_DIR, load_event_graph
from evaluation.synthetic_conets import (
    SyntheticOCoN,
    aircraft_maintenance_conet,
    mortgage_origination_conet,
    pharmaceutical_cold_chain_conet,
    validate,
)

Ref = tuple[str, str]  # (object_type, object_id)
LOG_DIR = os.path.join(EVENT_LOG_DIR, "synthetic_logs")
MANIFEST_PATH = os.path.join(LOG_DIR, "manifest.json")
DEFAULT_INSTANCES = 100


@dataclass(frozen=True)
class Scenario:
    name: str
    net_builder: Callable[[], SyntheticOCoN]
    arrival_rates: dict[str, float]
    anchor_object_type: str
    service_rate: float
    loop_caps: dict[str, int]
    terminal_activities: frozenset[str]


SCENARIOS = (
    Scenario(
        "pharmaceutical_cold_chain",
        pharmaceutical_cold_chain_conet,
        {"Vial": 0.06, "ColdBox": 0.02, "Shipment": 0.02},
        "Shipment",
        0.50,
        {"Temperature Excursion": 2},
        frozenset({"Deliver Cold Chain", "Deliver Hub Cold Box", "Close Hub Shipment"}),
    ),
    Scenario(
        "mortgage_origination",
        mortgage_origination_conet,
        {"Document": 0.08, "Application": 0.02, "Property": 0.02},
        "Application",
        0.50,
        {"Request Conditions": 2},
        frozenset({"Close Loan", "Archive Decline"}),
    ),
    Scenario(
        "aircraft_maintenance",
        aircraft_maintenance_conet,
        {"LRU": 0.04, "Tool": 0.04, "WorkOrder": 0.02, "Technician": 0.02},
        "WorkOrder",
        0.50,
        {"Test Failed": 2},
        frozenset({"Close Work Order", "Return Tools", "End Technician Assignment"}),
    ),
)


class OCEGBuilder:
    """Incrementally builds an :class:`ObjectCentricEventGraph`, one event at a time.

    Each event is stamped with a strictly increasing timestamp so that the total order on events
    (and therefore every object's event sequence) is exactly the emission order.
    """

    def __init__(self, start: datetime = datetime(2024, 1, 1)) -> None:
        self.oceg = ObjectCentricEventGraph()
        self._start = start
        self._event_index = 0
        self._known_objects: set[str] = set()

    def _add_event(self, activity: str, refs: list[Ref], timestamp: datetime) -> str:
        event_id = f"e{self._event_index:07d}"
        self._event_index += 1
        self.oceg.add_event_node(event_id, activity, timestamp)
        for object_type, object_id in refs:
            if object_id not in self._known_objects:
                self.oceg.add_object_node(object_id, object_type)
                self._known_objects.add(object_id)
            self.oceg.add_edge(event_id, object_id)
        return event_id

    def event_at(self, activity: str, refs: list[Ref], minutes_after_start: float) -> str:
        """Add an event at a deterministic simulated time."""
        return self._add_event(
            activity,
            refs,
            self._start + timedelta(minutes=minutes_after_start),
        )


def _base_references(tokens) -> set[ObjectReference]:
    """The base object references carried by a set/counter of compositional tokens."""
    references: set[ObjectReference] = set()
    for token in tokens:
        references |= token.higher_order_object.flatten()
    return references


def _source_places_by_type(workflow_net: ObjectCompositionWorkflowNet) -> dict[str, HigherObjectAwarePlace]:
    """Map each base object type to the source place that holds its initial tokens."""
    mapping: dict[str, HigherObjectAwarePlace] = {}
    for source in workflow_net.source_places:
        (object_type,) = source.higher_order_object_type.base_object_types()
        mapping[object_type] = source
    return mapping


def _counter_key(counter: Counter) -> tuple:
    """Canonical ordering key for a compositional consumption or production."""
    return tuple(
        sorted(
            (
                str(token.place.name),
                tuple(sorted((ref.otype, ref.oid) for ref in token.higher_order_object.flatten())),
                count,
            )
            for token, count in counter.items()
        )
    )


def _stable_rng(seed: int, namespace: str) -> random.Random:
    """Create a reproducible independent random stream without relying on Python's hash()."""
    digest = hashlib.sha256(f"{seed}:{namespace}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], byteorder="big"))


def _poisson_arrival_schedule(
    expected_anchor_arrivals: int,
    seed: int,
    arrival_rates: dict[str, float],
    anchor_object_type: str,
) -> tuple[list[tuple[float, Ref]], dict]:
    """Sample independent constant-rate arrivals over a finite common horizon."""
    anchor_rate = arrival_rates[anchor_object_type]
    horizon = expected_anchor_arrivals / anchor_rate
    arrivals: list[tuple[float, Ref]] = []
    per_type_times: dict[str, list[float]] = {}

    for object_type, rate in sorted(arrival_rates.items()):
        rng = _stable_rng(seed, f"arrival:{object_type}")
        timestamp = 0.0
        times: list[float] = []
        while True:
            timestamp += rng.expovariate(rate)
            if timestamp > horizon:
                break
            times.append(timestamp)
        for index, timestamp in enumerate(times):
            object_id = f"{object_type.lower()}_{index:05d}"
            arrivals.append((timestamp, (object_type, object_id)))
        per_type_times[object_type] = times

    arrivals.sort(key=lambda entry: (entry[0], entry[1][0], entry[1][1]))
    metadata = {
        "model": "independent_homogeneous_poisson",
        "horizon_minutes": horizon,
        "anchor_object_type": anchor_object_type,
        "expected_anchor_arrivals": expected_anchor_arrivals,
        "rates_per_minute": dict(sorted(arrival_rates.items())),
        "arrival_counts": {object_type: len(times) for object_type, times in sorted(per_type_times.items())},
    }
    return arrivals, metadata


def _inject_object(
    marking: Marking,
    source_places: dict[str, HigherObjectAwarePlace],
    reference: Ref,
) -> None:
    object_type, object_id = reference
    token = ObjectCompositionIdentityToken(
        source_places[object_type],
        HigherOrderObject(frozenset({ObjectReference(object_type, object_id)})),
    )
    marking[token] += 1


def _available_tokens(
    marking: Marking,
    place: HigherObjectAwarePlace,
) -> list[ObjectCompositionIdentityToken]:
    tokens = [
        token
        for token, count in marking.items()
        if count > 0 and token.place == place
        for _ in range(count)
    ]
    return sorted(
        tokens,
        key=lambda token: (
            tuple(
                sorted(
                    (reference.otype, reference.oid)
                    for reference in token.higher_order_object.flatten()
                )
            ),
        ),
    )


def _declared_variable_capacity(
    workflow_net: ObjectCompositionWorkflowNet,
    transition: Transition,
    input_place: HigherObjectAwarePlace,
) -> int:
    """Read a variable input's maximum capacity from the transition's output type."""
    input_type = input_place.higher_order_object_type
    ((component, component_count),) = (
        input_type.components if len(input_type.components) == 1 else ((input_type, 1),)
    )
    input_component = (
        component
        if isinstance(component, str) and component_count == 1
        else input_type
    )
    capacities = []
    for arc in PetriNetUtils.get_post_set_arcs(workflow_net.net, transition):
        output_type = arc.target.higher_order_object_type
        for output_component, capacity in output_type.components:
            if output_component == input_component or (
                not isinstance(output_component, str)
                and not isinstance(input_component, str)
                and output_component.contains_other(input_component)
            ):
                capacities.append(capacity)
    return max(capacities, default=1)


def _random_bounded_firing(
    workflow_net: ObjectCompositionWorkflowNet,
    transition: Transition,
    marking: Marking,
    rng: random.Random,
    fired: Counter,
    loop_caps: dict[str, int],
    max_events: int,
) -> tuple[Counter, list[Counter], tuple] | None:
    """Sample one capacity-bounded consumption without enumerating combinations."""
    label = str(transition.label)
    consumption: Counter = Counter()

    for arc in sorted(
        PetriNetUtils.get_pre_set_arcs(workflow_net.net, transition),
        key=lambda member: str(member.source.name),
    ):
        tokens = _available_tokens(marking, arc.source)
        if label in loop_caps:
            tokens = [
                token
                for token in tokens
                if fired[
                    (
                        label,
                        tuple(
                            sorted(
                                (reference.otype, reference.oid)
                                for reference in token.higher_order_object.flatten()
                            )
                        ),
                    )
                ]
                < loop_caps[label]
            ]
        if arc.type == ArcType.NORMAL:
            if len(tokens) < arc.weight:
                return None
            consumption.update(rng.sample(tokens, arc.weight))
        else:
            maximum = min(
                len(tokens),
                _declared_variable_capacity(workflow_net, transition, arc.source),
            )
            if maximum == 0:
                return None
            consumption.update(rng.sample(tokens, rng.randint(1, maximum)))

    references = tuple(
        sorted(
            (reference.otype, reference.oid)
            for reference in _base_references(consumption)
        )
    )
    cap_key = (label, references)
    if fired[cap_key] >= loop_caps.get(label, max_events):
        return None
    productions = ObjectCompositionSemantics.get_productions(
        workflow_net.net, transition, marking, consumption
    )
    return (
        (consumption, sorted(productions, key=_counter_key), cap_key)
        if productions
        else None
    )


def _references_in_marking(
    marking: Marking,
    sink_places: set[HigherObjectAwarePlace],
) -> tuple[set[Ref], set[Ref]]:
    sink_references: set[Ref] = set()
    in_flight_references: set[Ref] = set()
    for token, count in marking.items():
        if count <= 0:
            continue
        references = {
            (reference.otype, reference.oid)
            for reference in token.higher_order_object.flatten()
        }
        if token.place in sink_places:
            sink_references.update(references)
        else:
            in_flight_references.update(references)
    return sink_references - in_flight_references, in_flight_references


def _max_overlapping_objects(oceg: ObjectCentricEventGraph, object_type: str) -> int:
    points: list[tuple[datetime, int]] = []
    for obj in oceg.object_nodes:
        if obj.object_type != object_type:
            continue
        events = [
            oceg.get_event_node(neighbor)
            for neighbor in oceg.get_neighbors(obj.object_id)
            if oceg.get_event_node(neighbor) is not None
        ]
        if not events:
            continue
        points.append((min(event.timestamp for event in events), 1))
        points.append((max(event.timestamp for event in events), -1))
    active = 0
    maximum = 0
    for _, delta in sorted(points, key=lambda point: (point[0], -point[1])):
        active += delta
        maximum = max(maximum, active)
    return maximum


def _complete_lifecycle_projection(
    oceg: ObjectCentricEventGraph,
    terminal_activities: str | set[str],
) -> tuple[ObjectCentricEventGraph, dict]:
    """Retain complete event-object components and drop right-censored components."""
    if isinstance(terminal_activities, str):
        terminal_activities = {terminal_activities}
    terminal_object_ids = {
        object_id
        for event in oceg.event_nodes
        if event.activity in terminal_activities
        for object_id in oceg.get_neighbors(event.event_id)
        if oceg.get_object_node(object_id) is not None
    }
    visited_object_ids: set[str] = set()
    retained_object_ids: set[str] = set()
    retained_event_ids: set[str] = set()
    retained_components = 0
    dropped_components = 0

    for obj in sorted(oceg.object_nodes, key=lambda member: member.object_id):
        if obj.object_id in visited_object_ids:
            continue
        component_object_ids: set[str] = set()
        component_event_ids: set[str] = set()
        frontier = [obj.object_id]
        visited_nodes: set[str] = set()
        while frontier:
            node_id = frontier.pop()
            if node_id in visited_nodes:
                continue
            visited_nodes.add(node_id)
            if oceg.get_object_node(node_id) is not None:
                component_object_ids.add(node_id)
            elif oceg.get_event_node(node_id) is not None:
                component_event_ids.add(node_id)
            frontier.extend(oceg.get_neighbors(node_id) - visited_nodes)

        visited_object_ids.update(component_object_ids)
        if component_object_ids <= terminal_object_ids:
            retained_components += 1
            retained_object_ids.update(component_object_ids)
            retained_event_ids.update(component_event_ids)
        else:
            dropped_components += 1

    projection = ObjectCentricEventGraph()
    for event in sorted(
        (
            event
            for event in oceg.event_nodes
            if event.event_id in retained_event_ids
        ),
        key=lambda member: (member.timestamp, member.event_id),
    ):
        projection.add_event_node(event.event_id, event.activity, event.timestamp)
    for obj in sorted(
        (
            obj
            for obj in oceg.object_nodes
            if obj.object_id in retained_object_ids
        ),
        key=lambda member: (member.object_type, member.object_id),
    ):
        projection.add_object_node(obj.object_id, obj.object_type)
    for event_id in retained_event_ids:
        for object_id in oceg.get_neighbors(event_id):
            if object_id in retained_object_ids:
                projection.add_edge(event_id, object_id)

    raw_objects = list(oceg.object_nodes)
    retained_objects = list(projection.object_nodes)
    metadata = {
        "terminal_activities": sorted(terminal_activities),
        "retained_components": retained_components,
        "dropped_components": dropped_components,
        "raw_events": len(list(oceg.event_nodes)),
        "retained_events": len(list(projection.event_nodes)),
        "dropped_events": len(list(oceg.event_nodes)) - len(list(projection.event_nodes)),
        "raw_objects": len(raw_objects),
        "retained_objects": len(retained_objects),
        "dropped_objects": len(raw_objects) - len(retained_objects),
        "retained_object_type_counts": dict(
            sorted(Counter(obj.object_type for obj in retained_objects).items())
        ),
        "dropped_object_type_counts": dict(
            sorted(
                (
                    Counter(obj.object_type for obj in raw_objects)
                    - Counter(obj.object_type for obj in retained_objects)
                ).items()
            )
        ),
    }
    return projection, metadata


def generate_stochastic_log(
    scenario: Scenario,
    expected_anchor_arrivals: int,
    seed: int = 0,
) -> tuple[ObjectCentricEventGraph, dict]:
    """Play one scenario with independent arrivals and no preassigned object bundles."""
    workflow_net = scenario.net_builder().net
    source_places = _source_places_by_type(workflow_net)
    arrivals, arrival_metadata = _poisson_arrival_schedule(
        expected_anchor_arrivals,
        seed,
        scenario.arrival_rates,
        scenario.anchor_object_type,
    )
    process_rng = _stable_rng(seed, f"process:{scenario.name}")
    builder = OCEGBuilder()
    marking: Marking = Marking()
    fired: Counter = Counter()
    composition_types: dict[str, Counter] = {}
    arrival_index = 0
    current_time = 0.0
    next_service_time = process_rng.expovariate(scenario.service_rate)
    transitions = sorted(
        workflow_net.net.transitions,
        key=lambda transition: (str(transition.label), str(transition.name)),
    )
    max_events = max(1_000, len(arrivals) * 20)
    max_scheduler_steps = max(10_000, (len(arrivals) + max_events) * 10)
    event_count = 0
    terminal_state = "safety_limit"

    for _ in range(max_scheduler_steps):
        next_arrival_time = (
            arrivals[arrival_index][0] if arrival_index < len(arrivals) else float("inf")
        )
        if (
            arrival_index < len(arrivals)
            and next_arrival_time <= next_service_time
        ):
            current_time, reference = arrivals[arrival_index]
            _inject_object(marking, source_places, reference)
            arrival_index += 1
            continue

        current_time = next_service_time
        candidates = []
        for transition in transitions:
            firing = _random_bounded_firing(
                workflow_net,
                transition,
                marking,
                process_rng,
                fired,
                scenario.loop_caps,
                max_events,
            )
            if firing is not None:
                candidates.append((transition, firing))

        if not candidates:
            if arrival_index < len(arrivals):
                next_service_time = (
                    arrivals[arrival_index][0]
                    + process_rng.expovariate(scenario.service_rate)
                )
                continue
            remaining = [token for token, count in marking.items() if count > 0]
            terminal_state = (
                "drained"
                if remaining
                and all(token.place in workflow_net.sink_places for token in remaining)
                else "deadlock"
            )
            break

        next_transition, firing = process_rng.choice(candidates)
        consumption, productions, cap_key = firing
        production = process_rng.choice(productions)
        marking = ObjectCompositionSemantics.fire(
            workflow_net.net,
            next_transition,
            marking,
            consumption,
            production,
            sanity_check=False,
        )
        fired[cap_key] += 1
        event_count += 1

        references = _base_references(consumption) | _base_references(production)
        builder.event_at(
            str(next_transition.label),
            sorted((reference.otype, reference.oid) for reference in references),
            current_time,
        )
        if next_transition.payload.get("scope", (0, 0))[1] > 0:
            label_counts = composition_types.setdefault(
                str(next_transition.label), Counter()
            )
            for token, count in production.items():
                label_counts[str(token.higher_order_object.higher_order_object_type)] += count

        if event_count >= max_events:
            break
        remaining = [token for token, count in marking.items() if count > 0]
        if (
            arrival_index == len(arrivals)
            and remaining
            and all(token.place in workflow_net.sink_places for token in remaining)
        ):
            terminal_state = "drained"
            break
        next_service_time = current_time + process_rng.expovariate(
            scenario.service_rate
        )

    sink_references, in_flight_references = _references_in_marking(
        marking, workflow_net.sink_places
    )
    diagnostics = {
        "schema_version": 1,
        "scenario": scenario.name,
        "seed": seed,
        "target_anchor_arrivals": expected_anchor_arrivals,
        "anchor_object_type": scenario.anchor_object_type,
        "arrival_process": arrival_metadata,
        "service_rate_per_minute": scenario.service_rate,
        "transition_selection": "uniform_transitions_random_bounded_subsets",
        "terminal_state": terminal_state,
        "events": len(list(builder.oceg.event_nodes)),
        "observed_objects": len(list(builder.oceg.object_nodes)),
        "sink_object_counts": dict(
            sorted(Counter(object_type for object_type, _ in sink_references).items())
        ),
        "in_flight_object_counts": dict(
            sorted(Counter(object_type for object_type, _ in in_flight_references).items())
        ),
        "max_overlapping_anchor_objects": _max_overlapping_objects(
            builder.oceg, scenario.anchor_object_type
        ),
        "composition_types": {
            label: dict(sorted(counts.items()))
            for label, counts in sorted(composition_types.items())
        },
        "marking_by_place": {
            str(place): count
            for place, count in sorted(
                Counter(
                    token.place.name
                    for token, token_count in marking.items()
                    for _ in range(max(0, token_count))
                ).items(),
                key=lambda entry: str(entry[0]),
            )
        },
    }
    return builder.oceg, diagnostics


def generate_complete_stochastic_log(
    scenario: Scenario,
    expected_anchor_arrivals: int,
    seed: int = 0,
) -> tuple[ObjectCentricEventGraph, dict]:
    """Generate an open-system log and retain only complete lifecycle components."""
    raw_oceg, diagnostics = generate_stochastic_log(
        scenario, expected_anchor_arrivals, seed
    )
    complete_oceg, projection = _complete_lifecycle_projection(
        raw_oceg, set(scenario.terminal_activities)
    )
    retained_anchor_objects = sum(
        obj.object_type == scenario.anchor_object_type
        for obj in complete_oceg.object_nodes
    )
    if retained_anchor_objects == 0:
        raise RuntimeError(
            f"{scenario.name} produced no complete {scenario.anchor_object_type} lifecycles"
        )
    diagnostics["raw_log"] = _log_summary(raw_oceg)
    diagnostics["complete_lifecycle_projection"] = {
        **projection,
        "summary": _log_summary(complete_oceg),
        "retained_anchor_objects": retained_anchor_objects,
    }
    return complete_oceg, diagnostics


def write_ocel2_json(oceg: ObjectCentricEventGraph, path: str) -> None:
    """Serialize an event graph to the OCEL 2.0 JSON format read by ``read_from_file_path``."""
    events = sorted(oceg.event_nodes, key=lambda event: (event.timestamp, event.event_id))
    objects = sorted(oceg.object_nodes, key=lambda obj: (str(obj.object_type), str(obj.object_id)))
    document = {
        "eventTypes": [{"name": activity} for activity in sorted({event.activity for event in events})],
        "objectTypes": [{"name": object_type} for object_type in sorted({obj.object_type for obj in objects})],
        "events": [
            {
                "id": event.event_id,
                "type": event.activity,
                "time": event.timestamp.isoformat(),
                "relationships": [
                    {"objectId": object_id, "qualifier": event.activity}
                    for object_id in sorted(oceg.get_neighbors(event.event_id))
                    if oceg.get_object_node(object_id) is not None
                ],
            }
            for event in events
        ],
        "objects": [
            {"id": obj.object_id, "type": obj.object_type, "attributes": [], "relationships": []}
            for obj in objects
        ],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(document, file, indent=2)
        file.write("\n")


def _write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write("\n")


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _log_summary(oceg: ObjectCentricEventGraph) -> dict:
    events = list(oceg.event_nodes)
    objects = list(oceg.object_nodes)
    return {
        "events": len(events),
        "objects": len(objects),
        "activities": len({event.activity for event in events}),
        "activity_counts": dict(sorted(Counter(event.activity for event in events).items())),
        "object_type_counts": dict(sorted(Counter(obj.object_type for obj in objects).items())),
    }


def _net_summary(synthetic: SyntheticOCoN) -> dict:
    net = synthetic.net.net
    return {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
        "transition_scopes": {
            str(member.label): list(member.payload["scope"])
            for member in sorted(net.transitions, key=lambda transition_: str(transition_.label))
        },
    }


def generate_and_persist(scenario: Scenario, instances: int, seed: int) -> dict:
    """Generate the scenario log, write it to OCEL 2.0 JSON, and round-trip check the reload."""
    oceg, generation = generate_complete_stochastic_log(scenario, instances, seed)
    summary = _log_summary(oceg)
    retained_anchors = generation["complete_lifecycle_projection"][
        "retained_anchor_objects"
    ]
    print(
        f"retained {retained_anchors} complete {scenario.anchor_object_type} lifecycles "
        f"-> {summary['events']} events, {summary['objects']} objects",
        flush=True,
    )

    dataset = f"synthetic_logs/{scenario.name}.json"
    path = os.path.join(EVENT_LOG_DIR, dataset)
    write_ocel2_json(oceg, path)
    reloaded_summary = _log_summary(load_event_graph(dataset))
    if (reloaded_summary["events"], reloaded_summary["objects"]) != (summary["events"], summary["objects"]):
        raise RuntimeError(f"OCEL round trip changed event/object counts for {scenario.name}")
    print(
        f"wrote {path} (reload [OK]: {reloaded_summary['events']} events, "
        f"{reloaded_summary['objects']} objects)",
        flush=True,
    )

    synthetic = scenario.net_builder()
    problems = validate(synthetic)
    if problems:
        raise RuntimeError(f"{scenario.name} has an invalid simulation net: {problems}")
    metadata = {
        "dataset": dataset,
        "sha256": _sha256(path),
        "loop_caps": dict(sorted(scenario.loop_caps.items())),
        "generation": generation,
        "log": summary,
        "simulation_net": _net_summary(synthetic),
    }
    return metadata


def generate_logs(instances: int, seed: int) -> dict:
    os.makedirs(LOG_DIR, exist_ok=True)
    scenario_metadata = {}
    for scenario in SCENARIOS:
        print(f"\n===== generate {scenario.name} =====", flush=True)
        scenario_metadata[scenario.name] = generate_and_persist(
            scenario, instances, seed
        )
    manifest = {
        "schema_version": 3,
        "seed": seed,
        "expected_anchor_arrivals_per_scenario": instances,
        "scenarios": scenario_metadata,
    }
    _write_json(MANIFEST_PATH, manifest)
    print(f"\nwrote {MANIFEST_PATH}", flush=True)
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--instances",
        type=int,
        default=DEFAULT_INSTANCES,
        help="expected arrivals of each scenario's anchor object type",
    )
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.instances < 1:
        raise ValueError("--instances must be positive")
    generate_logs(args.instances, args.seed)


if __name__ == "__main__":
    main()
