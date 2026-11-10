# Reproducible retrieval experiments

The production application still uses its existing CLIP preprocessing, semantic
routing and ranking. Experiments live in `evaluation/` and do not configure the API.
The implemented application change is bounded embedding caching, safe CPU inference
serialization, visible encoder failures and search timing. No experimental score
weights, thresholds, square padding or DINOv2 encoder are enabled in the website.

## Run

From the repository root using the existing environment:

```powershell
.\.venv\Scripts\python.exe -m evaluation.run --models clip --local-evidence
.\.venv\Scripts\python.exe scripts/download_dinov2.py
.\.venv\Scripts\python.exe -m evaluation.run --models clip dinov2 --local-evidence
.\.venv\Scripts\python.exe -m evaluation.verify_cache
.\.venv\Scripts\python.exe -m pytest -q
node tests/frontend_selection.cjs
```

DINOv2 is optional: the explicit downloader installs a pinned, SHA-256 verified
24,451,943-byte quantized small encoder and configuration. There are no new runtime
dependencies, no PyTorch installation and no inference downloads or external API.
The application does not load DINOv2. `--development`, `--independent`, `--models`
and `--output` configure the evaluator. Private sample photos and model weights are
excluded from Git; another checkout needs its own images/annotations and installed
CLIP/NanoDet models. Missing models are recorded as unavailable, not replaced silently.

Validation on this machine: 56 tests passed on the host, plus frontend-state checks.
A subsequent sandbox-only evaluation test run hit four temporary-directory fixture
setup errors; rerunning those tests on the host passed all 12. This is an execution
environment restriction, not a reproduced retrieval failure. The earlier TestClient
sandbox restriction also remains relevant when running the full suite from Codex.

The JSON report contains every candidate score, relevance label, ordering, query
condition, threshold fit and timing. A Markdown report is generated beside it.
Source checksums, model fingerprints, manifest checksums, library versions, platform,
worker memory and CPU configuration are recorded. Different encoders run sequentially
in separate worker processes. Avoid concurrent CPU-heavy jobs when timing them.

## Ground truth and isolation

`data/retrieval-development.json` contains the existing seven development images.
Three positive and three absent-target queries reuse three views of **one**
user-reported Realme case. Other product images are different-model lookalikes;
the graph is unrelated. Same-instance ground truth is user-reported, not independently
verified. These correlated views do not establish accuracy on three independent objects.

`data/retrieval-independent.json` is deliberately empty. It must be populated with
new physical instances, not development photos under new filenames. Keep stable,
globally unique physical-instance IDs. The loader rejects duplicate content, identical
decoded pixels (including lossless re-encodings), contradictory relation labels,
self-matches, missing files, and physical-instance overlap across splits. Lossy
near-duplicates and incorrect human IDs still need curator review; hashes cannot
prove that photographs depict different physical objects.

Each image entry has `id`, repository-relative `path`, `instance_id` (required and
consistent for positives), and `manual_box` in normalized EXIF-corrected coordinates.
Each query has:

```json
{
  "id": "heldout-item-view-a",
  "image_id": "view-a",
  "gallery_ids": ["lookalike-view", "view-b", "unrelated-view"],
  "positive_ids": ["view-b"],
  "relations": {
    "lookalike-view": "lookalike",
    "view-b": "same_instance",
    "unrelated-view": "unrelated"
  },
  "conditions": ["view_angle", "background_change"]
}
```

For no-match queries, use `positive_ids: []` and only negative relations. Every
query/candidate pair needs a label. Do not label two different units as the same
instance merely because their product model or brand agrees.

Manual-crop recipes require a crop/full-frame annotation on every image. Reviewed
detector recipes additionally require an explicit `detector_review` decision:
`accept` with the frozen proposal index and normalized box; `manual_fallback`; or
`full_frame`. Accepted geometry is checked on replay. The development reviews are
agent annotations of prior Phase 1 proposals, not independently evaluated user choices.
There is no automatic ground-truth-IoU oracle for choosing a crop. Missing annotations
disable a recipe rather than silently removing its difficult examples.

## Compared recipes

1. Full frame: the existing shared preparation and standard encoder preprocessing.
2. Manual object crops on both reference and candidates.
3. Reviewed NanoDet regions, with explicitly recorded manual/full-frame fallback.
4. Unreviewed top NanoDet proposal (a stress test, not the website's behavior).
5. Manual crops centered on an aspect-preserving square filled with the encoder mean.
6. Global/object score fusion: a predeclared coefficient grid, fitted on development
   routed MRR. Exact ties prefer the larger global coefficient. Nothing is deployed.

For CLIP, category routing and featureless-image handling reproduce the live gallery;
tests compare offline results directly with `rank_gallery`. Raw, unfiltered embedding
results are also reported because category mistakes can move correct results into
the uncertain section. Fusion holds crop-based category routing fixed while changing
the visual score. DINOv2 has no category head here; its raw and routed lists are the
same. Compare **raw** columns when comparing the two encoders' visual retrieval.

Both roles receive identical operations within a recipe. Pixel aspect ratio is
preserved when preparing crops; the encoder's standard center crop can still cut
off edges unless the square-pad recipe is selected. Image scores follow the existing
four-decimal precision and appearance-only tie break for baseline comparability.

## Metrics and abstention

- Recall@1/@5: fraction of labeled positive images in the first k results, averaged
  over positive queries. With one positive per query this equals the usual hit rate.
- MRR: reciprocal of the first positive rank, including zero for a missed positive.
- Wrong top-1 count: wrong first suggestion on queries with a known positive.
- Proposal no-match rejection: no relevant suggestions on a labeled absent-target
  query. Suggestions are not accepted identity matches.
- Thresholded false positives: every accepted wrong top result, including wrong
  acceptance on queries where the true item exists. The absent-target false-positive
  rate uses only absent-target queries as its denominator.
- No-match rejection and correct acceptance recall are reported together. Rejecting
  everything can appear perfect on rejection and useless on positive retrieval.

Threshold fitting uses development scores only and maximizes balanced correct
acceptance/no-match rejection. Conservative higher thresholds break ties. Only the
frozen development value and selected fusion coefficient are applied to independent
queries. An empty independent split returns **inconclusive**, with unavailable metrics,
not zero accuracy. Development acceptance rates are explicitly optimistic fits and
must never be described as validated precision, confidence or identity probability.

The optional local-feature check reuses cropped CLAHE/SIFT plus geometric verification
on positive/lookalike/unrelated pairs. The available positives produced no geometric
inliers, so neither local reranking nor a heavier matcher is enabled. Optional brand,
color, category and description metadata have not been scored: the dataset lacks
independently labeled metadata. Filenames and ground-truth IDs are never retrieval
features. Future metadata/local signals need development fitting and independent
validation; no fixed weights have been invented for them.

## Cache, privacy and CPU limits

The live CLIP cache stores at most 256 descriptor records in RAM. It retains no raw
photos and writes no descriptors to disk. Entries are evicted by LRU or disappear
when the process ends. Keys hash prepared pixel content, shape/dtype, actual model
fingerprint and a versioned preprocessing recipe. The model fingerprint includes
the vision weights, text/category embeddings, normalization constants and labels.
Different crops, pixels, models or preprocessing configurations cannot share an
incorrect entry. Returned vectors are copied to prevent caller mutation.

Concurrent misses are serialized to one native CLIP inference (two native CPU threads);
duplicate requests reuse the first result. Waiters time out after ten seconds with
a visible 503 error. Inference failures are not cached and never trigger an
appearance-only fallback. NanoDet retains its separate Phase 1 inference guard.

`evaluation.verify_cache` requires identical cold/warm search responses apart from
`elapsed_ms` and requires zero new inference calls for unchanged inputs. It measures
the whole handler, including reads/decode/scoring/previews, separately from model
loading. API search timing and encoder timing logs contain no filenames, images,
descriptions or content hashes. Optional DINOv2 uses the same bounded cache class
only inside its isolated experimental worker.

## Remaining evidence needed

Collect multiple physical units of the same product model, several views of each,
lighting/background/scale changes, smooth objects, distinctive marks and absent-target
queries with plausible lookalikes. Partition by physical instance before tuning, then
freeze preprocessing/fusion/thresholds and evaluate untouched instances. Expand beyond
earbud cases. Until then, the reported observations support efficiency improvements
and failure diagnosis, not a new production identity-matching policy.

Model references: [official DINOv2 model card](https://github.com/facebookresearch/dinov2/blob/main/MODEL_CARD.md),
[DINOv2 encoder outputs](https://huggingface.co/docs/transformers/model_doc/dinov2),
[pinned ONNX conversion repository](https://huggingface.co/Xenova/dinov2-small).
