# Phase VIII-C evaluation design (preparation only)

Reuse evaluation.phase6, report_retrieval, metrics, catalog and integrity. Read
[Phase VI methodology](../PHASE6_DATASET.md) for recipes, frozen development
selection, threshold fitting and exact metric definitions. VIII-A performs no
recognition scoring, threshold calibration or model downloads.

Freeze dataset_version, manifest/file hashes, gallery order/composition, query
cohort, label provenance and split review. Record encoder file fingerprints,
preprocessing/recipe version, ranking and gate policy, aggregation settings,
experimental thresholds/calibration objective, random seed if used, Python/runtime
versions, CPU/RAM and cold/warm cache state. Version selection boxes and derivative
provenance. Do not mutate held-out data after looking at scores; create a new
held-out cohort if it becomes tuning data. Existing fingerprinted JSON and Markdown
outputs are reused; do not invent a CSV scoring exporter requirement.

Evaluate same physical unit across angles/lighting/background/distance/occlusion;
same-model different-unit hard negatives; different models within category;
different categories; and independently labeled absent-target galleries. Report
counts of instances, models with multiple units, categories, reports, queries,
positive candidates and no-match queries, plus missing annotation coverage.
Compare methods on the same cohort/transforms; report unavailable recipes rather
than silently dropping hard examples. Do not count views as independent objects.

Report Recall@1/5, MRR, mAP, wrong top-1, accepted precision, false acceptance on
absent queries and rejection on known queries with their own explicit denominators
and null for undefined rates. Experimental no-match acceptance requires development
calibration and held-out validation. Raw embedding similarity is not a probability.
Category rejection and retrieval rank need separate diagnostics. Summarize condition
slices, CPU latency/memory and sample limitations. Small/incomplete datasets yield
inconclusive results, not a production policy change. Smooth identical units can
be visually unidentifiable; human ownership review remains necessary.

New wrapper checks supplement existing schema, not replace it; legacy development
manifests remain readable by original tools. Query/gallery identity overlap is
legitimate within a partition; development/independent instance overlap is forbidden.
Product-model overlap is allowed and documented. Reviewer signs custody and
near-duplicate review before independent scoring. Do not use private development
example photos for independent evidence.
