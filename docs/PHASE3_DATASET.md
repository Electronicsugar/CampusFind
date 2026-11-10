# Adding real evaluation photographs

Phase 3 uses the existing Phase 2 manifests and validation. No photographs or identity labels have been invented. `data/retrieval-development.json` still contains the seven old photos; `data/retrieval-independent.json` is still empty. Four old negatives have unknown physical identity. They are not evidence for distinguishing two units of the same model.

## Create and validate a dataset

Run from the repository root, using the virtual environment:

```powershell
.venv\Scripts\python.exe -m evaluation.catalog --init data/phase3
.venv\Scripts\python.exe -m evaluation.catalog --development data/phase3/development.json --independent data/phase3/independent.json
.venv\Scripts\python.exe -m evaluation.phase3 --development data/phase3/development.json --independent data/phase3/independent.json --output reports/phase3-new.json
```

Initialization creates empty manifests and `photos/development/` and `photos/independent/` folders; it refuses an existing directory. It does not create sample evidence. Store photographs under `photos/<split>/<physical-unit-id>/<capture-id>.jpg`. Paths in manifests are repository-root relative (absolute local paths also work). Keep private photos and generated detailed reports out of version control. Reports contain image identifiers and labels, but no embedded images.

Every v2 photo requires `id`, `path`, `instance_id`, and `label_provenance`. Use one stable, globally unique physical-unit ID across all views. Product-model ID is separate: two identical purchased products must have different instance IDs. Identify units from custody/owner records or documented distinguishing marks; never infer ground truth from an encoder's output. Provenance should record annotator, date, evidence, and review status without unnecessary personal information. Do not claim independent review if none occurred.

Optional image fields:

| Field | Meaning |
|---|---|
| `manual_box` | Reviewed normalized `[left,top,right,bottom]`, same coordinate convention as existing crops; `[0,0,1,1]` explicitly means whole image |
| `metadata` | Text or null values for `category`, `brand`, `product_model`, `color`, `location`; missing means unknown |
| `capture` | Recorded conditions such as `angle`, `lighting`, `background`, `object_size`, `occlusion`, `texture`, `session`, `camera`; only observed values |
| `detector_review` | Existing Phase 2 accepted proposal index + frozen box, explicit manual fallback, or full-frame decision |

Do not attach identity IDs, relation labels, or post-search knowledge as retrieval metadata. Use metadata available at search time. Location disagreement is not proof of different identity. A logo often identifies a model, not a physical unit. Mark unknown conditions as null or omit them.

Every query uses the existing fields: unique `id`, representative `image_id`, ordered `gallery_ids`, `positive_ids`, `relations` for every gallery representative, and `conditions` for evaluation slices. Relations are `same_instance`, `lookalike`, or `unrelated`. Empty `positive_ids` means an explicitly reviewed absent-target gallery, not missing annotations. Add `same_model_different_unit`, `partial_occlusion`, `smooth_texture`, `background_change`, `scale_change`, `lighting_change`, or other observed conditions to support stratified metrics. Conditions may overlap; subgroup metrics are correlated and must not be averaged as independent samples.

For multi-view evaluation, add optional `view_ids` to the query and `candidate_views` mapping a gallery representative ID to a list of that item's photograph IDs. Each group includes its representative, has 1–8 unique views, and must describe one documented physical unit. Groups cannot reuse query/candidate photographs. Use exactly one gallery representative per physical unit when grouping; positives and relations refer to those representatives. Group membership must come from a known item record before retrieval, never automatic grouping by ground-truth similarity. Without explicit groups, experiments use single views. The legacy image-level recall metric remains unchanged; grouped experiments measure recall over candidate item representatives.

All new group views must be listed in `images`. Missing crop annotations disable the complete cropped cohort instead of silently dropping hard cases. The same photographs and crops are encoded for CLIP and DINOv2. Mean and maximum pairwise multi-view similarity are experimental alternatives; max pooling can increase false matches as photo count grows. Keep view counts balanced and report group size distributions when collecting data.

## Isolation and collection requirements

Assign physical units to development or independent evaluation **before tuning**. Never put different views of the same unit in both. Exact bytes, decoded pixels, and declared physical-instance overlap are rejected. Lossy near-duplicates and incorrect identity labels still require human audit. Do not tune after looking at held-out results; use a new held-out cohort for the next iteration. Sharing a product model across splits is intentional for the same-model challenge; additionally collect unseen models/categories to assess broader generalization. Report these cohorts separately.

Suggested initial collection target (a planning target, not a statistically sufficient guarantee):

- At least four categories: earbud cases, bottles, wallets/bags, and keys or another textured item.
- At least two product models per category and four independently documented units per model: two units for development and two different units held out. This is 32 physical objects.
- Around eight real photos per unit: front, back, side, oblique, brighter and dimmer lighting, changed background/distant view, and partial occlusion. Include multiple capture sessions. Roughly 256 photos at this starting scale.
- Smooth unmarked units and units with naturally existing scratches, stickers, wear or damage. Include close details and ordinary-distance photos; mark whether a distinctive feature is actually visible in both views.
- For each query, construct both a present gallery and a paired absent gallery removing **all** photos of its physical unit while retaining same-model hard negatives. Include unrelated objects sharing the background.
- Supply optional category/brand/color/location independently of image matching, including unknown, incomplete and contradictory metadata cases.

These are needed for real multi-view, metadata, same-model, occlusion and no-match conclusions. Repeated views of one object cannot substitute for independent units. If two pristine products have no visible distinguishing evidence, the correct product behavior is uncertainty and human inspection.

## Acceptance workflow

`evaluation.phase3` selects CLIP/DINO fusion, view aggregation, and optional metadata contribution on development MRR only. Pure encoders, zero metadata, and single views win equal-performance ties. It then fits the existing development-only acceptance threshold, freezes configuration and threshold, and measures independent results. Fixed CLIP and DINO baselines are evaluated separately with their own frozen development thresholds. Every gate policy also receives a development threshold fit and frozen held-out metrics for diagnosis.

Metrics include Recall@1/5, MRR, wrong top results, no-match false-positive rate and rejection, false accepted queries, and false-negative count/rate. A false negative here means a positive query did not produce a correctly accepted top result, including wrong accepted results. Such a query can count as both a false positive and a false negative. Missing positive/negative denominators yield null, never zero. An optimal development threshold can reject everything: inspect correct acceptance recall as well as rejection rate. Threshold selection over this small dataset is optimistic, not calibrated identity probability.

Before deployment, define acceptable false-acceptance and missed-match costs, then collect enough independent absent queries and physical units to estimate those rates with uncertainty bounds. Paired present/absent queries and repeated views are correlated; use physical-unit/session-level resampling rather than treating every pair as independent. This release does not automatically promote any policy, even if held-out queries are added. A validated acceptance threshold is still insufficient to call physical identity confirmed.
