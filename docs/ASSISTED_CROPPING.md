# Assisted object selection — Phase 1

This stage extends the existing HTML/JavaScript and FastAPI application. It does
not replace CLIP or introduce accounts or saved campus reports.

## Local installation

Use the existing virtual environment and locked requirements. There are no new
Python runtime dependencies. ONNX Runtime, tokenizers, NumPy, Pillow and OpenCV
are reused. No GPU, PyTorch or external inference API is required.

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/download_detector.py --model nanodet
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Grounding DINO's pinned quantized ONNX export is 203,824,675 bytes plus tokenizer
and configuration files. The downloader stores a manifest with revision, file
sizes and SHA-256 hashes. The ONNX hash is checked against its published LFS hash.
Partial downloads are kept separately and resumed with Windows curl. The urllib
fallback restarts partial downloads on other systems. Inference never downloads
files. Images and object descriptions stay on the local computer.

The installed default is NanoDet (3,800,954 bytes). Text-guided Grounding DINO is
an optional adapter requiring `--model grounding-dino`. It is not a silent fallback
or a claimed accuracy upgrade. Use the model status and measured results in
`PHASE1_RESULTS.md` before deciding whether to install it.

## Workflow

1. Open `/gallery`, upload a reference and candidate photos.
2. Select any photo. Optionally describe the target, such as `earbud charging case`.
3. Choose the text-guided assistant, or **Fast regions (NanoDet)** for fixed-category
   region proposals. NanoDet ignores the description and can assign wrong labels.
   Click **Suggest object crops**. Buttons list proposed objects; no box is applied.
4. Preview a proposal. An amber outline distinguishes the draft from the green
   accepted selection. Choose **Accept previewed crop** only after review.
5. For another object, preview a different proposal. To reject all proposals,
   choose **Dismiss suggestions**. Existing accepted selections are preserved.
6. Modify any accepted crop by dragging a new rectangle or using keyboard fields.
   **Use full image** is an explicit choice; the original remains available.
7. Every reference and candidate needs an explicit selection before search.

The default prompt covers common belongings; a shorter target description may
produce different proposals. Boxes and detector labels can be wrong. No proposed
box, detector score or retrieval rank establishes physical identity or ownership.

## API

`POST /api/suggest-crops`, multipart fields:

- `image`: JPEG/PNG/WebP file (existing 15 MB and 24 MP decode limits).
- `prompt`: optional object description, at most 240 characters.
- `model`: `nanodet` (default) or `grounding-dino`; no silent model fallback.

Response includes `model`, normalized `[left, top, right, bottom]` boxes in
`proposals`, labels, raw detector scores, `elapsed_ms`, a user-facing note, and
`requires_confirmation: true`. There is no selected box in the response.
Coordinates refer to the EXIF-corrected original, matching the crop editor and
`vision.prepare`. Both accepted reference and candidate boxes follow the same
existing matching preprocessing. This stage deliberately preserves CLIP's
standard 224 center crop; square padding must be evaluated separately.

Invalid uploads/prompts return 400, unavailable models return 503, and concurrent
detection returns 429. A single inference guard bounds concurrent detector memory.
Timing logs contain model/count/duration, not filenames, photos or descriptions.
The browser allows two minutes per request. Aborting the browser request does not
cancel ONNX inference already running on the server.

The legacy pair-comparison lab remains manual; assisted selection is in the
gallery used for retrieval.

## Reproducible comparison

```powershell
.\.venv\Scripts\python.exe scripts/download_detector.py --model all
.\.venv\Scripts\python.exe -m scripts.benchmark_detection
.\.venv\Scripts\python.exe -m pytest -q
node tests/frontend_selection.cjs
```

The benchmark uses fresh processes for each detector, two CPU inference threads,
per-image warmup, repeated timing and peak process memory. `data/detection-manifest.json`
references private sample files, which remain excluded from Git. Run from the
repository root. `--manifest`, `--models`, `--repeats` and `--output` are configurable.
Use a separate labeled manifest for independent testing rather than modifying the
development examples to support a desired conclusion.

Six approximate case boxes were visually annotated before Grounding DINO inference.
They are case-only annotations: floating earbuds in product photos are separate
objects. Success means every annotated case has some proposal at IoU >= 0.5,
independent of predicted label or rank. The chart has an explicit empty target list.
This tiny development set cannot establish general detection accuracy. Empty boxes
mean a labeled negative; omitted boxes mean unannotated (accuracy is null).

The benchmark reports negative-image proposal rate, which is not the retrieval
false-positive rate. Recall@1/5, MRR and no-match acceptance require a separate
retrieval dataset with physical-instance labels and held-out thresholds in Phase 2/3.

NanoDet's final labeled development smoke run localized four of six cases at IoU >= .5,
despite incorrect category labels, and returned a proposal on the one negative
chart. Mean inference was 17.9 ms, loading 222.2 ms, and peak process memory
300.7 MiB on this laptop (CPU provider, two threads, three measured runs per image).
These are proposal-localization observations, not object identification accuracy.
Its use is limited to suggestions a person reviews. See the saved benchmark
report for raw boxes and per-image measurements.

## Model investigation

- [NanoDet / OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_nanodet):
  small fixed-category detector; benchmark adapter is separate from gallery routing.
- [Grounding DINO](https://github.com/IDEA-Research/GroundingDINO) and its
  [quantized ONNX export](https://huggingface.co/onnx-community/grounding-dino-tiny-ONNX):
  text-guided boxes without a fixed COCO-only category list. CPU runtime is benchmarked
  locally rather than extrapolated from published GPU results.
- [SAM 2 installation](https://github.com/facebookresearch/sam2/blob/main/INSTALL.md):
  segmentation can refine an object after selection, but adds PyTorch/torchvision
  and a different installation path (the maintainers recommend WSL on Windows).
  SAM 2 was investigated, not installed or benchmarked. No local performance claim
  is made. It is not required to deliver editable bounding boxes in this stage.

## Production limits

The application remains a local research prototype. Multipart limits are checked
after request parsing; production ingress needs body limits, authentication,
rate limits, storage policies and operational monitoring. No production deployment
or privacy-sensitive campus workflow is introduced here. Detection and retrieval
need independent categories, multi-object scenes, hard negatives and absent-target
queries before progressing to the full campus service.
