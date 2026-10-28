# Provenance-Aware Multimodal Evidence Aggregation

UIUC CS 562 offline pilot. **All worker outputs and aggregation behaviors are deterministic software fixtures, not measured LLM behavior.** The intended future contribution is an empirical multimodal extension; provenance tracking and source counting are prior ideas.

## Run

Python 3.10+; no third-party runtime dependencies, credentials, internet, GPU, or model downloads. From this directory:

```sh
python3 -m provenance_pilot
python3 -m unittest discover -s tests -v
```

No installation step is necessary. Optional CLI flags: `--config configs/pilot.json --output artifacts/pilot`. Use a fresh output directory when changing configuration; known output files are overwritten and old unrelated files are not removed. `pyproject.toml` also provides an installable CLI, but package installation is not needed for the offline path.

## Design and assumptions

Ten seeded instances use a shuffled stratified sample of five Y=0 and five Y=1 states. The per-item prior is 0.5; balancing is a fixture design choice, not an IID sample of hidden states. Each acquisition matches its hidden state with probability 0.75. Sensor errors are independently drawn conditional on Y. Three acquisitions are generated per base: the first is shared across conditions, and the other two are used only by the independent condition. Copies never draw new sensor values.

The three paired conditions are one acquisition reported once; that acquisition routed to three workers; and three distinct acquisitions reported by three workers. The same three worker identities are available throughout, with one active for the single condition. Order is fixed for this deterministic pilot. Approval is a local Boolean at estimated P(Y=1) >= 0.90; it executes no action.

Every acquisition produces an SVG image card and a JSON record. Both inherit that acquisition's root. Mock workers parse the JSON record with perfect extraction; **they do not inspect image pixels**. SVG cards use only the observation value and contain no ground truth. Distinct acquisitions may intentionally have identical bytes. This deliberately simple two-payload world makes content matching failures visible, but their frequency is not representative of natural images.

The trusted registry exists outside worker text. Acquisition roots represent observation events, not worker or sensor identities. Derivations inherit the union of their parents' roots. Routing mints report identifiers, never acquisition roots. Validation checks missing parents, cycles, duplicate IDs, malformed acquisitions, and mismatched root inheritance. The harness alone creates acquisitions. This is a trusted boundary, not a cryptographic defense against forged roots.

The three mock aggregators are programmed policies:

- `naive`: Bayes update once per report.
- `hash`: SHA-256 of the evidence payload bytes (not IDs or envelopes), then one update per group.
- `lineage`: validate ancestry and update once per acquisition root.

Lineage abstains on invalid/unknown ancestry, multi-root evidence, or conflicting claims within a root. Conflicts need a real reconciliation design later. Naive/hash deliberately do not consume ancestry; they cannot recognize invalid lineage. No instruction-following baseline is simulated.

Methods receive report values and payloads; only lineage receives the trusted registry. The evaluator computes its oracle from the experimental acquisition assignment and generated observations, independently of the grouping method. Hidden states, acquisition truth mappings, oracle probabilities, and scoring annotations are never passed into workers or methods. Output truth/results files are evaluator-only and must not become model inputs later. This is API-level separation, not an OS sandbox.

The oracle multiplies q/(1-q) for positive and its reciprocal for negative **unique acquisitions**, using rational arithmetic until final float conversion. At q=.75, one positive gives .75, three independent positives give 27/28, and any number of replays of one positive still gives .75.

## Files and outputs

- `provenance_pilot/core.py`: registry, worker protocol, deterministic worker, methods, oracle, gate.
- `provenance_pilot/data.py`: paired generation and SVG/record rendering.
- `provenance_pilot/run.py`: evaluation, summaries, plot, manifest.
- `configs/pilot.json`: frozen pilot settings.
- `tests/test_pilot.py`: focused research invariants.
- `docs/references.md`: inspected sources, attribution, reuse decisions.
- `docs/expansion.md`: bounded next-stage plan.

`artifacts/pilot/` contains evidence cards/records, `registry.jsonl`, `worker_inputs.jsonl`, evaluator-only `evaluator_truth.json`, 90 rows in `results.jsonl`, `summary.csv`, `summary.json`, `comparison.svg`, a resolved configuration, and SHA-256 `manifest.json`. The explicit `identical_independent_diagnostic.json` shows three independently acquired positive values with identical payloads. It is a constructed control and excluded from the ten-instance metrics. Its fixed .5/.75 settings are the requested hand-calculation control regardless of custom configuration.

The plot shows mean absolute probability error by method and condition. It is a deterministic SVG with no plotting dependencies. JSON uses `null` for undefined rates; CSV leaves those cells empty. Paths and timestamps do not enter deterministic artifacts. Reproduction tests compare every output byte in two fresh directories.

## Metric definitions

Each summary row covers one method and one condition (n=10). Results retain per-instance probability, oracle posterior, group assignments, decisions, signed inflation `p - oracle`, absolute error, and Brier score `(p-Y)^2`. Signed inflation is toward Y=1; a negative value can still represent overconfidence in Y=0. The plot uses absolute error to avoid cancellation.

Premature approval rate = approvals among oracle-ineligible cases / count of oracle-ineligible cases. Incorrect approval rate = approvals among Y=0 cases / count of Y=0 cases. Legitimate approval retention = approvals among oracle-eligible cases / count of oracle-eligible cases; the independent-condition row is the corroboration control. Each rate includes numerator and denominator. Undefined denominators remain null, never zero. Abstentions are non-approvals and remain in decision denominators; probability metrics use valid outputs and expose their count.

False merges count unordered report pairs from distinct assigned acquisitions placed in the same group. The denominator is all unordered report pairs from distinct acquisitions. Thus this is a pairwise diagnostic, not a count of unique roots lost. Replay and single conditions have zero eligible pairs and undefined false-merge rates.

Replay rows also include direction-normalized copy weight `(a*logit(p)/log(q/(1-q))-1)/2`, with a=+1 for a positive source and -1 otherwise. It is an analytical fixture check, not a model measurement. No bootstrap intervals or significance claims are made for this pilot.

## Scope and limitations

Eight test groups cover Bayes hand calculations, replay invariance, paired acquisitions, routing, hash false merges, distinct-root retention, invalid/cyclic provenance, derivation roots, multi-root and conflict abstention, gate/config checks, input separation, empty denominators, and complete deterministic reproduction.

This validates software mechanics and evaluation accounting only. It does not validate perception, captioning, instruction following, model calibration, reconciliation, resistance to prompt injection, or benefits with real models. Related views require an explicit dependence model. Root identity alone never proves statistical independence in the real world. See the expansion plan before increasing scale.
