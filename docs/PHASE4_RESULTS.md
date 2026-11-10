# Phase 4 implementation and validation

The local MVP now supports accounts, PostgreSQL persistence, multiple private
photographs, reviewed object crops, stored CLIP suggestions, private claims,
receipt confirmation, in-app notifications and administrator moderation.
See PHASE4_SETUP.md for startup, environment settings and operator commands.

## Verification

- Full Python regression suite: **85 passed, 1 skipped**. The skip requires PostgreSQL.
- PostgreSQL platform suite: **17 passed**, including concurrent claim approvals,
  migration downgrade/upgrade, schema comparison, access controls, retention,
  upload failure cleanup, persisted embedding reuse and model-version invalidation.
- Existing frontend selection regression script passed; application JavaScript syntax checked.
- Live browser: registration, two-photo publication with explicit selections,
  real CLIP matching, side-by-side image inspection and private finder approval.
- Local API: second student's private claim, receipt confirmation, notifications,
  owner deletion of both synthetic reports. Fixture accounts were disabled afterward.
- Mobile landing page checked at a 390-pixel viewport with no horizontal overflow.

These are functional checks using synthetic fixtures, not recognition-accuracy
measurements. No private benchmark photographs or labels were changed.

## Challenges resolved

Docker's engine was unavailable locally. An official PostgreSQL Windows runtime
provides a documented portable alternative, with a localhost-only server and a
dedicated application role. Database migrations also run against disposable schemas.

The existing embedding cache key is binary; persistence now stores its hexadecimal
representation. Keys still include content, model and preprocessing, so altered
crops or models invalidate descriptors. Failed model loads preserve submitted reports.

Live form testing exposed disabled controls being omitted from upload metadata;
values are now captured before disabling controls. Campus dates use a configured
timezone rather than the UTC calendar day. Claim approval locks and database
constraints prevent two claimants receiving concurrent approval for one item.

## Security review

Passwords use Argon2id. Opaque sessions are hashed in the database, expire, rotate
at login and revoke at logout. Writes enforce origin and CSRF checks. Database
rate limits cover authentication, publication, claims and match retries. Photo
uploads are bounded, decoded, re-encoded without EXIF and stored under random
private names. Every image/report/claim route checks access; claim evidence and
student contact data are excluded from public report responses. Administrator
actions are audited. Production cookies require HTTPS configuration.

This review and regression coverage are not a penetration test. Before campus
deployment, add verified campus email or SSO, account recovery, HTTPS operations,
backup and deletion validation, monitoring, load tests and an independent security
review. An allowed email domain alone does not establish campus membership.
Move private storage outside cloud-synced folders for a pilot.

## Retrieval limitations and next steps

The production CLIP ordering and category gates remain unchanged. Multiple views
are compared separately; no unvalidated fusion weights or identity thresholds were
introduced. DINOv2 and hybrid experiments stay in the existing research harness.
In-app suggestions are not ownership verification or calibrated identity probabilities.

Independent accuracy remains inconclusive. Collect multiple physical units of the
same products, varied angles/light/backgrounds, low-texture objects, occlusions and
queries whose correct object is absent. Keep development and held-out object units
separate, then use the existing evaluation harness before changing production ranking.
The current serial CPU gallery scan also needs representative load measurements
before a larger campus rollout. No new vision-model downloads were required.

Automatic object-region proposals are available through the existing crop assistant.
Students explicitly accept or adjust them, or select the full image; unattended
cropping is not enabled because missed regions can reduce retrieval reliability.
