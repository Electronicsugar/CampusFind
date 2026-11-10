# Phase 5 prioritized audit

Scope: authentication, all platform/legacy endpoints, models/migrations, storage,
worker, matching, frontend, startup and operator scripts. Existing ranking and
private evaluation data are out of scope for modification.

## Confirmed issues, before changes

1. High: claims listing and administrator report listing can return expired text
   before retention cleanup. Authorization must enforce retention independently.
2. High: legacy multipart inference endpoints lack a total incoming-body limit;
   endpoint file checks happen after parsing/spooling. Bound all API requests.
3. Medium: file deletion after database commit can fail, returning a server error
   with no immediate durable retry record. Partial upload writes can leave files.
4. Medium: concurrent crop/delete/close versus matching can use stale candidate
   rows; matching needs a consistent lock protocol with report mutations.
5. Medium: public registration cannot verify campus membership. A pilot needs a
   controlled admission option, with SSO/email verification remaining prerequisites
   for open enrollment. Domain restriction alone is insufficient.
6. Medium: no explicit trusted-host/proxy launch policy, readiness/worker heartbeat,
   structured operational telemetry or tested backup-plus-photo restoration.
7. Performance: browse performs one image query per item. Matching performs image
   and existing-pair queries inside nested loops, recomputes appearance in both
   directions and encodes discarded thumbnails. Measure before optimizing.
8. UX: generic errors can lose actionable network context; forms lack consistent
   busy announcements; stale asynchronous crop selection can affect navigation.

Existing strengths: parameterized ORM queries, escaped dynamic HTML, private image
authorization, opaque hashed revocable sessions, Argon2id, origin/CSRF checking,
upload decode/re-encode, claim constraints/row locks, no identity probabilities.

## Execution and safety

Add regression tests for findings; run old tests after substantive stages. Use
randomized, guarded PostgreSQL schemas for workloads and migrations. Recovery uses
fresh disposable databases, never restores into the application database. No
public deployment, benchmark-photo modification or new model download.

Measure 100/1,000/5,000 report workloads using synthetic images and deterministic
encoder doubles, explicitly separating infrastructure timings from real CLIP
inference. Record real encoder timing separately where available. Preserve raw
results and report failures/limits. Do not infer physical-instance accuracy.
