# Phase 1 stage report

## Audit completed before implementation

See [AUDIT_AND_PLAN.md](AUDIT_AND_PLAN.md) for verified source behavior, causes of
matching failures and the staged implementation plan. The audited frontend is
plain HTML/JavaScript. Shared CLIP preprocessing is consistent between roles but
still center-crops the selected region. Manual selection on candidates was optional.

## Files changed or added

- `backend/main.py`: suggestion API, JavaScript delivery, corrected health stage.
- `backend/detection.py`: local Grounding DINO adapter, box validation, prompt
  bounds, duplicate suppression, detector cache, concurrency guard, error/timing logs.
- `backend/nanodet.py`: lightweight comparison adapter and explicit fast-region option.
- `backend/vision.py`: enforce JPEG/PNG/WebP from decoded content, including when
  an unsupported file is renamed to use a supported extension.
- `frontend/gallery.html`, `frontend/detection.js`: per-image proposals, draft
  overlays, multiple-object selection, accept/dismiss, explicit reference/candidate
  confirmation, original/manual fallback, opt-in diagnostics, visible errors.
- `scripts/download_detector.py`: pinned local model downloads and integrity checks.
- `scripts/benchmark_detection.py`, `data/detection-manifest.json`: repeatable CPU
  timing/memory/localization evaluation with explicit development annotations.
- `tests/test_detection.py`, `tests/frontend_selection.cjs`: API, invalid input,
  missing/busy errors, box clipping/NMS, non-square coordinate mapping, color order,
  user confirmation and multiple proposal review.
- `README.md`, `docs/AUDIT_AND_PLAN.md`, `docs/ASSISTED_CROPPING.md`, this report:
  audit, installation, model investigation, behavior and limitations.

Downloaded model weights, private images, generated benchmark reports and caches
are local artifacts excluded by the existing `.gitignore`. Dependencies unchanged.
The CLIP encoder, relevance rules, gallery ranking and pair-comparison lab are reused.

## Verification

The final full Python suite passed with **38 tests in 4.90 seconds** after upload
format, orientation and explicit detector selection checks were included. It was
run outside the restrictive sandbox so the HTTP tests could execute. The suite was
fully passing. The Node frontend-state checks passed for unreviewed references/candidates,
preview without applying, choosing among multiple objects, accept and dismiss,
asynchronous response handling, explicit detector submission and failure recovery.

The initial sandboxed full suite stalled on TestClient tests. Running the HTTP
tests and full suite outside that sandbox succeeded; no application change was
needed to make those pre-existing tests pass.

The local preview served `/gallery` and `/detection.js` successfully. Live browser
testing returned a region around the uploaded Realme case (incorrectly labeled
cell phone); clicking Preview drew the amber box and showed Accept previewed crop.
The accepted reference remained the user's prior full-image selection. No crop
was accepted on the user's behalf. The successful API response reported 0.3 seconds
including first model load. Evidence: `reports/assisted-crop-preview.png`.
These checks are not a substitute for broad browser/accessibility QA.

## Measured results

Final benchmark: Windows 11, Intel Family 6 Model 186, Python 3.14.5, CPU provider,
two inference threads, per-image warmup, three timed repeats, fresh worker process.

| Candidate | Mean inference | Model loading | Peak process working set | Case localization IoU >= .5 | Chart proposals |
|---|---:|---:|---:|---:|---:|
| NanoDet | 17.9 ms | 222.2 ms | 300.7 MiB | 4 / 6 | 1 / 1 negative image |
| Grounding DINO quantized | Not measured | Not available | Not measured | Not measured | Not measured |
| SAM 2 | Not run | Not installed | Not measured | Not measured | Not measured |

NanoDet localized the distant case, close case, angled query and silver product
case. It missed the black product case and returned a hand/person region instead
of a useful white-case box. Labels on the successfully localized cases were also
wrong. This is **class-agnostic region localization**, not correct object labeling.
The case annotations are approximate development annotations, not held-out data.
The raw repeatable output is `reports/detection-benchmark.json`.

The default assistant is explicitly NanoDet fast-region suggestions because it
is locally installed, benchmarked and fast enough for human review. Its results
do not justify unattended object selection. Grounding DINO remains an **unverified
optional adapter**: repeated CDN streaming/range attempts stalled, and the final
full-file attempt ended with `schannel: server closed abruptly (missing close_notify)`.
No complete weight file was installed. The larger incomplete prefix is preserved
as `models/grounding-dino/model_quantized.onnx.partial`; the pinned downloader can
resume it and must verify the published SHA-256 before installation. The benchmark
records the missing-model failure instead of inventing performance numbers.

SAM 2 was investigated using its maintainers' installation documentation. It was
deferred because editable boxes do not require segmentation, and introducing its
PyTorch/WSL setup is not justified by a measured benefit here.

This completes the first tested Phase 1 increment, **not** the full detector model
comparison or validation for production. No evidence establishes that one detector
is generally more accurate than another, or that retrieval accuracy improved.

## Limits and next stage

No Phase 2/3 identity-retrieval improvement is claimed. This stage isolates reviewed
regions; same-model items, viewpoint changes, occlusion and absent-target searches
remain unresolved. Small development examples do not establish production accuracy.

Next: independently annotated categories, multiple objects and no-target scenes;
then compare crop/global embeddings and local reranking on held-out instance labels
using Recall@1/5, MRR and calibrated acceptance/rejection metrics. Only after those
checks should persistent reports, authentication and claims be implemented.
