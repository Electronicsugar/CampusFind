# Phase VI recognition evaluation — 28 October 2026

**Recommendation: retain the existing production ranking and category gates.**
The experimental infrastructure is implemented and development experiments ran
with the installed CLIP, DINOv2 and NanoDet models. No independently validated
accuracy improvement is established. No ownership decisions, production scores,
database schemas, worker behavior or crop confirmation behavior were changed.

## Dataset coverage

| Evidence | Available |
| --- | ---: |
| Development photographs | 7 |
| Known physical units | 1 |
| Positive queries | 3 |
| Absent-target queries | 3 |
| Negative images with unknown physical-unit IDs | 4 |
| Labeled same-model different-unit negative pairs | 0 |
| Explicit multi-photo report queries | 0 |
| Reviewed segmentation masks | 0 |
| Independent photographs / queries | 0 / 0 |

The three views concern one user-reported physical earbud case; that identity was
not independently verified. Product lookalikes are different models and must not
be described as same-model physical-unit negatives. Present/absent variants reuse
the same images, so six queries do not constitute six independent observations.
No photographs, physical identities or new view groups were invented. Existing
private photos and identity labels were not edited.

An empty schema-3 collection is prepared under `.local/phase6-collection/`, with
separate development/independent manifests and photo directories. It contains no
new images. Follow [the labeling guide](PHASE6_DATASET.md) to populate it.

## Implementation and audit

The [recognition audit](PHASE6_AUDIT.md) traces preprocessing, crop coordinates,
category routing, caching, candidate selection and background jobs.

New implementation:

- `evaluation/integrity.py`: strict optional schema-3 report/capture/product labels,
  provenance split checks and hash-bound human review of suspected perceptual
  duplicates. Unresolved leakage and unknown held-out instance IDs block scoring.
- `evaluation/report_retrieval.py`: explicitly enabled offline report ranking,
  deduplicated report IDs, single/max/mean/bidirectional-best view aggregation,
  joint hybrid image-pair scores, strongest supporting pair and disagreement
  ranges. An isolated SQLite cache uses content/model/preprocessing/recipe keys.
- `evaluation/phase6.py`: same-cohort full/manual/padded/reviewed-detector/masked
  transforms, development-only parameter and threshold selection, frozen independent
  evaluation, existing category-gate diagnostics, conditions, CPU timings and hashes.
- `evaluation/metrics.py`: mAP, acceptance precision, explicit known-query rejection
  and wrong accepted known-query counts, preserving previous metric fields.
- `evaluation/dataset.py` and `catalog.py`: backward-compatible schema support and
  empty collection creation/leakage screening.
- `tests/test_phase6.py`: synthetic regression fixtures for infrastructure behavior;
  these fixtures are excluded from all recognition-accuracy evidence.

The feature flag is `--enable-experimental` on the offline command. Omitting it
fails before model loading. The production web app does not expose or install
experimental rankings or thresholds. Existing side-by-side photo inspection stays
available; new report results provide the supporting query/candidate image IDs for
inspection, without claiming local features or identity were verified.

## Baseline and preprocessing comparison

Each row below uses the same three development positive queries and their unchanged
galleries. Raw retrieval is shown separately from CLIP category sections. With one
positive candidate per query here, mAP equals MRR; the code supports multiple positives.

| Preprocessing | Encoder | Recall@1 | Recall@5 | MRR | mAP |
| --- | --- | ---: | ---: | ---: | ---: |
| Full frame | CLIP | 1/3 | 3/3 | 0.500 | 0.500 |
| Full frame | DINOv2 | 2/3 | 3/3 | 0.833 | 0.833 |
| Manual crop | CLIP | 3/3 | 3/3 | 1.000 | 1.000 |
| Manual crop | DINOv2 | 3/3 | 3/3 | 1.000 | 1.000 |
| Crop + square padding | CLIP | 1/3 | 3/3 | 0.667 | 0.667 |
| Crop + square padding | DINOv2 | 3/3 | 3/3 | 1.000 | 1.000 |
| Reviewed NanoDet + explicit fallback | CLIP | 2/3 | 3/3 | 0.833 | 0.833 |
| Reviewed NanoDet + explicit fallback | DINOv2 | 2/3 | 3/3 | 0.833 | 0.833 |

Manual crops look promising on this one unit. Padding is not universally helpful:
it reduces CLIP top-1 retrieval here while DINOv2 remains strong. This is evidence
against assuming preprocessing improvements transfer across encoders. Segmented
images were unavailable because no complete reviewed-mask annotations exist.

Hybrid coefficients 0.25, 0.5 and 0.75 were tested on development, alongside the
single-model endpoints. Full-frame hybrids achieved MRR 0.667, 0.611 and 0.611,
respectively, below DINOv2 alone. Manual-crop hybrids tied both single models at
MRR 1.000. Padded hybrids tied DINOv2 at 1.000. Reviewed-detector hybrids tied
the single models at 0.833. **No hybrid demonstrated a benefit over the best
single encoder on the available queries.** All independent comparisons are inconclusive.

## Category-gate diagnosis

The same distant case is predicted as `earbuds` in the full frame and `charger`
in the manual crop. The manual crop's top-category margin is only 0.000933; the
close case remains `earbuds` with margin 0.012470. Their visual similarity is
0.7743. The gate routes both directions of this pair to `uncertain` because labels
disagree with ambiguous margins. This is a prompt-category decision, not a measured
probability that the physical object differs.

| CLIP recipe | Original relevant-section R@1 | Category annotation R@1 | Retain uncertain R@1 |
| --- | ---: | ---: | ---: |
| Full frame | 1/3 | 1/3 | 1/3 |
| Manual crop | 1/3 | 3/3 | 3/3 |
| Square padding | 0/3 | 1/3 | 1/3 |
| Reviewed detector | 2/3 | 2/3 | 2/3 |

The original-policy metric treats only `relevant` candidates as proposals; the
application still lets users inspect uncertain/excluded sections. Removing a
candidate from this metric is therefore not deletion from the actual application.
Annotation-only ranks all candidates by visual similarity. Retain-uncertain merges
relevant and uncertain candidates while retaining non-item exclusions.

Category consistency and visual identity retrieval are separate concerns. Full-frame
CLIP groups multiple photos as earbuds yet ranks the white
lookalike above the true case on two queries. Conversely, ambiguous category labels
can accompany correct visual retrieval. No category calibration or general category
accuracy estimate is possible without broader labeled categories and hard negatives.
The raw JSON retains all margins, alternatives, reasons and pair decisions.

## Detector localization is a separate experiment

NanoDet was rerun on the existing detection smoke manifest with its approximate
development boxes: **4/6 object images** had a proposal at IoU >=0.5. The single
negative chart also received a proposal (**1/1**). Mean inference was **18.95 ms**,
model load **273.24 ms**, peak isolated process memory **303.15 MiB** (two timing
repetitions per image after warmup).

The distant case region has high overlap but is labeled `mouse`; the close/query
cases are labeled `cell phone`. The white case's best overlap is approximately
0.326, and the black case has no proposals. Existing human review accepts selected
regions, uses manual fallback for white/black cases and full frame for the chart.
These results do not establish category correctness or automatic crop safety.

The new strict runner intentionally reports localization as unannotated for the
retrieval manifest itself: manual crops are not silently converted into independent
ground truth. The separate smoke measurements above retain their original annotation
limitations. No extra Grounding DINO download or detector replacement was justified
by the limited evidence; human crop review and manual correction remain necessary.

## No-match and uncertainty

Without a fitted threshold, raw visual ranking proposes a candidate for all three
absent-target queries. That is a ranked suggestion, not an acceptance decision.
The existing development-only balanced objective fits these illustrative policies:

| Recipe / development-selected model | Threshold | Correct accepted positives | False accepted queries | Rejected absent queries | Rejected known queries |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full frame / DINOv2 | 0.678338 | 1/3 | 0 | 3/3 | 2/3 |
| Manual crop / CLIP | 0.762616 | 3/3 | 0 | 3/3 | 0/3 |
| Square padding / DINOv2 | 0.691521 | 3/3 | 0 | 3/3 | 0/3 |
| Reviewed detector / CLIP | 0.780201 | 2/3 | 0 | 3/3 | 1/3 |

Precision among accepted top results is 1.0 on these **same fitting examples**.
This is optimistic tuning performance, not validation. Same-model negatives and
independent absent-target queries are unavailable; their false acceptance/rejection
rates are **unknown**. Threshold fitting can also choose reject-all: padded CLIP
does so under this objective, with undefined precision and all known queries rejected.
High rejection alone must not be described as a good matcher.

Thresholds stay in experimental output only. No new “No reliable match” claim,
identity percentage or automatic ownership approval was installed.

## Multi-photo and fine-grained matching

Report-level infrastructure is implemented but its accuracy is **inconclusive**:
the existing manifest has no independently labeled multi-photo report groups.
Synthetic tests show report deduplication, stable ties, supporting image pairs,
contradictory views and the distinction between max, mean and coverage aggregation.
They do not establish which aggregation works on real items.

The new hybrid combines CLIP and DINOv2 at each pair before aggregating. A regression
guards against adding two models' maxima from different image pairs and presenting
that inflated score as jointly supported evidence. No view is dropped using an
unvalidated quality threshold; score ranges expose disagreement for investigation.
Empty or self-overlapping view groups are rejected.

SIFT was not rerun: the prior 14-pair diagnostic found no geometric inliers, and no
new detail-bearing photographs or changed hypothesis were available. Distinctive-part
embeddings and geometric reranking remain unsupported, not silently substituted by
global similarity. Existing optional metadata experiments remain available in the
Phase 3 harness; current images lack informative supplied metadata for tuning them.
Identical-looking, unmarked products may be impossible to distinguish from images
alone. Private ownership evidence and human review remain essential.

## CPU and cache observations

First run had **56 persistent misses, zero hits**. A new process using the same
cache had **56 hits, zero misses**; every ranking, supporting pair and metric was
identical. This verifies descriptor reuse and numerical compatibility, not accuracy.
Cache corruption, changed pixels/model/recipe and restart are covered by regressions.

| Recipe | CLIP first-run median / p95 ms | DINOv2 first-run median / p95 ms | CLIP cached median ms | DINOv2 cached median ms |
| --- | ---: | ---: | ---: | ---: |
| Full frame | 197.67 / 306.69 | 229.87 / 386.25 | 95.22 | 105.37 |
| Manual crop | 167.97 / 303.89 | 201.62 / 317.91 | 80.56 | 103.22 |
| Square padding | 200.82 / 300.48 | 208.95 / 313.53 | 97.54 | 97.44 |
| Reviewed detector | 158.13 / 282.64 | 186.79 / 333.27 | 99.31 | 110.66 |

Each timing includes file decode, preparation, cache access and encoding for seven
images, not upload/network time. Model load was 1,379.93 ms for CLIP and 368.90 ms
for DINOv2. Cold-recipe CPU time ranged 2.234–3.172 seconds for CLIP and 2.531–3.500
seconds for DINOv2. Native inference uses two threads and models run sequentially.
Combined peak process RSS was **456.91 MiB** first run and **449.09 MiB** cached.
Model residency, image arrays and diagnostics are included; this is not incremental
per-model memory. Hybrid inference requires both models.

These are one cold-cache pass and one warm-cache pass on the local Windows/Python
3.14.5 host, with other regression work in progress. They are not controlled latency
distributions or capacity guarantees. Existing encoder RAM caches may reuse identical
transformed pixels across recipes even during a cold persistent-cache run. Cached
timings still include image decoding; they must not be presented as model-only time.

## Representative errors

- Full-frame CLIP ranks `white-case` first for `distant-case-present` and
  `close-case-present`; DINOv2 still makes the latter error. Similar broad product
  appearance can outweigh identity evidence.
- Manual-crop CLIP retrieves the true case first but two positive pairs enter
  uncertain because of `charger`/`earbuds` category disagreement.
- Padded CLIP ranks `white-case` first for distant/query case searches. Preserving
  the entire crop changes the descriptor and does not guarantee a better result.
- Both encoders with reviewed detector crops rank `white-case` first for
  `query-case-present`. Better or accepted localization is not sufficient for
  reliable physical-instance retrieval.

These are development photo IDs, not new labels. Condition-level metrics for the
existing angle/light/background tags are in JSON. There are no reliable category,
textureless-unit or same-model-negative performance estimates yet.

## Validation and reproducibility

Final verification on 28 October: **117 Python tests passed, 3 PostgreSQL-only
tests skipped**, in 23.76 seconds. The separate PostgreSQL platform/pilot suite
had **32 passed** in 28.20 seconds, including concurrency and process-crash checks.
Frontend crop selection/comparison and platform CSRF/busy/error regression scripts
passed. The final two new regressions confirm held-out thresholds remain frozen
and incomplete crop cohorts cannot silently discard images. Manifest and production
source fingerprints matched the experiment records. No UI source, production
backend, database schema or dependency change was needed for this phase.

Exact runs (outputs are retained; use new filenames to repeat):

```powershell
.\.venv\Scripts\python.exe -m evaluation.phase6 --enable-experimental --output reports/phase6-20261028-cold.json
.\.venv\Scripts\python.exe -m evaluation.phase6 --enable-experimental --output reports/phase6-20261028-warm.json
.\.venv\Scripts\python.exe -m scripts.benchmark_detection --manifest data/detection-manifest.json --models nanodet --repeats 2 --output reports/phase6-localization-20261028.json
.\.venv\Scripts\python.exe -m pytest -q
$env:CAMPUSFIND_TEST_POSTGRES='true'
.\.venv\Scripts\python.exe -m pytest tests/test_platform.py tests/test_pilot.py -q
Remove-Item Env:CAMPUSFIND_TEST_POSTGRES
node tests/frontend_selection.cjs
node tests/frontend_app.cjs
```

The first cold run used the default `.local/phase6/descriptors.sqlite`, which did
not previously exist. Use a new `--cache` path to reproduce a cold run today.

Artifacts: [cold JSON](../reports/phase6-20261028-cold.json),
[cold comparison](../reports/phase6-20261028-cold.md),
[warm JSON](../reports/phase6-20261028-warm.json),
[localization JSON](../reports/phase6-localization-20261028.json).
Detailed reports are private local artifacts under the ignored reports directory.
They include model versions, source/manifest fingerprints, every ranking, gate
decision and fitted acceptance outcome. Missing annotations disable the complete
recipe; they do not remove difficult examples to improve metrics.

## Evidence classification and next step

| Classification | Conclusion |
| --- | --- |
| Independently validated recognition improvements | **None** |
| Promising but experimental | Manual object crops; annotation-only/retain-uncertain gate policies; DINOv2 for some framing conditions; report aggregation infrastructure |
| Supported engineering improvements | Schema/leakage validation, explicit abstention metrics, isolated persistent cache, joint-pair hybrid evidence and report deduplication mechanics |
| Unsupported by current evidence | Production hybrid advantage, reliable same-model unit distinction, segmentation benefit, local-feature/part reranking, calibrated no-match behavior or real multi-view improvement |

Collect approximately **30–50 physical units**, with several photographs each,
including multiple units of the same model across categories. Reserve entire units
for held-out testing before tuning. Include independent query/gallery sessions,
angle/light/background/size changes, occlusion, smooth and reflective items, visible
scratches/stickers where present, and absent-target galleries with same-model
negatives. Add explicit multi-photo report groups and reviewed localization/mask
annotations where applicable. The [dataset guide](PHASE6_DATASET.md) defines the
required labels and commands. This collection target enables initial experiments;
it is not sufficient proof of deployment-level reliability by itself.
