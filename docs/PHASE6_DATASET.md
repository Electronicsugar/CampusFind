# Phase VI real-photo dataset and experiment guide

Use only consented photographs with human-confirmed physical identities. Keep
photos, masks, annotations, caches and detailed reports private. Neither the
application database nor private claim evidence is an evaluation dataset.

## Create an empty collection

From the project root:

```powershell
.\.venv\Scripts\python.exe -m evaluation.catalog --init .local/phase6-dataset
```

This creates empty schema-3 `development.json` and `independent.json` manifests and
`photos/development/` and `photos/independent/` directories. It creates no photos,
labels or results and refuses to overwrite an existing directory. Legacy schema
1/2 manifests remain readable; `--schema-version 2` creates the older template.

Copy each original consented photograph into its assigned directory. Use anonymous
IDs, not student names. Paths in manifests are relative to the **repository root**,
not to the manifest location. Preserve originals and their labels; make a new
versioned manifest for a reviewed correction.

## Label photos

Every schema-3 photo record needs these fields:

| Field | Meaning |
| --- | --- |
| `id`, `path` | Unique image ID and original file location |
| `instance_id` | Human-verified physical unit; different units must never share an ID |
| `product_model_id` | Product model shared by identical-model units; do not guess unknown models |
| `report_id` | One lost/found photographic report, shared only by that report's views |
| `role` | `query` or `gallery`; use different report IDs for query and gallery captures |
| `capture_session_id` | Capture session ID, shared by bursts from that session |
| `source_asset_id` | Original asset ID, shared by derivatives/re-encodings of one photo |
| `label_provenance` | How physical identity was verified, without personal identifying information |
| `metadata` | `category` required; optional `brand`, `color`, `location`, `product_model` |
| `capture` | Nonempty condition annotations, e.g. angle, lighting, background, scale, occlusion, texture, reflective surface, visible marks |
| `manual_box` | Optional reviewed normalized `[left, top, right, bottom]` crop in the EXIF-oriented image |

Use consistent category/model spelling. Each physical unit must have consistent
model/category labels. Reports must have consistent instance IDs and roles.
Unknown attributes should remain unasserted; collect missing labels before using
the strict benchmark. Existing incomplete development data can stay in its legacy
schema and is explicitly reported as incomplete.

Capture conditions should describe observations rather than inferred identity.
Use, for example, `"occlusion":"partial"`, not an invented numerical severity.
Keep acquisition conditions and query-level challenge labels consistent across
the two splits. Product model IDs are evaluation labels, not retrieval features.

## Define a query and its gallery

Each query record uses the existing harness fields:

- `id`: unique query ID.
- `image_id`: representative query photograph.
- `view_ids`: one to eight query-report photo IDs including the representative.
- `gallery_ids`: one representative photograph per candidate report, in a fixed
  order that also provides the declared tie break.
- `candidate_views`: mapping from each gallery representative to its one-to-eight
  report photographs, including that representative. Omission means one photo.
- `positive_ids`: gallery representatives of the same verified physical unit;
  an empty array explicitly defines an absent-target query.
- `relations`: a label for **every** gallery representative: `same_instance`,
  `lookalike`, or `unrelated`. Do not derive lookalike labels from model scores.
- `conditions`: optional challenge tags such as `view_angle` or `no_match`.

Same-instance relations must exactly match positive IDs and physical-instance
labels. Different units of the same model are negatives. Query and gallery groups
cannot reuse photographs. Grouping is supplied by humans, never inferred from
identity labels by the ranking algorithm. If multiple gallery photos depict the
same candidate unit, group them under one representative.

Create paired present/absent scenarios by removing all same-instance candidate
reports for the absent scenario. Preserve hard negatives. These paired scenarios
are correlated; do not count them as new independent physical units.

## Separate development from held-out data

Assign **whole physical units** to a split before tuning. Keep all their photographs,
derivatives, capture sessions and reports in that split. Product models may span
splits intentionally to test new units of the same model. For stronger claims, add
a separate model-disjoint evaluation later and state its different purpose.

```powershell
.\.venv\Scripts\python.exe -m evaluation.catalog --development .local/phase6-dataset/development.json --independent .local/phase6-dataset/independent.json --screen-leakage
```

Exact file, decoded-pixel and physical-instance overlap is rejected. Phase VI also
rejects declared source-asset, report or capture-session overlap. Unknown independent
instance IDs block held-out scoring. A 63-bit perceptual hash with Hamming distance
at most four flags possible re-encodings/near duplicates for human review. It can
flag distinct similar-looking objects and miss crops/viewpoint changes: it does not
replace provenance review and does not establish identity.

If a flagged pair truly consists of distinct captures, record a review in the
independent manifest's `near_duplicate_reviews` array with `sha256_pair` (the exact
two reported hashes), `decision: "distinct_capture"`, a pseudonymous `reviewer`,
and a specific `reason`. Replacing either image invalidates that review. Exact
pixel, physical-unit and provenance leakage cannot be waived. Unresolved flags
leave independent results inconclusive; development experiments may still run.

## Cropping, localization and masks

The `manual_crop` and `square_pad` recipes require a manual box on every image in
the cohort. Missing annotations make the recipe unavailable, rather than silently
dropping difficult images. Full-frame, cropped and padded transformations are
identical for query and gallery photos within a model recipe. Padding uses each
encoder's normalization mean.

`reviewed_detector` reuses the existing `detector_review`: `accept` requires a
human-selected `proposal_index` and frozen `box`; `manual_fallback` requires the
manual box; `full_frame` records an explicit full-image choice. Changed proposal
geometry invalidates acceptance. Never pick a proposal by ground-truth IoU.

Detector localization is a separate measurement. Add `localization_boxes` and
`localization_provenance` only after annotation independent of detector proposals;
an empty list explicitly labels a negative image. The evaluator measures proposal
recall at IoU 0.5 and negative-image proposal rate. Retrieval crops are not silently
reused as localization truth. The old detection smoke manifest retains approximate
development boxes and is reported separately with that limitation.

Optional `segmentation` has `path`, `sha256`, `reviewed: true`, and `provenance`.
Supply a manually reviewed grayscale binary 0/255 mask with exactly the original
EXIF-oriented image dimensions. The hash binds the review to those bytes. White
keeps foreground; black becomes encoder-mean background. The recipe then applies
the manual crop and square padding. It requires masks for the complete cohort.
No automatic segmenter or additional detector is downloaded by the runner.

## Run experiments

```powershell
.\.venv\Scripts\python.exe -m evaluation.phase6 --enable-experimental --development .local/phase6-dataset/development.json --independent .local/phase6-dataset/independent.json --cache .local/phase6-dataset/descriptors.sqlite --output reports/phase6-new-run.json
```

The explicit flag enables only the **offline experiment engine**. It never changes
web ranking, report statuses, worker concurrency, notifications or ownership claims.
There is no production toggle for installing an unvalidated policy. Installed CLIP
and DINOv2 files are reused; missing models are reported without downloads.
Use a fresh cache path for a cold run. Repeat with the same cache and a new output
name for warm-cache measurement. Output paths cannot overwrite an earlier report.

The isolated SQLite descriptor store reuses production image/model/preprocessing
keying and adds a Phase VI recipe namespace. Transformed pixels bind crops, padding
and masks to the key. Encoders retain bounded, serialized inference caches. The
offline runner is sequential; it retains cohort vectors and per-recipe regions,
so it is not a streaming large-dataset benchmark. Cache entries are sensitive
derived data, unencrypted and retained until the operator deletes the dataset/cache.
Protect their directory and include them in retention cleanup. They never overwrite
the production `ItemImage` descriptors.

## Reading the output

The JSON contains model/source/manifest fingerprints, coverage, leakage screening,
all development trials, frozen configurations, independent observations, category
gate decisions, condition slices, timings, cache counts and supporting pairs. The
Markdown companion is a concise comparison. These artifacts can contain private
photo IDs and annotations; do not publish them without review.

Hybrid CLIP coefficients `{0, .25, .5, .75, 1}` are a development search grid,
not fixed production weights. View recipes are single representative, maximum
pair, all-pair mean, and the mean of best-pair coverage in both view directions.
The hybrid combines models **within each image pair before aggregating views**.
Ranking takes only supplied report groups and vectors; identity labels enter
metrics after sorting. Supporting pairs and per-view score ranges expose conflicting
views but do not assert that a scratch or sticker was recognized. Missing/empty
view groups are invalid; poor-quality photographs are retained rather than removed
using unvalidated quality thresholds. Compare single-view and aggregation recipes
on the identical grouped query cohort.

The runner selects per-preprocessing configurations using development MRR; ties
prefer a single model, a single view, then CLIP. It fits a scalar abstention threshold
on development positive and absent-target queries using the existing balanced
correct-acceptance/rejection objective. Only the frozen configuration and fixed
single-model baselines are assessed on independent queries. Repeatedly selecting
from held-out results would turn that set into development data; collect a new
held-out set after such changes.

Recall@k divides retrieved positives by all labeled positive candidates. mAP
includes zero contribution for missing positives. Precision is correct accepted
top matches divided by all accepted queries; undefined when none are accepted.
False rejection counts abstention on known queries, while the existing false-negative
rate also includes accepting the wrong candidate on a known query. No-match false
acceptance has absent-target queries as its denominator. Scores are similarities,
not identity probabilities. No fitted threshold changes the student-facing UI.

## Photographs still required

Start with 30–50 verified physical units and several photos per unit; this is a
collection target, not a deployment-validation threshold. Include several categories
and at least several product models with two or more visually identical units.
Separate those units across development and held-out groups before photographing.

For each unit collect distinct query/gallery sessions, different angles, light and
backgrounds, close and distant views, and partial occlusion where safe. Include
reflective and textureless items. Where marks exist, add focused views of scratches,
stickers, logos and damage; do not invent distinguishing marks or assume a logo
distinguishes units of one model. Add reviewed crops, optional masks, and multi-photo
report groups. Include absent-target galleries containing same-model negatives.
Image-only identity may be impossible for visually indistinguishable units; human
ownership evidence remains essential.
