# Object Composition Nets

Research code for the paper **"Discovering and Modeling Compositional Behavior in Object-Centric
Processes"** by Tim Luca Reimers, Sebastiaan J. van Zelst, Jan Niklas van Detten and Marko
Goldschmidt.

The paper introduces *object composition nets* (OCoNs), an extension of object-centric Petri nets
that explicitly models compositions of business objects together with their multiplicities, and a
framework for discovering such nets from object-centric event data. This repository contains the
implementation of the formalism and the discovery framework, plus the scripts and data needed to
reproduce the evaluation in Section 6.

## Repository layout

| path | contents |
|---|---|
| `src/objects/data_types/higher_order_object_types.py` | Higher-order object types and objects (Section 4.1) |
| `src/objects/petri_net/object_composition_nets/` | OCoN syntax (`ObjectCompositionNet`) and semantics (`ObjectCompositionSemantics`) (Section 4.2) |
| `src/algos/composition_mining/` | Mining compositions (Section 5.1): maximal object compositions, postprocessing, aggregation into higher-types and the coverage filter |
| `src/algos/oceg_abstraction/abstract_oceg.py` | Rewriting the event graph to make higher-types explicit (Section 5.2) |
| `src/algos/discovery/ocon_miner/ocon_miner.py` | `OCoNMiner` — the full discovery framework, including the OCPN-to-OCoN transformation (Section 5.3) |
| `src/algos/discovery/ocpn_miner/ocpn_miner.py` | `OCPNMiner` — the object-centric Petri net baseline |
| `src/algos/conformance/object_centric/precision_and_fitness.py` | Activity-level fitness and precision, and the binding-level precision variant |
| `evaluation/` | The evaluation scripts (see below) |
| `data/` | The five input OCEL 2.0 logs and generated logs used in the evaluation |
| `data/synthetic_logs/` | Reproducible stochastic OCEL 2.0 logs and their generation manifest |

The five event logs come from the [OCEL 2.0 collection](https://www.ocel-standard.org) and map to the
dataset names in the paper as follows:

| paper | file |
|---|---|
| Logistics | `01_Logistics.json` |
| P2P | `02_P2P.json` |
| LRM Order-to-Cash | `03_LRM_O2C.json` |
| LRM Hiring | `04_LRM_Hiring.json` |
| Orders | `05_Orders.json` |

## Setup

Requires [Python 3.10](https://www.python.org/downloads/) and
[Poetry](https://www.python-poetry.org/). Nets are rendered with Graphviz, so install that as well
(see the [installation guide](https://graphviz.org/download/); on Ubuntu `sudo apt install
graphviz`).

```console
poetry install
```

## Reproducing the evaluation

### Event-log benchmarks

The benchmark registry contains the five numbered input logs above and the four logs under
`data/synthetic_logs/`. Regenerate the latter with:

```console
poetry run python -m evaluation.synthetic_data
```

Number of discovered higher-types per filter threshold θ, and the runtime of the discovery framework
at θ = 1.0 for every registered log:

```console
poetry run python -m evaluation.ocon_theta_benchmark
```

Fitness and precision of the OCoN and OCPN, both at the activity level and at the binding level.
Logs without a higher-type at θ = 1.0 are skipped automatically:

```console
poetry run python -m evaluation.ocon_conformance_benchmark
```

Generation details and scenario descriptions are documented in
[`evaluation/synthetic_evaluation.md`](evaluation/synthetic_evaluation.md). The seed, arrival
configuration, projection diagnostics, and checksums are recorded in
`data/synthetic_logs/manifest.json`.
