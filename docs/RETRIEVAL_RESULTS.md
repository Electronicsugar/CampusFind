# Retrieval evaluation results

**Generalization result: inconclusive.** Development observations are not independent accuracy evidence.

Development coverage: 7 images, 3 positive queries, 3 no-match queries, 1 known positive physical instance(s).
Independent coverage: 0 queries.

Recall@k is the fraction of labeled positive images retrieved in the first k results, averaged over positive queries. MRR includes zero for missed positives. Current app suggestions have no identity-acceptance policy; proposal rejection is reported separately from thresholded acceptance.

| Model / recipe | Routed R@1 | Routed R@5 | Routed MRR | Raw R@1 | Raw MRR | Wrong routed top-1 / positive | No-match queries with proposals | Prepare + encode ms/image | Repeat ms/image |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clip / full_frame | 0.333 | 1.000 | 0.500 | 0.333 | 0.500 | 2 / 3 | 3 / 3 | 159.79 | 15.43 |
| clip / manual_crop | 0.333 | 0.333 | 0.333 | 1.000 | 1.000 | 1 / 3 | 2 / 3 | 161.55 | 9.10 |
| clip / reviewed_detector | 0.667 | 1.000 | 0.833 | 0.667 | 0.833 | 1 / 3 | 3 / 3 | 159.52 | 9.98 |
| clip / detector_top | 0.333 | 0.333 | 0.333 | 0.333 | 0.500 | 1 / 3 | 2 / 3 | 156.17 | 13.11 |
| clip / square_pad | 0.000 | 0.333 | 0.167 | 0.333 | 0.667 | 2 / 3 | 2 / 3 | 174.06 | 19.96 |
| clip / fusion_global_0 | 0.333 | 0.333 | 0.333 | 1.000 | 1.000 | 1 / 3 | 2 / 3 | 336.25 | 25.68 |
| clip / fusion_global_0.25 | 0.333 | 0.333 | 0.333 | 1.000 | 1.000 | 1 / 3 | 2 / 3 | 336.25 | 25.68 |
| clip / fusion_global_0.5 | 0.333 | 0.333 | 0.333 | 0.667 | 0.833 | 1 / 3 | 2 / 3 | 336.25 | 25.68 |
| clip / fusion_global_0.75 | 0.333 | 0.333 | 0.333 | 0.667 | 0.833 | 1 / 3 | 2 / 3 | 336.25 | 25.68 |
| clip / fusion_global_1 | 0.333 | 0.333 | 0.333 | 0.333 | 0.500 | 1 / 3 | 2 / 3 | 336.25 | 25.68 |
| dinov2 / full_frame | 0.667 | 1.000 | 0.833 | 0.667 | 0.833 | 1 / 3 | 3 / 3 | 238.97 | 7.71 |
| dinov2 / manual_crop | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0 / 3 | 3 / 3 | 196.73 | 6.99 |
| dinov2 / reviewed_detector | 0.667 | 1.000 | 0.833 | 0.667 | 0.833 | 1 / 3 | 3 / 3 | 247.01 | 7.49 |
| dinov2 / detector_top | 0.333 | 1.000 | 0.511 | 0.333 | 0.511 | 2 / 3 | 3 / 3 | 247.19 | 8.82 |
| dinov2 / square_pad | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0 / 3 | 3 / 3 | 246.66 | 20.02 |
| dinov2 / fusion_global_0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0 / 3 | 3 / 3 | 427.97 | 20.72 |
| dinov2 / fusion_global_0.25 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0 / 3 | 3 / 3 | 427.97 | 20.72 |
| dinov2 / fusion_global_0.5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0 / 3 | 3 / 3 | 427.97 | 20.72 |
| dinov2 / fusion_global_0.75 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0 / 3 | 3 / 3 | 427.97 | 20.72 |
| dinov2 / fusion_global_1 | 0.667 | 1.000 | 0.833 | 0.667 | 0.833 | 1 / 3 | 3 / 3 | 427.97 | 20.72 |

clip: model loading 4284.6 ms; peak worker process working set 470.4 MiB.
dinov2: model loading 700.5 ms; peak worker process working set 311.3 MiB.

DINOv2 has no text/category classifier here: its routed and raw lists are identical. Compare raw columns between encoders; CLIP routed columns additionally include the existing category policy.

## Development-only abstention fit

Optimistic fitted observations, not validation. Thresholds maximize balanced correct acceptance and no-match rejection on development; conservative ties prefer rejection. Empty independent data means no validated false-positive or rejection rate.

| Model / recipe | Fitted threshold | False accepted queries | No-match false-positive rate | No-match rejection | Correct acceptance recall |
|---|---:|---:|---:|---:|---:|
| clip / full_frame | 0.75415 | 0 | 0.000 | 1.000 | 0.333 |
| clip / manual_crop | 0.76275 | 0 | 0.000 | 1.000 | 0.333 |
| clip / reviewed_detector | 0.78020 | 0 | 0.000 | 1.000 | 0.667 |
| clip / detector_top | 0.73855 | 0 | 0.000 | 1.000 | 0.333 |
| clip / square_pad | 0.78550 | 0 | 0.000 | 1.000 | 0.000 |
| clip / fusion_global_0 | 0.76275 | 0 | 0.000 | 1.000 | 0.333 |
| clip / fusion_global_0.25 | 0.76060 | 0 | 0.000 | 1.000 | 0.333 |
| clip / fusion_global_0.5 | 0.75845 | 0 | 0.000 | 1.000 | 0.333 |
| clip / fusion_global_0.75 | 0.75630 | 0 | 0.000 | 1.000 | 0.333 |
| clip / fusion_global_1 | 0.75415 | 0 | 0.000 | 1.000 | 0.333 |
| dinov2 / full_frame | 0.67830 | 0 | 0.000 | 1.000 | 0.333 |
| dinov2 / manual_crop | 0.63630 | 0 | 0.000 | 1.000 | 1.000 |
| dinov2 / reviewed_detector | 0.61805 | 0 | 0.000 | 1.000 | 0.667 |
| dinov2 / detector_top | 0.56665 | 0 | 0.000 | 1.000 | 0.333 |
| dinov2 / square_pad | 0.69150 | 0 | 0.000 | 1.000 | 1.000 |
| dinov2 / fusion_global_0 | 0.63630 | 0 | 0.000 | 1.000 | 1.000 |
| dinov2 / fusion_global_0.25 | 0.61490 | 0 | 0.000 | 1.000 | 1.000 |
| dinov2 / fusion_global_0.5 | 0.57295 | 1 | 0.333 | 0.667 | 1.000 |
| dinov2 / fusion_global_0.75 | 0.54110 | 1 | 0.333 | 0.667 | 1.000 |
| dinov2 / fusion_global_1 | 0.67830 | 0 | 0.000 | 1.000 | 0.333 |

## Independent evaluation

No independent queries: Recall@1, Recall@5, MRR, false-positive rate and no-match rejection are unavailable. Development-fitted thresholds have no independent validation.

## Interpretation and reproducibility

These recipes are offline. Live cropping, CLIP preprocessing, category routing, and ranking weights are unchanged. Detector-top is deliberately unreviewed and is not the live assisted-selection behavior. Reviewed-detector uses explicit development review records and documented manual fallback.

Thresholds and fusion coefficients are fitted on development only. Their development acceptance metrics, frozen independent results, raw unfiltered embedding rankings, candidate relevance labels and local-feature diagnostics are in the JSON report. No threshold or coefficient is installed in the website.

Missing evidence: same-model different physical items, independent instances, broader categories and independently reviewed labels. Three views of one object are correlated observations. Product lookalikes are different models, not same-model hard negatives.

Manifest fingerprints: development `7904d754e20ef387f30484850d58dc032ada7096f07e59d0409dfdadda84a720`, independent `b8a11661ce0f66d5fc60f8528e7db9efd690dbc5455851b5fb5722096bf8f2d8`.

Platform: Windows-11-10.0.26200-SP0; Python 3.14.5; CPU provider, two native inference threads. Timings include region preparation and encoding, exclude upload/decode, and are subject to process/cache warmup. Repeated measurements use identical pixels. Model processes are isolated; cached native inference is bounded separately in the application.

## Implemented efficiency improvement

Changed components: `evaluation/dataset.py`, `metrics.py`, `pipeline.py`,
`encoders.py`, `run.py` and `verify_cache.py`; `backend/embedding_cache.py`,
`backend/semantic.py` and `backend/main.py`; `scripts/download_dinov2.py`;
`data/retrieval-development.json` and `data/retrieval-independent.json`;
`tests/test_embedding_cache.py` and `tests/test_retrieval_evaluation.py`;
README, roadmap and evaluation documentation. Frontend files and dependency
requirements were preserved. Raw generated reports and downloaded weights remain
local ignored artifacts.

The full-handler cache check observed 1109.7 ms cold versus 680.3 ms averaged over three warm requests, excluding initial model loading. Responses were exactly identical except elapsed time. Six initial native inferences served all requests; the warm requests added zero inferences and 18 cache hits. This is a local timing observation, not an accuracy improvement or a guaranteed service latency.

All ten CLIP experiment recipes were also compared with the saved pre-cache run: every candidate score, relevance label and ordering was identical. The cache is the only production retrieval optimization enabled.

## Local-feature evidence and validation

SIFT geometric verification produced zero inliers on all 14 unique development pairs, including the two distinct same-instance view pairs. It provided no useful ranking discrimination here. No local reranking or extra matcher download was enabled.

The full regression suite passed with 56 tests; frontend selection/acceptance and asynchronous failure-recovery checks also passed. The independent split contains no cases, so accuracy, acceptance thresholds and no-match rejection remain unvalidated beyond development.
