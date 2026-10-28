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

## Offline raster transformation milestone

The original pilot above is unchanged. A separate optional experiment now implements raster rendering, transformations, synthetic image-to-record conversions, and perceptual matching. **It still uses mock fixture readings, not visual extraction or a real model.** It is restricted to ten evaluation base instances.

### Run and dependencies

Pillow **12.3.0** is the sole optional image dependency (`images` extra in `pyproject.toml`). The current workspace has an ignored `.venv` created from the already-installed bundled Python with system site packages; no packages or models were downloaded. From this checkout, run:

```sh
.venv/bin/python -m provenance_pilot.transformations --output artifacts/transformations-review
.venv/bin/python -m unittest discover -s tests -v
```

Choose a new or empty output directory on each run. The transformation command refuses nonempty directories to prevent stale output files. The delivered run is under `artifacts/transformations/`.

On another machine, use an existing Python environment containing Pillow 12.3.0, then run `python -m provenance_pilot.transformations`. If needed, provision Pillow from a local wheelhouse with `python -m pip install --no-index --find-links /path/to/wheels Pillow==12.3.0`. No runtime network access is used. The `.venv` is local and not portable or committed. Without Pillow, the original pilot/tests remain usable; unittest discovery explicitly skips the optional transformation module. Use the Pillow environment to run all **18 tests**.

Files: `imaging.py` handles raster rendering/validation, `matching.py` handles perceptual calibration and inference, and `transformations.py` orchestrates this experiment. `configs/transformations.json` fixes seeds and operation parameters. The original oracle, lineage logic, and metric definitions are shared.

### Artifact and extraction boundaries

Every existing evaluation acquisition additionally renders a 320x180 PNG with a large seven-segment 0/1 glyph. This is a raster card generated from the same observation, not a rasterization of the original SVG layout. Derivatives include a 192x108 Lanczos resize; JPEG quality 45 with no chroma subsampling; and a crop of that JPEG using `(left, top, right, bottom) = (100,45,220,158)`. The crop contains the entire signal region. New registry entries include actual parent IDs, modality, operation parameters, and inherited roots. The registry's optional parameters field preserves the original pilot's parameterless serialization.

`synthetic_image_to_record` uses the fixture reading associated with its cropped-image parent to create a labeled JSON record. It does **not** decode pixels or call a vision model. The worker API receives evidence bytes and an explicit observed `fixture_reading`; worker claims simply retain it. Readings are observation values, not the hidden state Y. No hidden states, oracle answers, or evaluator signal checks are supplied to workers. `evaluator_truth.json`, results, calibration labels, and signal audits are evaluator/harness data, not worker inputs.

All hashes are computed from actual PNG/JPEG/JSON payload bytes, excluding report envelopes. Worker routing preserves the payload and acquisition roots. Synthetic conversion records label their mock origin inside the payload. Image originals and contact sheets have visible mock labels; tight crops can omit those labels, so keep the dataset README/manifest with exported artifacts.

### Signal-preservation validation

Separate evaluator code opens the **encoded image bytes**, checks that the tracked glyph ROI stays in bounds and is at least 24x36 native pixels, then samples 3x3 pixel patches at all seven segment centers. Expected active segments must have mean luminance >=190 and inactive segments <=110. ROI coordinates are propagated through resizing/cropping. Expected segments come from the observation fixture only for this audit; the measured pixels never generate a worker claim.

These known-geometry checks test signal preservation, not general OCR, semantic readability, or model perception. They do not establish that every glyph edge survives. Tests reject a crop that cuts the signal, an excessively small resize, incorrect expected glyphs, and a blacked-out glyph. Inspect `contact_sheet.png` alongside `signal_checks.jsonl` to check the ten first acquisitions visually; `controls_contact_sheet.png` shows independent-lookalike controls. All evaluation/control images and calibration images receive checks, including those not shown on the main sheet.

### Conditions, calibration, and controls

Six paired evaluation conditions use the same ten base instances and generated sensor observations as the original pilot:

| Condition | Evidence presented |
|---|---|
| `single_raster` | One original PNG |
| `exact_replay` | Same PNG routed three times |
| `resized_jpeg` | Original, resized PNG, and JPEG from one root |
| `cropped_replay` | Original, JPEG, and JPEG crop from one root |
| `cross_modal` | Original PNG, crop, and synthetic structured record from one root |
| `independent_raster` | Three original PNGs from three distinct acquisitions |

The three original methods are joined by `perceptual`: a **full-frame 16x16 RGB thumbnail**, mean absolute channel distance on [0,1], and connected-component grouping of image pairs at or below a calibrated threshold. It receives image bytes and modalities, not roots or truth. It cannot match a JSON record to an image; unsupported modality pairs are counted and left unmerged. Conflicting claims in a matched group cause abstention. Trusted lineage retains its invalid/unknown/multi-root and conflicting-interpretation abstentions.

Calibration uses 12 additional roots named `cal-*`, seed 1562, separate from evaluation's `b*-a*` roots and seed 562. Their binary observation appearances are sampled for matching fixtures, without hidden states or a Bayesian score. Each has four raster variants, giving 72 same-root and 1,056 independent pairs. Candidate thresholds are all calibration pair distances plus -1 (no matches); minimize the mean of pairwise false-negative and false-positive rates, breaking ties toward the smaller threshold. Threshold selection uses calibration labels only and finishes before evaluation. It is a pairwise objective; inference's connected components can additionally create transitive merges.

The frozen threshold is **0.006352124183006534**, with calibration balanced pair error **0.306818**. All calibration artifacts, labels, distances, provenance, and signal checks are exported so the selection can be recomputed. Exact reproduction is tested in the same environment; raster bytes may differ across Pillow, font, or JPEG codec builds. `environment.json` records Python, Pillow, and JPEG codec versions.

Three explicitly constructed controls live in `controls.jsonl`, outside the 240 sampled evaluation rows and their summaries:

- Different-looking variants of one root: resize and crop change appearance without new acquisitions.
- Similar-looking independent roots: three positive observations with nuisance border/background variations; distinct bytes. The fixed matcher separates this particular control (zero false merges); visual similarity need not exceed its threshold.
- Byte-identical independent roots: three positive observations rendered identically. Both hash and perceptual matching merge all three independent pairs, while lineage retains three readings.

Independent controls are analytic assignments of three positive observations, not extra sampled hidden states. They have no Brier score or incorrect-approval result. Their posterior is the oracle conditional on those distinct positive readings (27/28).

### Outputs and verified diagnostics

`artifacts/transformations/` includes raster/SVG/JSON evidence, contact sheets, `artifacts.jsonl` with paths and payload hashes, `provenance.jsonl`, worker inputs, separate evaluator truth, signal audits, frozen calibration and its evidence, 240 per-instance evaluations, 12 control evaluations, 24 summary rows, configuration/environment records, and a SHA-256 manifest. Every summary is a mock diagnostic. New matching metrics count false-split pairs among same-root report pairs, false-merge pairs among independent report pairs, abstentions, and unsupported-modality pairs. Empty pair denominators are null, as with the original decision metrics.

Verified locally: both CLI commands run; all 18 tests pass; the original pilot's tracked output artifacts are unchanged; the new output tree reproduces byte-for-byte across two fresh directories; all 144 evaluation/control and 48 calibration raster checks pass; corrected contact sheets were visually inspected.

With this seed, lineage matches the oracle throughout. Hashing leaves all transformed representations separate. Perceptual matching consolidates the resize/JPEG condition, misses crop and cross-modal relationships, and merges identical independent observations. These are behaviors of explicit software rules, not evidence about LLMs or robust multimodal matching. Actual perception, instruction following, reconciliation, natural-image generalization, and statistical efficacy remain untested. Stop here for design review before expanding scope.
