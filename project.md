# Project memory

Updated October 30, 2026 (America/Chicago). Branch: `real-vision-preliminary-results`.

## Persistent instructions

Read this file at each task. Update it after changes with actual verification,
limitations, and next steps. Use lowercase task-named branches, never `codex/`.
Preserve uncommitted work; no implicit commit/push/publication. Maintain default
offline execution without credentials, paid services, GPU, or model downloads.
Truth/oracle values must stay outside worker/model inputs. Unknown ancestry and
unresolved conflicting root interpretations must not become independent support.
Mock diagnostics are never empirical LLM findings.

## Objective and current status

UIUC CS 562: provenance-aware multimodal evidence aggregation. Distinguish extra
representations of one acquisition from genuinely independent acquisitions.

The user authorized real vision extraction, actual model-produced cross-modal
records, LLM aggregation with matched cached workers, failure/cost logging, and
preliminary results for the PDF. Latest explicit constraints: free-tier-eligible
Gemini Flash, exact $0 cap, no paid fallback, stop on quota exhaustion, first two
instances then ten. User confirmed free-tier project with billing disabled; key
is saved outside the repository. Never display it or put it in Git.

**Live pilot is incomplete. Do not start ten yet.** Google authenticated model
lookup succeeded, but generation encountered timeout and HTTP 503 high demand.
There is no successful vision extraction or valid aggregation comparison.
The PDF addendum reports software diagnostics and the incomplete live status,
not invented empirical findings. No 100-instance run was performed.

## Current implementation

- Original dependency-free offline pilot: ten balanced seeded instances, prior .5,
  sensor reliability .75, three workers, approval gate .90. Three conditions and
  naive/hash/lineage policies; truth separated, exact rational evaluator oracle.
- Reviewed transformations: six paired conditions, four policies, 240 evaluations.
  PNG, 192x108 resize, JPEG quality45, crop [100,45,220,158], explicitly synthetic
  image-to-record fixture copy. Offline workers do not perceive pixels.
- Every derivative inherits parent roots. Hashing uses actual bytes. Perceptual
  baseline uses16x16 RGB distance, threshold .006352124183006534 calibrated on12
  disjoint roots (seed1562). Appearance templates overlap evaluation; no claim of
  new-appearance generalization or image/JSON semantic matching.
- Unknown ancestry/conflicts abstain. Summary decision denominators retain
  failures/abstentions; oracle means include all cases. Missing partitions yield
  undefined matching errors. Review: `docs/review-offline-transformations.md`.
- Separate opt-in `provenance_pilot/vision/` accepts actual image bytes, no fixture
  reading. Gemini-produced structured records inherit crop parent/root in trusted
  code. Three methods: naive LLM, instruction LLM, trusted-lineage preprocessing
  plus same LLM; cached worker content is paired across methods. All methods see
  root metadata; naive is not forced to count sources or ignore ancestry.
- `gemini-3.8-flash` image and structured-output support/free pricing verified in
  official Google docs October30; authenticated model lookup also succeeded.
  Google's OpenAI-compatible endpoint, low reasoning, max2048 completion tokens,
  provider-default sampling, minimum7s request spacing. No OpenAI service calls.
- Cache stores request/raw response, returned model, usage, latency and free-tier
  cost estimate. The $0 guarantee relies on user-confirmed billing-disabled
  account; no provider billing inspection API was used. No retries/fallback.
  HTTP/quota errors persist a stop latch. Interrupted unknown calls are not resent.
- Source/config/evidence changes reject resume. Atomic checksummed result
  checkpoints, request/response cache, process lock, prefix expansion, paired
  whole-base bootstrap, summaries, plots and contact sheets are implemented.
  Final audit fixed stopped replay losing previously attempted failure rows.
- Prior unfinished offline100 work remains: count parameterization, paginated
  contact sheets, `analysis.py`, `checkpoint.py`, benchmark configs. Odd counts use
  balanced pairs plus one seeded random class. No `benchmark.py` runner or full
  100-instance acceptance verification exists; do not claim this milestone done.

## Actual live attempt

`artifacts/real-vision-two-stage`: sandbox network failure, no aggregation attempts.
`artifacts/real-vision-gemini`: planned two original dataset bases b000/b001,36
method-condition rows. First vision request timed out after90s. Read-only model
lookup succeeded; a documented manual review cleared only that transport latch,
preserving the cached failed call without resending it. Next aggregator response
failed citation schema (empty citations with non-null probability); next returned
HTTP503 high demand. Stopped immediately. No quota response and no paid fallback.

Three generation requests: one unknown timeout, one received but invalid aggregator
output, one503. Two attempted aggregation failures;34 not-attempted scheduled rows;
0 valid probabilities,0 resolved extractions,0 completed base comparisons. These
rows are operational failures, not evidence of defense effectiveness. No ten-run.

Historical live code hashes are saved in `code_revision.json`; subsequent resume
fixes changed source hashes, so execution under current code correctly rejects
that historical run. Preserve it; a later service-available run needs an explicit
new replicate or reviewed migration, not silent cache relabeling.

## Verification actually performed this task

- Final `.venv/bin/python -m unittest discover -s tests -v`: **30 tests passed**
  (23 existing +7 vision tests using fake transports only).
- New tests: free-only configuration/429 latch; strict schemas/conflict abstention;
  matched reports/prefix extension/offline replay; interrupted call retention and
  cache tamper rejection; evaluator-label intervention leaves requests unchanged;
  stopped-run denominators; stopped replay preserves attempted failures.
- `python3 -m provenance_pilot` runs; tracked pilot artifacts unchanged.
- Transformation CLI to `/tmp/provenance-transforms-20261030` runs240 evaluations.
  Its manifest and existing transformation manifest verify.
- Audited live25-entry manifest, all36 result statuses, and request allowlist.
  Confirmed credential bytes absent from both saved attempt trees and fixture/
  evaluator keys absent from logged model requests. No secret contents printed.
- Viewed transformation contact sheet: transformed glyphs readable. Existing and
  regenerated signal checks pass through tests/CLI (192 including calibration).
- PDF11 pages: original9 page texts preserved, two appended pages rendered and
  visually inspected; no clipping/overlap. Source PDF unchanged. `git diff --check`
  passes. No commit/push.

## Files and commands

- `docs/real-vision-pilot.md`: frozen design, limitations, execution/resume commands.
- `configs/real-vision.example.json`: free-only, user-confirmed account configuration.
- `artifacts/real-vision-gemini/`: preserved failed live attempt, not successful pilot.
- `output/pdf/562-with-preliminary-status.pdf`: original report plus dated addendum.
- `scripts/build_preliminary_report.py`: rebuild addendum from saved outputs.

```sh
python3 -m provenance_pilot
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m provenance_pilot.transformations --output NEW_EMPTY_DIRECTORY
.venv/bin/python scripts/build_preliminary_report.py
# After service recovery and review; NEW output, first two, no paid fallback:
.venv/bin/python -m provenance_pilot.vision.run --instances 2 --output artifacts/real-vision-next
# Only after successful two-instance review: same directory with --instances 10.
```

System Python lacks Pillow. Ignored `.venv` uses existing bundled Python3.12.14
and Pillow12.3.0; no model or dependency downloads were required. PDF uses bundled
ReportLab/pypdf/Poppler. `tmp/` contains ignored PDF previews/font cache.

## Limits and next steps

Service availability blocks empirical results. Review/resume operationally before
any ten-instance live run. No actual cross-modal model record was successfully
produced in this failed attempt, though injected-transport tests exercise the
implementation. Do not substitute the offline fixture record in a live condition.

Only two synthetic glyphs, shared layouts, trusted ancestry and stipulated
conditional independence; no adversarial prompts or reconciliation model.
Citations do not expose LLM internal grouping, so naive/instruction matching
errors are undefined. Intervals describe synthetic-base variability conditional
on cached responses, not model-sampling uncertainty or broad defense performance.
Do not tune on these cases and call them held-out evidence. After a successful
small pilot, revisit the unfinished100-instance offline benchmark separately.
