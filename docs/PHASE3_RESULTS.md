# Phase 3 experimental results

Production ranking unchanged. No policy or similarity score verifies physical identity.

Coverage: `{"development": {"images": 7, "physical_instances": 1, "categories": [], "product_models_with_multiple_units": 0, "capture_values": {}, "no_match_queries": 3, "multi_view_queries": 0, "unknown_instance_images": 4}, "independent": {"images": 0, "physical_instances": 0, "categories": [], "product_models_with_multiple_units": 0, "capture_values": {}, "no_match_queries": 0, "multi_view_queries": 0, "unknown_instance_images": 0}}`

All development numbers below are tuning observations. Independent results are stored separately; absent data means inconclusive.

| Recipe / CLIP gate policy | Recall@1 | Recall@5 | MRR |
|---|---:|---:|---:|
| full_frame / original | 0.3333333333333333 | 1.0 | 0.5 |
| full_frame / category_as_annotation | 0.3333333333333333 | 1.0 | 0.5 |
| full_frame / retain_uncertain | 0.3333333333333333 | 1.0 | 0.5 |
| manual_crop / original | 0.3333333333333333 | 0.3333333333333333 | 0.3333333333333333 |
| manual_crop / category_as_annotation | 1.0 | 1.0 | 1.0 |
| manual_crop / retain_uncertain | 1.0 | 1.0 | 1.0 |

## Model and fusion observations

CLIP coefficient 1 uses CLIP; 0 uses DINOv2. Interior coefficients require both models. Selection maximizes development MRR; ties prefer single models, zero metadata contribution, single views, then CLIP. Coarse grids are experimental search spaces, not deployed weights.

| Recipe | CLIP coefficient | Views | Metadata coefficient | Recall@1 | MRR |
|---|---:|---|---:|---:|---:|
| full_frame | 1.0 | single | 0.0 | 0.3333333333333333 | 0.5 |
| full_frame | 0.0 | single | 0.0 | 0.6666666666666666 | 0.8333333333333334 |
| full_frame | 0.25 | single | 0.0 | 0.3333333333333333 | 0.6666666666666666 |
| full_frame | 0.5 | single | 0.0 | 0.3333333333333333 | 0.611111111111111 |
| full_frame | 0.75 | single | 0.0 | 0.3333333333333333 | 0.611111111111111 |
| manual_crop | 1.0 | single | 0.0 | 1.0 | 1.0 |
| manual_crop | 0.0 | single | 0.0 | 1.0 | 1.0 |
| manual_crop | 0.25 | single | 0.0 | 1.0 | 1.0 |
| manual_crop | 0.5 | single | 0.0 | 1.0 | 1.0 |
| manual_crop | 0.75 | single | 0.0 | 1.0 | 1.0 |

full_frame: selected `{'alpha': 0.0, 'aggregation': 'single', 'metadata_weight': 0.0}`. Independent: `{'status': 'inconclusive', 'reason': 'Independent queries or required complete annotations/models unavailable.'}`.
unavailable: no explicitly grouped multi-view queries
unavailable: no informative supplied metadata


manual_crop: selected `{'alpha': 1.0, 'aggregation': 'single', 'metadata_weight': 0.0}`. Independent: `{'status': 'inconclusive', 'reason': 'Independent queries or required complete annotations/models unavailable.'}`.
unavailable: no explicitly grouped multi-view queries
unavailable: no informative supplied metadata

## Gate decisions on positive pairs

| Recipe | Query → candidate | Similarity | Predicted categories | Margins | Gate |
|---|---|---:|---|---|---|
| full_frame | distant-case-present → close-case | 0.6289 | earbuds / earbuds | 0.0141 / 0.0194 | relevant |
| full_frame | query-case-present → close-case | 0.763 | earbuds / earbuds | 0.0106 / 0.0194 | relevant |
| full_frame | close-case-present → distant-case | 0.6289 | earbuds / earbuds | 0.0194 / 0.0141 | relevant |
| manual_crop | distant-case-present → close-case | 0.7743 | charger / earbuds | 0.0009 / 0.0125 | uncertain |
| manual_crop | query-case-present → close-case | 0.7746 | earbuds / earbuds | 0.0081 / 0.0125 | relevant |
| manual_crop | close-case-present → distant-case | 0.7743 | earbuds / charger | 0.0125 / 0.0009 | uncertain |

## CPU measurements

Preparation and encoding exclude decode and model loading; one pass per image, two native threads, sequential inference. Hybrid costs require both encoders; scoring-only time is in JSON. Peak memory is combined process residency, not per-model memory.

Peak process memory: 450.0 MiB.

clip: `{"version": "ca64be06ab5e745807097ec1054476ec30f70e8e8f157e098a3ba8d7906bc61a", "loading_ms": 5150.427100015804, "timing": {"full_frame/development": {"images": 7, "mean_prepare_encode_ms": 226.76304285414517, "p95_prepare_encode_ms": 292.8916400298476}, "full_frame/independent": {"images": 0, "mean_prepare_encode_ms": null, "p95_prepare_encode_ms": null}, "manual_crop/development": {"images": 7, "mean_prepare_encode_ms": 189.59519998835665, "p95_prepare_encode_ms": 219.75034001516175}, "manual_crop/independent": {"images": 0, "mean_prepare_encode_ms": null, "p95_prepare_encode_ms": null}}}`

dinov2: `{"version": "837cc156f12e7538b547a93170850d9c1d6168af58842ad0e342efb5530a1d79", "loading_ms": 753.0240999767557, "timing": {"full_frame/development": {"images": 7, "mean_prepare_encode_ms": 316.41912859465396, "p95_prepare_encode_ms": 389.6406699903309}, "full_frame/independent": {"images": 0, "mean_prepare_encode_ms": null, "p95_prepare_encode_ms": null}, "manual_crop/development": {"images": 7, "mean_prepare_encode_ms": 268.9235571638814, "p95_prepare_encode_ms": 296.9534199917689}, "manual_crop/independent": {"images": 0, "mean_prepare_encode_ms": null, "p95_prepare_encode_ms": null}}}`

Local diagnostics: 14 distinct pairs, 0 with geometric inliers. No local-feature reranker enabled.

Raw scores, every gate decision, condition slices, fitted threshold false positives/negatives, source/model/manifest hashes and frozen independent metrics are in the JSON. Threshold fitting is development only, including reject-all outcomes; no-match rejection is not independently validated.

## Verification and files changed

69 Python regression tests passed outside the sandbox; the existing sandbox HTTP/thread hang was interrupted. Frontend crop-state, async error recovery and side-by-side tests passed. A live browser search and comparison dialog were verified, including narrow-screen layout.

New: evaluation/catalog.py, evaluation/phase3.py, tests/test_phase3.py, docs/PHASE3.md, docs/PHASE3_DATASET.md and this report. Updated: evaluation/dataset.py, evaluation/pipeline.py, evaluation/metrics.py, frontend/gallery.html, tests/frontend_selection.cjs and README.md. Backend production ranking and models were unchanged.

See [interpretation and production recommendations](PHASE3.md) and [real-photo collection requirements](PHASE3_DATASET.md).
