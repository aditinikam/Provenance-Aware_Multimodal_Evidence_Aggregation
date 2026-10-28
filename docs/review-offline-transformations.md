# Offline transformation implementation review

Reviewed October 28, 2026 on `offline-multimodal-transformations`, starting from commit `84e6eab`. Read AGENTS.md/project.md and inspected implementation, tests, configuration, and saved artifacts. This review does not run 100 instances or use a real model.

## Findings fixed

1. **Method failures were lost when scoring aborted.** A malformed raster raised out of perceptual matching. Scoring now retains an explicit `failure:` result with no probability/approval. Pillow error text is normalized to avoid memory-address-dependent output. A modality/report length mismatch is rejected explicitly. Unexpected exceptions still fail the run rather than being hidden.
2. **Interpretation abstention erased successful grouping.** Hash/lineage conflict handling returned an empty grouping, preventing correct matching-error accounting. Conflicts now retain their grouping even though the probability is null. If a full partition was never produced (e.g. decode failure or invalid ancestry), matching errors are undefined instead of inventing false splits or zero false merges. Summaries expose evaluated versus attempted pair denominators and grouping coverage.
3. **Oracle means were conditioned on method success.** The summary averaged oracle probabilities only over valid method outputs. It now includes every attempted case, including abstentions and failures. Decision-rate denominators continue to include all eligible attempts. Probability/error/Brier means remain conditional on available probabilities and expose coverage.
4. **Generation failures left ambiguous partial directories.** Runs now write `run_status.json` with running/complete/failed state. A failed signal check stops generation and records failure; partial artifacts are not a completed benchmark. The success record reports method failures/abstentions and check counts. These are distinguished from method-level failures counted in completed-run summaries.

The calibration/evaluation overlap guard now raises explicitly rather than relying on an assertion that optimized Python can disable.

Five new regression tests cover conflict-group accounting, corrupt-image failure accounting and deterministic error records, all-attempt oracle/decision denominators, failed-generation status, and evaluator-label changes that must not alter worker inputs or method estimates. Existing tests continue to cover invalid ancestry, multi-root rejection, transformation validity, exact bytes, calibration disjointness, and reproduction.

## Actual verification

| Check | Result |
|---|---|
| Original `python3 -m provenance_pilot` | Runs; 90 rows; tracked artifacts unchanged |
| Original tests under system Python | 8 passed |
| Full `.venv/bin/python -m unittest discover -s tests -v` | 23 passed |
| Transformation CLI in fresh temporary directory | 240 rows, ten base instances, complete run |
| Saved artifact audit | Payload hashes, all provenance nodes, 169 worker reports, 144 evaluation/control pixel checks, 240 oracle/result rows, and 24 summary decision denominators verified |
| Calibration | Recomputed from saved raster bytes/ancestry: threshold 0.006352124183006534; 12 roots disjoint from evaluation/control roots |
| Calibration signal checks | 48 passed in generated runs/tests; 192 total with evaluation/control checks |
| Oracle | Independently checked using odds `3 ** sum(2*x-1)` over assigned unique acquisitions |
| Output reproduction | All files byte-identical across two fresh runs in the test environment |
| Updated output manifest | All 388 entries verified, with no unlisted files |
| Contact sheets | Main/control sheets visually inspected; glyphs readable; review changes leave their PNG bytes unchanged |
| Regeneration comparison | Every previously stored result field retains its value; only accounting fields/status artifact were added |

Inputs and fixture readings were traced through `fixture_report` and `score`. An intervention test changes only Y/evaluator acquisition annotations: worker call arguments, exported worker inputs, and all method probabilities remain unchanged, while the oracle changes. Observed fixture readings legitimately enter worker inputs; hidden states, oracle posteriors, and signal-check outputs do not.

Distinct roots remain distinct in the registry, oracle, and trusted-lineage method even when bytes match. Hash/perceptual merging in the identical-independent control is an intentional measured baseline error, not a change to acquisition identity. No independence is inferred from visual resemblance.

## Remaining methodological limits

- Mock claims copy known observations and do not perceive pixels. The synthetic structured record is not OCR/captioning. These runs establish software behavior only.
- Pixel validation checks seven known segment centers, ROI bounds, and minimum resolution; it is not full glyph reconstruction or a general readability guarantee. Human review covered the displayed contact sheets; not every calibration rendering was individually inspected by eye.
- Calibration roots are separate, but templates/appearances are not held out. Two glyphs and repeated layouts make independent byte collisions frequent. Calibration also includes nuisance styles whereas sampled evaluation uses the base style. The threshold should not be interpreted as generalizing to natural images.
- Perceptual matching is a simple full-frame color metric, is crop-sensitive, and cannot resolve image-to-JSON relationships. Pairwise threshold calibration and connected-component inference have different objectives due to transitive matches.
- Trusted acquisition IDs establish computational ancestry, not real-world conditional independence. Signal errors, forged metadata, correlated views, and useful disagreement/reconciliation remain outside this fixture.
- Generation failures deliberately abort a run rather than dropping cases. Method failures remain in decision denominators. A future benchmark must preserve that distinction and never pool partial runs into successful results.
- Ten balanced base instances and deterministic workers do not support statistical or real-model claims. Calibration/root splits, thresholds, metric definitions, and any uncertainty plan must be frozen before interpreting a larger run.

## Readiness decision

**The reviewed ten-instance implementation is a verified foundation for a 100-instance offline milestone, but it is not yet runnable as that benchmark unchanged.** `validate_settings` deliberately rejects instance counts other than ten, and contact-sheet construction uses ten rows. The next authorized milestone should parameterize those limits, test full output coverage for the requested size (including paginated sheets), and freeze the larger-run design without tuning on its evaluation outcomes. Keep controls/calibration out of the evaluation population. A 100-instance run would still be a software benchmark, not an LLM study.

No scaling, real-model integration, commit, push, or publication was performed during this review.
