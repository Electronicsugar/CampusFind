# Phase 3: reliability experiments

The application retains its existing CLIP ranking, category gates, crops, cache, upload validation and graceful model-loading errors. No default model, weights or threshold changed. No downloads, authentication, database, messaging or claims were added.

## Implemented

- Backward-compatible dataset validation adds physical-unit provenance, product-model metadata, capture conditions and explicit multi-view groups. `evaluation.catalog` creates empty datasets and audits coverage without loading models. See [dataset instructions](PHASE3_DATASET.md).
- `evaluation.phase3` reuses the Phase 2 loader, encoders, preprocessing, gate logic, metrics, threshold fitting and SIFT diagnostics. It compares full-frame and manual-crop CLIP/DINO, three interior hybrid coefficients, explicit mean/max multi-view aggregation and metadata contributions when actual annotations exist. Metadata uses a signed agreement average over supplied category/brand/color/location; missing fields are neutral. Its development-tuned coefficient includes zero. Identity labels and product-model IDs never enter the score.
- Gate diagnostics record query/candidate categories, category margins, non-item margin, alternatives, structure override, visual similarity, relation and decision reason. Original policy, category-as-annotation and retaining-uncertain policies are separate offline comparisons. Category gates are never interpreted as identity acceptance.
- Development selection and frozen independent scoring are separate. Fixed single-model baselines also have independent results. Condition slices preserve explicit denominators. False-negative measurements accompany false positives and rejection.
- The gallery now says “potential matches,” explains the actual visual/category/tie-break signals and explicitly says metadata and distinctive details are unused. Side-by-side crop inspection uses the current selected reference and candidate. Native dialog supports Escape and keyboard focus. Assisted cropping remains unchanged.
- There is no “No reliable match found” claim because no validated rejection policy exists. An empty relevant section is explained as failure of the current category check, not proof that the physical item is absent. All identity outcomes remain unverified.

## Reproduce

```powershell
.venv\Scripts\python.exe -m evaluation.catalog
.venv\Scripts\python.exe -m evaluation.phase3 --output reports/phase3.json
.venv\Scripts\python.exe -m pytest -q
node tests/frontend_selection.cjs
```

Models load locally only. Missing optional DINOv2 leaves CLIP experiments available. CPU encoding is serial with the existing two native threads; embedding caches remain bounded. Timing includes prepare+encode, excludes image decode, and reports mean/p95 and loading separately. Scoring time excludes encoding. Peak memory is combined process residency, including CLIP's retained singleton; it is not a claim about each model's standalone memory. Model/source/manifest fingerprints are saved. No heavy local matcher is added because current SIFT evidence is uninformative.

Detailed numeric output: [measured report](PHASE3_RESULTS.md). Machine-readable local output: `reports/phase3.json`. Numeric development results are correlated observations of one user-reported physical object. Synthetic tests exercise logic only and are never included in accuracy metrics.

## Interpretation and production recommendation

The distant manual crop is predicted as charger (margin 0.0009), while the close crop is earbuds (margin 0.0125). Their visual similarity is 0.7743. Since the labels disagree but neither margin reaches the existing 0.025 confidence margin, the existing rule falls through to uncertain. Visual similarity above 0.70 prevents one exclusion branch but does not make a mismatched pair relevant. It is therefore possible to be the strongest visual result and be absent from the relevant section. Both directions of this same pair account for the two affected positive queries; they are not two independent physical units. No hardcoded label exception or new cutoff was introduced.

On the current three positive queries, retaining uncertain candidates and using categories as annotations both recover cropped CLIP Recall@1 from 1/3 to 3/3. These policies also retain more potential false matches; independent absent-target data is required before promotion. Full-frame DINOv2 gives 2/3 versus CLIP's 1/3. The tested interior hybrid coefficients give 1/3 full-frame; all cropped endpoints/interior hybrids give 3/3. Cropped fusion therefore offers no observed benefit for its additional encoding cost. The coarse grid does not establish that every possible hybrid is inferior.

All 14 SIFT pairs still have zero geometric inliers, including positive pairs. No local-feature evidence supports reranking these smooth cases. This does not establish that scratches/stickers cannot help: collect real cross-view visible details and model-matched negatives before selecting a local matcher.

Multi-view and metadata paths have regression coverage but are explicitly **not empirically evaluated**: existing manifests have no explicit view groups or supplied retrieval metadata. Their potential benefit is unknown. No held-out photographs exist, so generalization, false-positive control, calibration and no-match reliability remain inconclusive. Keep production ranking unchanged. The most useful next experiment is category-as-annotation versus the current gate on independently documented same-model units, including paired absent galleries.
