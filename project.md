# Project memory

Last updated: 2026-10-28 (America/Chicago).

## Objective and scope

UIUC CS 562: **Provenance-Aware Multimodal Evidence Aggregation in Multi-Agent Systems**. Investigate false corroboration from repeated/transformed observations and whether trusted acquisition lineage preserves genuine independent corroboration. The intended contribution is an empirical multimodal extension, not provenance or source counting itself.

Current milestone: complete offline pilot, awaiting user review before expansion. No model API access, GPU, model downloads, or paid services are required. Mock agents validate software only.

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

No real vision perception, image transformations, captions, instruction-following baseline, reconciliation model, perceptual matching, cost/latency study, bootstrap uncertainty, or actual LLM behavior has been tested. Related views require an explicit dependence model. Different root IDs alone do not prove independence in real environments.

Next: user reviews pilot design, then explicitly requests the next expansion stage from `docs/expansion.md`. Do not silently scale to 100 instances or add live-model experiments.

## Latest task

Task: `project-memory-and-git`.
Added `project.md` and `AGENTS.md` to retain context and enforce memory updates and task-based branch naming. Initialized a local Git repository on the task branch; no remote or publication requested. Documentation-only change; existing implementation test results above are historical and were not rerun for this change.
