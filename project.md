# Project memory

Last updated: 2026-10-28 (America/Chicago).

## Objective and scope

UIUC CS 562: **Provenance-Aware Multimodal Evidence Aggregation in Multi-Agent Systems**. Investigate false corroboration from repeated/transformed observations and whether trusted acquisition lineage preserves genuine independent corroboration. The intended contribution is an empirical multimodal extension, not provenance or source counting itself.

Current milestone: offline raster transformation and matching validation implemented; awaiting review before further expansion. No model API access, GPU, model downloads, or paid services are required. Mock agents validate software only.

## Persistent user preferences

- Read this file at the start of each chat; update it after every project change.
- Name branches after the current task using lowercase hyphen-separated words. **No `codex/` prefix.** Continue an existing task on its branch; use a new task branch for new work.
- Preserve uncommitted work. Do not assume permission to push or publish.
- Complete authorized implementation and focused verification; ask only when a decision materially changes the research design.

These instructions are also in `AGENTS.md` for future agents.

## Implemented state

Dependency-free Python 3.10+ package with CLI and JSON configuration. Ten seeded, shuffled, balanced hidden states (five of each class), prior .5, sensor reliability .75, three mock workers, and a simulated .90 approval gate.

Paired conditions: single observation, exact replay through three workers, and three conditionally independent acquisitions. The first acquisition is shared across conditions; the other two appear only in the independent condition. Copies inherit values without resampling.

Each acquisition has an SVG sensor card and a JSON record. Workers parse records; they do not perceive images. Trusted registry fields: evidence_id, root_ids, parent_ids, operation, modality. Validation checks ancestry and cycles. Routing preserves roots. Lineage abstains on invalid/unknown ancestry, multi-root inputs, and conflicting root interpretations.

Methods: naive report counting, SHA-256 payload deduplication, and trusted-lineage consolidation. The evaluator-only oracle counts unique acquisitions using exact rational Bayes updates. Methods never receive hidden states or oracle answers.

Outputs include evidence artifacts, registry and worker-input JSONL, separate evaluator truth, 90 result rows, summary CSV/JSON, SVG comparison plot, a constructed identical-independent-payload diagnostic, and SHA-256 manifest. Rates expose denominators; empty denominators are undefined.

## Commands and key files

Run from repository root:

```sh
python3 -m provenance_pilot
python3 -m unittest discover -s tests -v
```

- `README.md`: setup, method behavior, metric definitions, limitations.
- `configs/pilot.json`: seed 562 and pilot settings.
- `provenance_pilot/core.py`: registry, worker interface, methods, oracle, gate.
- `provenance_pilot/data.py`: paired data and artifact generation.
- `provenance_pilot/run.py`: evaluation and outputs.
- `tests/test_pilot.py`: research invariant tests.
- `docs/references.md`: inspected references, license and reuse notes.
- `docs/expansion.md`: staged next steps.
- `artifacts/pilot/`: generated diagnostic outputs; truth/results are not model inputs.

## Verification and interpretation

The implementation task passed all eight unittest groups: hand-calculated oracle, replay/pairing/routing invariants, identical-independent hash false merges, invalid/cyclic provenance, derivation and multi-root abstention, conflicting-claim abstention, deterministic byte-for-byte reproduction/input separation, and gate/config validation. Plot and sample card were rendered locally and visually inspected.

Seed-562 diagnostics: naive replay prematurely approved 4/10 oracle-ineligible cases. Lineage matched the oracle in every evaluation and retained 2/2 oracle-approved independent cases. Hash deduplication retained 0/2 and falsely merged 18 independent report pairs. These are programmed fixture results, not empirical research findings.

## Sources and design decisions

Read the supplied `/Users/aditi/Downloads/562.pdf`. It describes the broader future study; the explicit user request limits current work to an offline pilot. Balanced hidden-state sampling follows the report. No material design contradiction was found.

Inspected separately:
- https://github.com/marcbara/epistemic-sybil-resistance — Gaussian root aggregation and reproducibility patterns; code MIT, experimental materials CC BY 4.0.
- https://arxiv.org/html/2610.06192v1 — binary oracle, copy weight, controls and interventions; displayed license CC BY-NC-ND 4.0.

No external code, data, prompts, or figures were copied. The implementation is original; attribution details are in `docs/references.md`.

## Limitations and next steps

Offline raster transformations, synthetic record conversions, and calibrated pixel matching are now implemented. Real vision perception, semantic captions, instruction-following baselines, reconciliation models, cost/latency studies, bootstrap uncertainty, and actual LLM behavior remain untested. Related views require an explicit dependence model. Different root IDs alone do not prove independence in real environments.

Next: user reviews the transformation milestone, its contact sheets and matching limitations, then explicitly requests another expansion stage from `docs/expansion.md`. Do not silently scale to 100 instances or add live-model experiments.

## Latest task: offline-multimodal-transformations

Branch: `offline-multimodal-transformations` (no prefix). Verified the supplied GitHub repository HEAD matches local commit `1010c2f`; updated origin to `https://github.com/aditinikam/Provenance-Aware_Multimodal_Evidence_Aggregation.git`. No push or remote publication performed.

Implemented `imaging.py`, `matching.py`, and `transformations.py`; added optional Pillow 12.3.0 dependency and `configs/transformations.json`. Added optional operation parameters to registry entries without changing old pilot serialization. Existing summary helper accepts condition/method lists; its defaults remain unchanged.

New experiment: same ten base instances, six paired conditions (single raster, exact replay, resize/JPEG, cropped replay, synthetic cross-modal, independent raster), four methods (naive/hash/lineage/perceptual), 240 evaluations. Raster glyphs use observation fixtures, with 192x108 resizing, JPEG quality 45, and signal-preserving JPEG crops. Derivatives and routed reports inherit roots. Synthetic image-to-record conversion explicitly copies fixture readings and is not pixel extraction. Workers receive bytes plus observed fixture readings, never Y, oracle, calibration labels, or signal-check outcomes.

Perceptual matcher uses full-frame 16x16 RGB mean absolute distance and connected components. It is image-only; JSON/image pairs remain unresolved and separately counted. Calibration uses 12 separate `cal-*` roots (seed 1562), excludes all evaluation roots, and freezes the threshold before scoring. Chosen threshold 0.006352124183006534 minimizes balanced pair error (0.306818), with low-threshold tie-breaking. No evaluation-driven tuning. Three constructed matching controls are excluded from sampled metrics; their hidden state and Brier score are undefined.

Separate pixel audit checks tracked ROI bounds, minimum 24x36 ROI dimensions, and active/inactive seven-segment center luminance. This is a known-geometry signal check, not OCR or model readability proof. Main and control contact sheets were visually inspected after correcting label overlap and footer fragments. All 144 evaluation/control and 48 calibration image checks passed.

New outputs: `artifacts/transformations/` (388 files), including raster and retained SVG/JSON artifacts, contact sheets, provenance, worker inputs, evaluator truth, results, summaries, matching errors, full calibration inputs/pairs, runtime versions, and manifest. Every dataset/output is labeled mock-only. Tight crops may omit visible labels, so keep the accompanying dataset description.

Actual verification:
- `python3 -m provenance_pilot` ran successfully; `git diff --exit-code -- artifacts/pilot` confirmed no tracked artifact changes.
- `python3 -m unittest discover -s tests -p test_pilot.py -v`: 8 passed.
- `.venv/bin/python -m unittest discover -s tests -v`: 18 passed (8 existing + 10 transformation tests).
- `.venv/bin/python -m provenance_pilot.transformations`: generated the delivered 240-row experiment.
- Verified all 387 manifest entries against file hashes, with no unlisted outputs; `git diff --check` found no whitespace errors.
- Tests verify root/parameter inheritance, unchanged acquisition readings, real-byte hashes, signal checks and corruption rejection, invalid ancestry/conflict abstention, calibration disjointness/recomputation, matching errors, no evaluator labels in worker inputs, and whole-output byte-for-byte reproduction in fresh directories.

Environment: system `python3` lacks Pillow. An ignored local `.venv` uses the already-installed bundled Python 3.12.14 with Pillow 12.3.0 (JPEG codec 6.2); no dependency/model downloads or live-model calls occurred. Run the new milestone with `.venv/bin/python -m provenance_pilot.transformations --output artifacts/transformations-review` (choose a fresh directory). A nonempty output directory is refused. Other machines need an existing Pillow environment or local wheelhouse; see README. Original pilot stays dependency-free. Optional tests explicitly skip if Pillow is absent; use `.venv` for the complete suite.

Observed mock diagnostics: lineage equals the oracle across all evaluation cases. Hashing fails to consolidate transformed bytes. Pixel matching consolidates resize/JPEG, misses crop/cross-modal relationships, and falsely merges identical independent images. The nuisance-style independent control is separated by this threshold; identical-independent controls produce three pairwise false merges under hash/perceptual matching. These are fixture behavior, not research efficacy findings.

Next: review this milestone. Do not scale to 100 instances or integrate real models without the next user request. Uncommitted changes are retained on the task branch.
