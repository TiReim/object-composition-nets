# Synthetic log generation

The synthetic datasets cover three object-centric processes with different composition
lifecycles:

- pharmaceutical cold-chain logistics,
- mortgage origination, and
- aircraft line maintenance.

They are ordinary OCEL 2.0 inputs to the evaluation scripts and are registered alongside the five
numbered logs in `data/`.

## Artifacts

- Generator: [`synthetic_data.py`](synthetic_data.py)
- Simulation models: [`synthetic_conets.py`](synthetic_conets.py)
- Generated logs and manifest: [`../data/synthetic_logs/`](../data/synthetic_logs/)
- Dataset registry and theta benchmark:
  [`ocon_theta_benchmark.py`](ocon_theta_benchmark.py)
- Fitness and precision benchmark:
  [`ocon_conformance_benchmark.py`](ocon_conformance_benchmark.py)
- Generation checks: [`../tests/test_synthetic_evaluation.py`](../tests/test_synthetic_evaluation.py)

## Pharmaceutical cold chain

Up to three released vials are packed into a validated cold box, which is assigned to a shipment.
A temperature excursion quarantines the shipment and may repeat after release.

At a transfer hub, `Hub Unload` separates the shipment from the cold box while preserving the
box's vial membership. The box is inspected and delivered independently while the shipment record
is closed. Direct shipments remain intact until final delivery.

## Mortgage origination

One application, one property, and one to four verified documents form a loan dossier.
Underwriting performs concurrent credit assessment and property appraisal before joining the
branches for review. It can request and review conditions repeatedly before approval or decline.
The dossier remains intact until closure or archival.

## Aircraft line maintenance

A work order and up to two line-replaceable units form a work package. A technician and up to two
tools join that package during maintenance. Functional testing can fail and return to rework.

After maintenance, tools and the technician follow independent return and sign-off paths while the
work package continues through inspection and closure.

## Stochastic generation

Every base object type has an independent homogeneous Poisson arrival stream. The nominal arrival
ratios follow the configured composition capacities:

- cold chain: `3:1:1` for vials, cold boxes, and shipments;
- mortgage: `4:1:1` for documents, applications, and properties;
- aircraft maintenance: `2:2:1:1` for LRUs, tools, work orders, and technicians.

All objects enter a shared marking. At each service epoch, one enabled transition is selected
uniformly. Variable inputs consume a uniformly sampled capacity-bounded subset. There are no
transition weights or preassigned object bundles. Loop transitions are capped at two executions
per affected composition.

The finite arrival horizon can leave unmatched or right-censored objects. The written datasets are
complete-lifecycle projections: an event-object component is retained only when every object in it
reaches a configured terminal activity. The manifest records both raw and retained sizes, dropped
object counts, arrival counts and rates, loop caps, and file checksums.

Independent random streams and canonical ordering make each fixed seed reproducible.

## Dataset registration

The generated files are:

- `data/synthetic_logs/pharmaceutical_cold_chain.json`
- `data/synthetic_logs/mortgage_origination.json`
- `data/synthetic_logs/aircraft_maintenance.json`

They are listed in `EVENT_LOGS` together with:

- `data/01_Logistics.json`
- `data/02_P2P.json`
- `data/03_LRM_O2C.json`
- `data/04_LRM_Hiring.json`
- `data/05_Orders.json`

Both evaluation scripts consume this registry. The conformance benchmark skips a dataset
automatically when it has no higher-type at theta `1.0`.

## Reproduce

```bash
# Regenerate the three stochastic datasets and manifest.
poetry run python -m evaluation.synthetic_data --instances 100 --seed 0

# Evaluate all registered datasets over the theta grid.
poetry run python -m evaluation.ocon_theta_benchmark

# Evaluate fitness and precision where theta 1.0 yields a higher-type.
poetry run python -m evaluation.ocon_conformance_benchmark

# Validate generation, registration, checksums, and lifecycle projection.
poetry run python -m unittest tests.test_synthetic_evaluation
```

## Scope

The generated logs are noise-free complete-lifecycle projections. Their raw simulations contain
overlapping work, unmatched arrivals, and right-censored lifecycles; those incomplete components
are reported in the manifest but are not written into the benchmark logs.
