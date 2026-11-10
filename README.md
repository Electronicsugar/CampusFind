# CampusFind — Smart Campus Lost & Found

## Current milestone: Phase VI recognition experiments

Phase VI adds stricter dataset validation, leakage screening, report-level visual
experiments, supporting image pairs, no-match metrics and an isolated descriptor
cache. See the [measured results](docs/PHASE6_RESULTS.md) and
[real-photo collection guide](docs/PHASE6_DATASET.md).
The experimental engine requires an explicit offline opt-in; production ranking
is unchanged. Independent physical-object recognition remains **inconclusive**.

## Phase 5 pilot hardening

CampusFind now includes PostgreSQL-backed accounts, private multi-photo reports,
assisted object cropping, saved CLIP suggestions, private claim review, in-app
notifications and administrator moderation. Phase 5 adds security and storage
hardening, tested recovery, matching infrastructure optimizations and operational
checks. Overall pilot status is **PARTIALLY READY**; see the
[readiness report and measurements](docs/PHASE5_READINESS.md) and
[production operations guide](docs/PILOT_OPERATIONS.md).

For local development, start with
[Phase 4 setup](docs/PHASE4_SETUP.md) and [implementation results](docs/PHASE4_RESULTS.md).
Run `./start.ps1 -PortableDatabase` after the documented first-time setup.
This launcher is for local development; use the operations guide for production.
The application opens at http://127.0.0.1:8000/; pair comparison is at `/lab`
and the research gallery remains at `/gallery`.

Production retrieval ranking is preserved. Independent identity-recognition
accuracy remains inconclusive; visual suggestions never establish ownership.

## Earlier research milestones

## Assisted object selection

The repository audit and staged plan are in `docs/AUDIT_AND_PLAN.md`.
Assisted crop setup, review behavior, API and benchmarking instructions are in
`docs/ASSISTED_CROPPING.md`. Suggestions require acceptance; every reference and
candidate now needs an explicit crop or full-image choice. CLIP ranking is preserved.

Offline retrieval evaluation now compares full frames, manual/reviewed detector
crops, square padding, global/object fusion and an optional CPU DINOv2 encoder.
See `docs/RETRIEVAL_RESULTS.md` for measured development results and
`docs/EVALUATION.md` for reproducible commands, ground-truth schema and split rules.
There is no independent labeled test set yet; no accuracy upgrade or fitted
acceptance policy has been installed. The live CLIP path now safely caches unchanged
embeddings and serializes native inference; its scores and ranking are preserved.

A local full-stack application with FastAPI, a responsive crop interface, and local CLIP inference. General-purpose chat remains outside this milestone.

From this project folder, start:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

- Gallery: http://127.0.0.1:8000/gallery
- Pair comparison: http://127.0.0.1:8000/lab
- API docs: http://127.0.0.1:8000/docs

After backend updates, stop the existing server with Ctrl+C, run the command again and refresh the page. The first comparison loads the model and takes longer. No API key is needed. The installed model runs locally without network access; photos are never sent to the model provider.

## What changed after the graph false positive

The old color/edge baseline rated the supplied case and oscilloscope screenshot 93.9%. That is retained as a diagnostic, not a search ranking signal.

The current pipeline uses an ONNX-quantized CLIP ViT-B/32 model:

1. Apply the user's crop and standard CLIP preprocessing (resize, center crop, RGB normalization).
2. Encode image content and compare against prompt groups for campus item categories, scenes, diagrams and screenshots.
3. Put candidates with matching predicted item categories into Similar-item candidates. Ambiguous cases are displayed separately. Confident non-item content or strong category mismatches are excluded from similar items but remain inspectable under Unrelated candidates.
4. Rank each section by cosine similarity of CLIP image embeddings. Color/structure overlap only breaks exact semantic-score ties; upload order breaks remaining ties.

The displayed CLIP value is an embedding similarity, not an identity probability. It is not comparable to the earlier appearance percentage. Same-label inclusion is intentionally permissive; broad category agreement does not prove that two objects are identical. Exclusion margins are provisional heuristics, not validated confidence thresholds. A chart and software interface are both non-item content, so their combined best evidence is compared with physical-item categories rather than requiring them to beat each other by a large margin.

The gallery now requires an explicit reference-region choice: draw a crop, use the keyboard crop fields, or explicitly choose Use full image. The reference thumbnail shows the actual selected crop. Cancelling a selection disables searching until a valid selection is made.

Keep the object centered in a tight crop: CLIP center cropping may discard an off-center item. This model can still confuse products, miss unknown categories, or rank lookalikes highly. Further evaluation needs different objects of the same model, more categories, and absent-target searches. No broad accuracy claim is made from this regression pair.

## Uploads and privacy

Gallery: one reference, up to 12 candidates, 15 MB per image, 60 MB for candidate uploads, 24 megapixel image cap. Uploaded images are processed in memory and are not persisted. Refreshing clears the session gallery. Invalid candidate images are reported individually. Missing model files return a visible error; there is no silent fallback to appearance-only search.

Derived CLIP descriptors may remain in a bounded 256-entry memory cache until LRU
eviction or process restart. Raw photos are not retained by that cache, and no
descriptors are written to disk. Search responses include elapsed processing time.

The provided test photos are copied under `data/samples` and excluded from Git. The source paper is in `docs/research-paper.pdf`. Model files and the virtual environment are ignored.

## Setup on another computer

Use Python 3.14, create `.venv`, install `requirements-lock.txt`, then:

```powershell
.\.venv\Scripts\python.exe scripts/download_model.py
```

The downloader uses a pinned model revision, writes partial downloads separately, and records file hashes. Model files total approximately 156 MB. Dependencies require additional disk space. Runtime inference performs no downloads.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The real-image regression verifies that the chart is excluded while the close-up earbud case remains relevant, even with misleading filenames. Unit tests cover ambiguous relevance, missing-model failure, ordering, input errors and baseline behavior. Synthetic ranking tests use an explicit mocked encoder and are not model-accuracy tests.

`python -m backend.experiment` preserves the earlier appearance/SIFT experiment for comparison. See `docs/SEMANTIC_RESULTS.md` for observed model results and limits.

## Files

- `backend/semantic.py`: local model, preprocessing, categories and relevance rules
- `backend/gallery.py`: candidate scoring and sorting
- `backend/main.py`: API and local pages
- `backend/vision.py`: image validation and earlier appearance/SIFT diagnostics
- `frontend/gallery.html`: crop editor and three relevance sections
- `frontend/index.html`: pair-comparison lab
- `docs/ROADMAP.md`: paper-derived full-stack stages

Model: https://huggingface.co/Xenova/clip-vit-base-patch32 (ONNX conversion of OpenAI CLIP, MIT license). Original model: https://huggingface.co/openai/clip-vit-base-patch32 . CLIP preprocessing is read from the downloaded model configuration. Do not publish this local research server as a production campus system.


## Distant-reference ranking regression

The supplied screenshot was reproduced exactly using the original distant photo with no crop: white case 0.7043, silver OnePlus 0.6725, black OnePlus 0.6553, correct Realme 0.6289 (rank 4). With a reference crop of left 26%, top 40%, right 60%, bottom 59%, the same model and candidates put the Realme first at 0.7464. No filename rules, brand rules or ranking-weight changes were needed for this example. The graph remains excluded.

Run `python -m scripts.check_ranking` using the virtual environment to reproduce the three scenarios. Tests cover the selected-region ranking and the UI's explicit-selection state. This verifies this known gallery, not general retrieval accuracy. Earlier CLIP region proposals were tried but did not improve this gallery and are not enabled. The new assisted detector is separate; install its local weights and review every suggested crop as described in `docs/ASSISTED_CROPPING.md`.

## Phase 3 reliability experiments

See [Phase 3 implementation and limitations](docs/PHASE3.md), [real-photo dataset guide](docs/PHASE3_DATASET.md), and [measured diagnostics](docs/PHASE3_RESULTS.md). Production ranking is unchanged; no independent same-model identity or rejection accuracy is established. The gallery now includes side-by-side inspection and clearer potential-match explanations.
# Phase VII interface

The student interface now includes responsive navigation, guided report review,
in-tab drafts, crop confirmation, selected-object comparison and clearer claim
and notification states. See [Phase VII results](docs/PHASE7_RESULTS.md) for
screenshots, verification and remaining limitations, and the
[initial audit](docs/PHASE7_AUDIT.md). Matching remains advisory.

