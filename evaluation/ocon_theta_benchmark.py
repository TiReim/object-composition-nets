"""Benchmark the OCoNMiner over the OCEL2 event logs for varying theta thresholds.

For each of the event logs in ``data`` the benchmark
tracks the number of discovered higher-types for theta in {0.5, 0.6, 0.7, 0.8, 0.9, 1.0}.
For theta = 1.0 it additionally measures the runtime of the full OCoNMiner.

The number of discovered higher-types is the number of compositional event logs kept by the
``HigherTypeCoverageFilter`` (one per higher-type). This mirrors exactly the filtering step
performed inside ``OCoNMiner.apply``. The theta-independent preprocessing (object composition
mining, postprocessing and grouping) is computed once per log and reused across all theta values.
"""

import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from src.algos.composition_mining.composition_grouping import (
    CompositionalEventLog,
    CompositionGrouper,
)
from src.algos.composition_mining.compute_object_compositions import ObjectCompositionMiner
from src.algos.composition_mining.filter import HigherTypeCoverageFilter
from src.algos.composition_mining.postprocessing import postprocess_compositions_remove
from src.algos.discovery.ocon_miner.ocon_miner import OCoNMiner
from src.objects.event_log.object_centric.in_out.read_from_file import read_from_file_path
from src.objects.graphs.object_centric_event_graph.oceg import ObjectCentricEventGraph

THETAS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
RUNTIME_THETA = 1.0

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENT_LOG_DIR = REPO_ROOT / "data"
EVENT_LOGS = [
    "01_Logistics.json",
    "02_P2P.json",
    "03_LRM_O2C.json",
    "04_LRM_Hiring.json",
    "05_Orders.json",
    "synthetic_logs/pharmaceutical_cold_chain.json",
    "synthetic_logs/mortgage_origination.json",
    "synthetic_logs/aircraft_maintenance.json",
    "synthetic_logs/customs_clearance.json",
]


def parse_ocel2_xml(xml_file_path: str) -> ObjectCentricEventGraph:
    """Parse an OCEL 2.0 XML file into an ObjectCentricEventGraph."""
    tree = ET.parse(xml_file_path)
    root = tree.getroot()
    if root.tag != "log":
        raise ValueError(f"Expected root element 'log', but found '{root.tag}'")

    oceg = ObjectCentricEventGraph()

    objects_elem = root.find("objects")
    if objects_elem is not None:
        for obj_elem in objects_elem.findall("object"):
            oceg.add_object_node(obj_elem.get("id"), obj_elem.get("type"))

    events_elem = root.find("events")
    if events_elem is not None:
        for event_elem in events_elem.findall("event"):
            event_id = event_elem.get("id")
            oceg.add_event_node(event_id, event_elem.get("type"), datetime.fromisoformat(event_elem.get("time")))
            event_objects_elem = event_elem.find("objects")
            if event_objects_elem is not None:
                for rel_obj_elem in event_objects_elem.findall("relationship"):
                    obj_id = rel_obj_elem.get("object-id")
                    if obj_id:
                        oceg.add_edge(obj_id, event_id)

    return oceg


def load_event_graph(file_name: str) -> ObjectCentricEventGraph:
    path = EVENT_LOG_DIR / file_name
    if path.suffix == ".xml":
        return parse_ocel2_xml(str(path))
    return ObjectCentricEventGraph.from_object_centric_event_log(read_from_file_path(str(path)))


def compute_compositional_event_logs(oceg: ObjectCentricEventGraph) -> set[CompositionalEventLog]:
    """Reproduce the theta-independent preprocessing performed inside OCoNMiner.apply."""
    object_compositions = ObjectCompositionMiner.compute_maximal_object_composition_per_object(oceg)
    processed_object_compositions = postprocess_compositions_remove(object_compositions)
    return CompositionGrouper.compute_compositional_event_logs(processed_object_compositions)


def count_higher_types(cels: set[CompositionalEventLog], oceg: ObjectCentricEventGraph, theta: float) -> int:
    return len(HigherTypeCoverageFilter.filter(cels, oceg, theta=theta))


def measure_runtime(oceg: ObjectCentricEventGraph, theta: float) -> float:
    start = time.perf_counter()
    OCoNMiner().apply(oceg, theta=theta)
    return time.perf_counter() - start


def main() -> None:
    results: dict[str, dict[float, int]] = defaultdict(dict)
    runtimes: dict[str, float] = {}
    load_failures: dict[str, str] = {}

    for file_name in EVENT_LOGS:
        print(f"Processing '{file_name}'...", flush=True)
        try:
            oceg = load_event_graph(file_name)
        except Exception as error:  # pylint: disable=broad-except
            load_failures[file_name] = f"{type(error).__name__}: {error}"
            print(f"  could not be loaded -- {load_failures[file_name]}", flush=True)
            continue

        cels = compute_compositional_event_logs(oceg)
        for theta in THETAS:
            results[file_name][theta] = count_higher_types(cels, oceg, theta)

        runtimes[file_name] = measure_runtime(oceg, RUNTIME_THETA)

    print_results(results, runtimes, load_failures)


def print_results(
    results: dict[str, dict[float, int]], runtimes: dict[str, float], load_failures: dict[str, str]
) -> None:
    theta_headers = [f"theta={theta:.1f}" for theta in THETAS]
    header = ["event log", *theta_headers, f"runtime[s] (theta={RUNTIME_THETA:.1f})"]
    rows = [header]
    for file_name in EVENT_LOGS:
        if file_name in load_failures:
            continue
        row = [file_name]
        row.extend(str(results[file_name][theta]) for theta in THETAS)
        row.append(f"{runtimes[file_name]:.3f}")
        rows.append(row)

    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    print("\nDiscovered higher-types per theta:")
    for r, row in enumerate(rows):
        print("  " + "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        if r == 0:
            print("  " + "  ".join("-" * widths[i] for i in range(len(header))))

    if load_failures:
        print("\nEvent logs that could not be loaded:")
        for file_name, reason in load_failures.items():
            print(f"  {file_name}: {reason}")


if __name__ == "__main__":
    sys.exit(main())
