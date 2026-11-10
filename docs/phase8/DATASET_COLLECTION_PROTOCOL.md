# Independent dataset collection protocol

Prepare only in VIII-A; no real dataset collected. First target 30–50 physical
objects across categories, including multiple separate units of several identical
product models, smooth/low-texture and reflective objects. This is exploratory,
not a statistical deployment threshold. Use consented staged possessions, no faces,
IDs, screens with personal content or claim evidence. Store all images/derived
embeddings and annotations in approved private, non-synced storage. Follow the
[privacy procedure](PRIVACY_AND_SAFETY.md); approval is pending.

Reuse [Phase VI schema/collection guide](../PHASE6_DATASET.md) and
[evaluation.collection](../../evaluation/collection.py). Create empty schema-3
manifests with evaluation.catalog --init in a NEW directory. IDs identify objects,
models, reports, sessions and original assets, never people. A custodian verifies
physical units by a separate staged custody log; do not infer instance identity
from CLIP, appearance, filenames or model labels. Unknown labels remain pending
and cannot pass strict collection preflight. Labels must describe observations.

Assign whole instances to development or independent (held-out) before tuning or
capture. Photograph each unit in separate query and gallery capture sessions with
different report IDs. Capture front/back/side/oblique views, bright/dim light,
plain/cluttered/different backgrounds, near/far object sizes and safe partial
occlusion. Include natural wear/marks where present, without inventing marks.
Use equivalent condition plans for both partitions. Document failures rather than
removing difficult textureless or indistinguishable units.

Keep originals and their provenance, EXIF-oriented crop geometry and derivatives
linked by source_asset_id. Bursts/derivatives stay in one partition. Capture sessions
also stay in one partition. Models may intentionally span partitions with different
units; later model-disjoint studies answer a different question. All views of an
instance remain in its partition, but query and gallery roles within that partition
MAY share instance identity: this is the valid retrieval-positive case.

Collection fields (schema-3 extension, no production schema changes):

| Scope | Required fields |
| --- | --- |
| Manifest | schema_version=3, dataset_version (frozen nonempty version), split=development or independent, images, queries |
| Image | id, portable repository-relative path, instance_id, product_model_id, report_id (pseudonymous study group), capture_session_id, source_asset_id, label_provenance, role=query/gallery |
| Image metadata | category; optional brand/color/location/product_model under existing supported fields |
| Capture | viewpoint, lighting, background, distance, occlusion as nonempty observed text; additional scalar annotations permitted |
| Selection | selection_confirmed=true plus optional manual_box normalized [left,top,right,bottom]; absence of box explicitly means full frame |
| Query | id, image_id, gallery_ids, positive_ids, relations for every gallery member, no_match boolean; optional existing view_ids/candidate_views/conditions |

Paths use forward slashes, no absolute drive/UNC paths, no traversal. Existing loader
resolves from repository working directory, not manifest parent; run from the
collection repository root. Keep a controlled portable private checkout/root for
external approved storage; do not copy private photos into this synced workspace.
Crop/selection is required on both query/gallery sides consistently for each recipe.

Same unit -> same_instance and positive_ids. Different physical units sharing a
product_model_id -> lookalike, never positive. Different models in category may be
lookalike; different categories normally unrelated, human-reviewed. No-match=true
requires empty positive_ids and no same-instance gallery unit, including grouped
views. Create absent-target cases by removing all same-unit gallery reports while
keeping hard negatives. Similarity scores cannot define absence. Paired present/
absent queries are correlated and do not add independent objects.

[TEST ONLY manifest illustration](../../research/phase8/manifest-TEST-ONLY.json)
shows valid relation structure but references intentionally nonexistent photos.
It is not a runnable accuracy dataset and must fail file validation as supplied.

```powershell
.\.venv\Scripts\python.exe -m evaluation.collection --development PRIVATE/development.json --independent PRIVATE/independent.json
```

The wrapper requires complete collection annotations, explicit no-match agreement,
same-model hard negatives and portable paths, then reuses load_manifest,
validate_v3, screen_splits and coverage. These check IDs, files/decoded duplicates,
metadata conflicts, roles/groups, crops and cross-partition instance/source/report/
session leakage. pHash suspects require recorded review; unresolved flags return
nonzero. Manual provenance review is mandatory: pHash is not an identity oracle.
Empty collections fail readiness, while catalog --init remains useful preparation.
No model is loaded. No duplicate independent retrieval harness was added.
