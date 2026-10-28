# Reference inspection and attribution

Inspected October 28, 2026. These are separate works, not a repository/paper implementation pair. No external source code, prompts, datasets, figures, or frozen model outputs were copied into this project. Implementation is original. No source license is silently applied to the user's original project.

## Marc Bara: Epistemic Sybil Resistance

[Repository](https://github.com/marcbara/epistemic-sybil-resistance), [aggregation source](https://github.com/marcbara/epistemic-sybil-resistance/blob/master/src/aggregate.py), and [reproducibility notes](https://github.com/marcbara/epistemic-sybil-resistance/blob/master/REPRODUCIBILITY.md) were inspected.

Its aggregators use Gaussian updates, including per-root precision that accounts for extraction noise; the optional gamma variant models correlated extraction. Its content baseline clusters rationale embeddings. We reuse the conceptual separation of ancestry from similarity, not those formulas. Here, perfect mock extraction permits one binary reading per root.

Its reproducibility practices separate calibration from evaluation and frozen-output analysis from live collection. We adapt configuration capture, JSONL outputs, deterministic evaluation, and invariant tests. We do not reproduce its experiments.

[Code license](https://github.com/marcbara/epistemic-sybil-resistance/blob/master/LICENSE-CODE): MIT, copyright 2026 Marc Bara. [Experimental-material license](https://github.com/marcbara/epistemic-sybil-resistance/blob/master/LICENSE-DATA): CC BY 4.0. Future copying must retain applicable notices and attribution. No vendored materials currently require license redistribution.

## Jianxin Gao et al.: Copies or Sources?

[Copies or Sources? Measuring How LLM Aggregators Count Restated Evidence in Multi-Agent Systems](https://arxiv.org/html/2610.06192v1), arXiv:2610.06192v1, was inspected independently.

Sections 2–3 define an oracle over distinct readings and direction-normalized effective evidence `a*logit(p)/log(q/(1-q))`; copy weight is `(mean effective evidence - 1)/(m-1)`. Controls include Single, Copies, Pointers, Padding, Independent, dose changes, and opposing readings. Interventions include a source-counting declaration, extraction of distinct readings, and protocol references instead of restatements.

We adapt the oracle and Single/Copies/Independent comparison. Our fixed one-sided approval threshold differs from the paper's cost-based commit/query policy. We implement only programmed aggregation fixtures; declaration/extraction interventions require real-model evaluation later. The empirical contribution remains image transformations and cross-modal derivatives, not source counting itself.

The displayed paper license is CC BY-NC-ND 4.0. We link and paraphrase methodological ideas; no paper text, figures, or adapted paper artifact is distributed.

## Supplied project report

Read all pages of `/Users/aditi/Downloads/562.pdf`. The report describes a broader future vision-model study, including reconciliation and 100-instance evaluation. The explicit user request narrows the immediate milestone to an offline ten-instance pilot. No material design contradiction requires resolution: prior, reliability, threshold, pairing, trusted lineage, and core decision-rate denominators align. Balanced sampling follows the report. Model access, crop tests, timing/cost evaluation, and empirical conclusions remain future work.
