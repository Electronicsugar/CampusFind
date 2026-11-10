# Repository audit — 21 October 2026

Audit completed before implementation changes. Source inspected: both HTML pages,
all backend modules, requirements/lock, downloader, ranking reports and all tests.

## Verified behavior

- Frontend is standalone HTML/CSS/JavaScript, not React. No frontend build system.
- FastAPI serves `/`, `/gallery`, `/api/health`, `/api/compare`, `/api/search`.
- CLIP ViT-B/32 runs locally with ONNX Runtime CPU; tokenizer and weights exist.
- Both query and candidates call `vision.prepare(..., normalize=False)` before
  `SemanticModel.describe`: EXIF-corrected decode, normalized box coordinates,
  maximum edge 1000, then CLIP resize-short-edge/224 center crop and normalization.
- Manual crop, reference preview, explicit full-frame reference choice, independent
  invalid-candidate handling, size/pixel limits and stable ranking are implemented.
- Originals remain in browser File objects; images are not persisted by the API.
- 20 baseline tests passed in 4.05 seconds (two TestClient tests excluded because
  the earlier complete run stalled). Real-model sample regressions passed.

## Findings and causes

1. Candidate selection is optional while reference confirmation is required.
   A cropped query can therefore be compared to candidate backgrounds.
2. CLIP's center crop discards edges of non-square regions. Same preprocessing
   does not guarantee that it includes the complete object.
3. CLIP learns broad semantic similarity, not physical-instance identity. Category
   agreement admits lookalikes. Category margins are provisional, not calibrated.
4. Appearance descriptors fail on unrelated content (graph scored ~93.9%);
   SIFT found no real-case geometric inliers. Preserve these as diagnostics.
5. Small objects occupy few input pixels; background dominates full-frame CLIP.
   Perspective/occlusion remove distinctive evidence; cropping cannot recover it.
6. Existing crop proposals were removed after failing the known gallery. No
   detector endpoint or model is implemented in the audited source.
7. No persistence, accounts, report/claim lifecycle, messaging, admin or notifications.
   Health stage text is stale. Documentation contains historical milestone text.
8. Tests mostly cover mechanics; only a few private samples exercise real matching.
   No independent detection ground truth, retrieval benchmark or acceptance policy.
9. Repeated embedding extraction across searches; synchronous CPU work; lazy model
   loading; no detection concurrency guard, timing logs or request-body middleware.
   Image limits apply after multipart parsing, not at ingress. Not production-ready.
10. The upload picker advertised JPEG/PNG/WebP, but the decoder accepted other
    Pillow-readable formats. Phase 1 should enforce the advertised formats from
    decoded content, rather than trusting a filename or MIME header.

## Implementation sequence

1. Benchmark an existing lightweight CPU detector and text-guided Grounding DINO
   on identical available images. Assess SAM 2 installation and role. Record latency,
   memory, errors and boxes; distinguish unlabeled smoke results from accuracy.
   Do not declare a winning model on unannotated samples.
2. Implement a local, modular suggestion API with explicit missing-model errors,
   bounded inference and no automatic crop acceptance. Keep original/manual paths.
3. Add per-image suggestion review: multiple boxes, preview, accept, reject and
   manual adjustment for reference and candidates. Require explicit selection for
   every photo, prevent stale requests/selections from affecting another image.
4. Reuse identical accepted-region preprocessing for both roles. Preserve CLIP
   preprocessing initially to keep the matching baseline comparable; evaluate
   square padding separately rather than silently changing the baseline.
5. Add API, coordinate mapping, empty/multiple detection and UI acceptance tests;
   reproducible detection benchmark format with optional ground-truth IoU.
6. Report measured limitations. Phase 2 retrieval changes and Phase 4 campus
   workflows remain gated on broader, independently labeled evaluation.

No public deployment is part of this stage. No object suggestion is ownership
evidence, and detector scores must not be presented as identity probabilities.
