# Image-search root-cause diagnosis — 25 November 2026

## Confirmed failure chain

1. The active browser tab loaded `/assets/app.js?v=7.6`; production HTTP requests served version 7.7 and byte-identical current source.
2. The tab retained the old free-text category field and sent `hair clip` as an exact category constraint.
3. The published found report was active and visible, with one photograph, stored category `other` and location `canteen table`.
4. Category filtering selected zero candidate photos before the encoder ran. The old client rendered the generic empty-gallery message and did not understand the newer filter diagnostics.
5. Hash-route navigation does not reload scripts. Deploying a fix or changing pages did not replace the JavaScript already executing in this tab.

## Components checked

| Component | Evidence | Conclusion |
| --- | --- | --- |
| Public site and backend | Homepage, assets and readiness returned HTTP 200 | No outage during this diagnosis |
| Deployment | Served HTML referenced 7.7; script bytes matched checkout | Fix was deployed; browser was still executing 7.6 |
| Database | Existing FOUND and LOST reports active, visible, unexpired, each with one image | Reports were not missing |
| Storage | Both stored JPEG hashes matched their database records; images decoded at 1280 × 960 | No missing or corrupted upload |
| Crops | Both normalized stored crops decoded successfully | Cropping did not prevent candidate selection |
| Worker | Both matching jobs DONE; worker idle with heartbeat about 3 seconds old | Not a pending or failed job |
| Encoder | Both stored object regions encoded successfully | Local CLIP model available |
| Category prediction | Both real object photos were predicted as earbuds | Category guesses are unreliable for this object |
| Stored-pair similarity | CLIP cosine 0.8065 for the existing LOST/FOUND regions | A measurable visual signal exists; this is not identity probability or accuracy evidence |

## General correction

Image search now considers all active, visible, unexpired FOUND reports across every category by default. Category and text inputs are advisory metadata hints and never exclude or reorder visual candidates. Only the explicitly selected **Limit results to this category and text** checkbox activates strict metadata filtering. Older clients omit that flag and therefore receive broad visual retrieval automatically, even when they still submit a descriptive category or wrong location.

Strict filtering remains available for intentional narrowing and CPU-bound galleries. Empty strict results disclose the available visible gallery counts and the reason no image comparison ran. The notice includes this explanation for older clients too. No result is labelled as a verified physical identity, and category guesses no longer appear as evidence of a match. The separate published-report matching policy remains unchanged.

Version 7.8 adds one release manifest shared with the backend and frontend builder, response version headers, an update notice on a detected version mismatch, and revalidation when the tab regains focus. Reload is explicit and warns that unsaved photos/drafts/recovery codes will be lost; there is no forced reload. Main HTML and app assets use no-store headers. These measures do not retroactively change code already running in a 7.6 tab; backend compatibility is what fixes those tabs immediately.

Browse and image-search category controls use the same choices as the report form. The generic `other` category remains available for objects outside the named choices. No object name, user image, category exception, matching weight or acceptance threshold was added to special-case this report.

## Limits

The encoder can rank objects of arbitrary categories, but dependable same-physical-instance recognition under all viewpoints or among identical products is not established. This user case is a reproduction and regression check, not a held-out evaluation dataset. No user photographs or embeddings were committed, used for training, or used to tune thresholds.

Search remains bounded to 2,000 candidate photos and a 45-second processing budget; large/cold galleries may require explicit narrowing. Busy/model/unavailable errors must remain distinct from an empty gallery. Public availability still depends on the owner's computer and the temporary free tunnel; always-on hosting and a stable tunnel are separate deployment requirements.

## Final verification

- 195 general Python tests passed (4 skipped).
- 26 PostgreSQL image-search/deployment checks passed.
- 26 targeted final image-search/deployment checks passed after the shared-release refactor.
- All seven frontend scripts passed, covering explicit filtering, broad retry, client-version warning and release build validation.
- Re-ran the original 7.6 tab without clearing its `hair clip` category or replacing its photo. The existing found report was retrieved, one report/one photo was searched, and the server explained that the tab was old. No report was modified or published.
- Published release 7.8 to the existing Vercel production alias.

These checks establish the corrected retrieval path and compatibility. They do not establish universal recognition accuracy.
