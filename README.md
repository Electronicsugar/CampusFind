# CampusFind — Smart Campus Lost & Found

## Public demonstration

Website: https://campusfind-alpha-nine.vercel.app/

The frontend is on Vercel Hobby. The FastAPI backend, matching worker, separate
PostgreSQL cluster (loopback port 5434), and private images run on the owner's
computer. An HTTPS Cloudflare Quick Tunnel connects Vercel to the backend. This
is a free computer-hosted demonstration, not an always-on cloud deployment.
The backend stops being available when the computer sleeps, shuts down, loses
network access, or the tunnel/processes stop. Docker is not required for this setup.

After restarting the computer, run `./start-public.ps1` from this checkout. It reuses
the isolated database/storage, starts the worker/web/tunnel, updates Vercel with
the new temporary tunnel address, and redeploys. It requires the existing Vercel
CLI sign-in. `./start-public.ps1 -Status` checks availability without restarting.
Partial starts/occupied ports require inspection rather than stopping unknown
processes. This helper is not an installed Windows service or automatic supervisor.

Private configuration and data are stored outside this OneDrive workspace under
`%LOCALAPPDATA%/CampusFind/public/<instance-id>/`, with restricted Windows access.
`.local/public-host-pointer.json` identifies the instance without containing its
database password. Do not commit or share the private runtime/operator JSON files.
The previous local development database and reports are separate. The public demo
uses seven-day photo retention. No existing private photos were copied to it.

Public demo self-registration is explicitly enabled with
`CAMPUSFIND_PUBLIC_REGISTRATION=true`. Other production instances remain closed
unless they opt in. Signup does not verify email ownership or campus affiliation.
No administrator was created (owner's choice). HTTPS, Secure sessions, CSRF
protection and shared throttling remain enabled.

New accounts and password resets require 6–12 characters, including at least one
letter and one number. Existing passwords remain valid for login.

Signup shows eight private recovery codes once, with a download and save
acknowledgment. Store them securely outside CampusFind. **Forgot your password?**
on the login page accepts your email, one saved code and a new password. A reset
revokes all sessions and replaces the entire recovery-code set; save the new set
before logging in. Only SHA-256 hashes of random 128-bit codes are stored in the
database. Codes remain valid until replaced or used; using one invalidates all
other codes in that set. Never include codes in reports or screenshots.

Already signed in? Profile lets you generate replacement codes after confirming
your current password. Existing accounts need to do this once to enable recovery.
There is no email delivery service or email reset flow. If you have forgotten the
password and have no saved code, automated recovery is unavailable; contact the
operator. An email address alone is not proof of account ownership.

`CAMPUSFIND_BACKEND_URL` in Vercel is an HTTPS origin, not a database credential.
The frontend build copies only allowlisted static assets. When the backend address
is absent it publishes an explicit unavailable notice and API 503 responses.
No frontend authentication bypass or model/ranking change is introduced.

Verified on 23 November 2026: public homepage/options/readiness, HTTPS session,
generated-photo report upload, authenticated image access and a real worker match
completed successfully; synthetic reports were deleted and test accounts disabled.
This is deployment functionality evidence, not recognition-accuracy validation.

Account-access update verified on 23 November 2026: public signup, recovery-code
replacement, password reset, session revocation, replay rejection and login with
the new password passed through the public HTTPS URL. The synthetic test account
was disabled afterwards. Automated checks: 175 Python tests passed (4 skipped),
73 PostgreSQL tests passed, and all six frontend check scripts passed, including
the signup/recovery flow. A verified private backup preceded migration
`0004_account_recovery`. Production matching behavior is unchanged.

24 November follow-up: a failed temporary tunnel returned API 502 responses,
which the login screen incorrectly interpreted as closed registration. The
connection was replaced and public signup/recovery rechecked successfully.
Create account now stays visible; opening signup refreshes registration settings
and offers Retry connection when the backend cannot be reached. All six frontend
check scripts passed, including outage, retry and explicitly closed signup cases.
The restart helper preserves the existing Vercel variable's Secret type.

## Search found items before publishing

Choose **Search by Image** in the navigation or **Search found items by image**
on Browse. The home page's **I Lost Something** starts here too. You can still
browse by text, location and category first.

1. Sign in and choose one JPEG, PNG or WebP (up to 15 MB / 24 megapixels).
2. Draw/adjust an object crop, use the NanoDet crop assistant, or explicitly choose
   the full image. Optionally narrow by category or location/description.
3. Search existing active found reports. Inspect ranked reports, compare the
   selected regions side by side, and use the existing private claim workflow
   when ownership details are convincing.
4. If nothing looks right, choose **Continue to lost report**. Your photo and
   crop carry into the draft. Publication still requires reviewing the report.

Search creates no report, notification or claim, and retains no query photo on
application storage. The browser keeps the photo/results in this tab for return
navigation, until replaced, logged out, refreshed or closed. Existing found photos
remain subject to authentication, visibility and retention rules.

`POST /api/v1/found/search-image` requires a session, Origin and CSRF token. It
accepts multipart `photo`, JSON `selection` (`confirmed: true`, `box`: normalized
coordinates or `null`), optional `category`, `q`, and `offset`. It searches all
eligible photos within those filters, ranks by CLIP cosine similarity, keeps the
best photo per report, and returns 25 reports per page. Category predictions are
advisory and do not suppress results. No confidence percentages or automatic
identity/no-match verdicts are returned. Saved-report matching policy is unchanged.

Candidate descriptors reuse the existing content/model/preprocessing/crop cache.
CPU encoding is serialized with the worker through a PostgreSQL advisory lock;
concurrent/busy requests receive a retryable response. Searches have a 45-second
processing budget and 2,000-photo cap. Larger/cold galleries may require narrower
filters; they fail explicitly instead of returning a silently incomplete ranking.
The existing local CLIP model is used; no new download is required. Timing and
candidate counts are returned and logged without query pixels or account details.

This adds a practical retrieval workflow, not Google Lens-level recognition.
Different views, identical products and missing candidates remain difficult.
Synthetic tests establish functionality, privacy, cache reuse and pagination;
they do not demonstrate real-world same-instance accuracy.

Verified on 24 November 2026: 187 general Python tests passed (4 skipped), 85
PostgreSQL checks passed, and all seven frontend scripts passed. A public HTTPS
test with the real CLIP encoder retrieved an existing generated found-report
photo and opened its authenticated report/image without creating a lost report.
For that one synthetic candidate, first and repeated search processing took
1,474.3 ms and 3.1 ms; these are functionality/cache observations, not gallery-scale
latency or recognition-accuracy benchmarks. Generated reports were deleted and
test accounts disabled. Browser checks confirmed photo selection, explicit full
image acceptance, a filtered empty result and photo transfer to an unpublished
lost-report draft.

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

