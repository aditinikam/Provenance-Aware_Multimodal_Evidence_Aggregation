# Expansion plan — review before scaling

1. Review this pilot and freeze acquisition semantics, truth/input separation, metric denominators, invalid-lineage behavior, and output schemas. Keep the diagnostic control separate from sampled metrics.
2. Add actual raster cards and resizing, JPEG compression, and signal-preserving crops. Record parameters and parent IDs, audit signal preservation, and test copied values are never resampled. Introduce a payload renderer interface alongside the existing worker protocol.
3. Add cross-modal derivatives with inherited roots. Measure extraction accuracy separately from aggregation. Preserve disagreements and use a documented reconciliation policy with explicit abstention; do not discard useful interpretations silently.
4. Add configurable real vision-model adapters implementing the worker interface. Store raw responses separately from trusted metadata. Add schema validation, parsing failures, model/prompt versions, caching, token/cost/latency accounting, and hard spending caps. Evaluate instruction-only and perceptual-matching baselines with real responses; calibrate matching thresholds on disjoint data.
5. Freeze configuration and expand to 100 base instances. Reuse cached worker outputs across methods, randomize report order/worker labels with logged seeds, and use paired bootstrap intervals resampling whole base instances. Keep repeated model trials nested within base instances.
6. Add related views only after specifying their joint likelihood/dependence model. Until then report descriptive behavior without the independence oracle. Multi-root summaries need overlap-aware accounting before inclusion.

Acceptance checks: transformation lineage invariance, no truth leakage, independent positive-control retention, identical-independent false merges, invalid-lineage abstention, extraction versus counting error decomposition, and reproducibility from frozen outputs. Only real-model runs can test the research hypothesis. The offline pilot supplies no empirical evidence of LLM susceptibility or defense efficacy.

## Milestone status — October 28, 2026

Completed offline: stage 2 raster cards, resize/JPEG/crop operations, parameterized ancestry, signal audits and contact sheets; stage 3's synthetic image-to-record ancestry fixture; and an offline pixel-matching baseline calibrated on disjoint roots. This does not complete real extraction or reconciliation. The experiment remains ten base instances, with calibration and constructed controls reported separately.

Review `artifacts/transformations/` and README's extraction boundary and matching limitations next. Real-model adapters, empirical instruction-only comparisons, 100-instance scaling, uncertainty estimates, related views, and multi-root aggregation remain deferred until separately requested. Preserve the original offline pilot and frozen calibration/evaluation separation when proceeding.
