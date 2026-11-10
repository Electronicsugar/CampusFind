# Phase VI recognition audit

Inspected 28 October 2026 before modifying retrieval code.

Production remains per-photo CLIP with category sections. No new configuration
will be installed without independent physical-instance evidence.

| Component | Observed implementation | Accuracy/evaluation concern |
| --- | --- | --- |
| `backend/semantic.py` | Quantized CLIP B/32, short-edge 224 then center crop; normalized image vector; averaged text prompts | Off-center objects or long crops lose pixels. Text-category margin is not calibrated identity confidence. |
| `evaluation/encoders.py` | Quantized DINOv2 small, configured resize/center crop and CLS token; CPU two threads | Same framing risk; no category classifier, so compare raw retrieval separately from CLIP routing. |
| `backend/nanodet.py`, `detection.py` | 416 letterbox, normalized coordinate inversion, fixed COCO labels, proposal filtering | Earbud cases are outside explicit COCO categories. Localization and label accuracy are separate; manual review must remain. |
| `backend/vision.py` | EXIF transpose before normalized crop, minimum 24 pixels, max-side 1000 | Very small objects lack detail; center cropping downstream can discard selected pixels. |
| `semantic.relevance`, `gallery.score_descriptions` | Matching labels accepted even at small margin; disagreement often uncertain; low-structure override | Cropped positive case changes from earbuds to charger at a tiny margin. Sections can obscure good visual retrieval. No evidence yet to weaken production gate. |
| `backend/matching.py` | Every query photo versus eligible opposite-type report photos; directional gate; SQL sort and per-photo pages | Multiple photos can repeat the same report. Background or an accidental best pair can dominate naive multi-view maximum. |
| `PreparedCache`, `embedding_cache.py` | Content/crop/model/preprocessing signature, persisted CLIP and appearance, bounded RAM and serialized inference | Preserve production descriptors. Experimental model/preprocessing entries need an isolated cache namespace. |
| `backend/worker.py` | Durable pending job, one database-wide matching lock, transactional pairs | Keep experiment work offline so it cannot affect notifications, claims or production job latency. |
| Existing evaluation | Explicit relations, instance split isolation, byte/pixel duplicate checks; full/manual/reviewed detector/pad/fusion; model and gate trials | Missing perceptual near-duplicate review, strict report/capture schema, mAP/acceptance precision and report-level supporting pairs. |
| Existing multi-view hybrid | Combines each model's maximum independently | Maxima may come from different image pairs; a new experiment must expose consistent combined pair scores and disagreement rather than imply one jointly strong pair. |

Available data: seven development images, three positive and three absent-target
queries, one known physical instance, four unknown-instance negative images, no
independent images. No labeled same-model physical-unit negatives, multi-photo
reports, masks or distinctive-mark regions. Do not invent these annotations.

Implementation scope: extend the existing manifest/evaluation machinery; add a
strict optional schema, leakage review, report-level experiments, abstention metrics,
isolated persistent cache and explicitly enabled offline runner. Reuse existing
local encoders and reviewed detector boxes. Do not repeat the unproductive SIFT
experiment without new detail-bearing photographs. Segmentation accepts reviewed
masks only; no automatic segmentation model is justified by current evidence.
