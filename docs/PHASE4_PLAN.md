# Phase 4 implementation plan and audit

The repository has FastAPI handlers in backend/main.py, a standalone gallery, a pair-comparison page, and isolated evaluation tooling. There is no persistence or authentication. The existing vision functions validate uploads and accepted crops; CLIP ranking orders category sections then visual similarity and appearance tie breaks. We will reuse those functions and preserve all benchmark data.

## Architecture

PostgreSQL is the application database, accessed by SQLAlchemy 2 and versioned with Alembic. SQLite is permitted only in explicit automated test configuration. Application startup does not create tables or silently substitute a database. Database failure produces a service-unavailable response while the legacy vision lab remains usable.

Tables: User (private email, display name, Argon2id hash, student/admin role); Session (hashed random token, CSRF token, expiration); Item (owner, LOST/FOUND, public description/category/approximate location/date, state, visibility, consent and retention dates); ItemImage (private random storage key, selected crop, content/model/preprocessing cache key and descriptor); ClaimRequest (claimant, found item, private evidence and status); Notification (recipient, type, item/claim link, read time); ModerationRecord (actor, action, entity IDs, non-sensitive audit detail). MatchSuggestion and MatchJob provide persisted potential matches and durable retry state. RateLimit stores shared fixed-window counters, avoiding per-process authentication throttling bypass.

Private images are decoded, EXIF-oriented and re-encoded with metadata stripped, stored outside static files, and served through authenticated authorization checks. Original filenames and storage keys are never returned. Crop acceptance and retention consent are explicit. Deletion withdraws public visibility and removes photos/descriptors; minimal action records remain.

Authentication uses opaque database-backed revocable HttpOnly cookies, SameSite=Lax, strict Origin checks and session-bound CSRF tokens for writes. Registration/login also require a same-origin request. Secure cookies are required outside explicit local HTTP development. Students cannot assign themselves roles. Admin promotion is a local operator command. Optional campus domain allowlisting is supported; it does not establish verified campus-email ownership or SSO.

State changes and claims use database transactions and row locks. Finder/admin approval checks pending claims; conflicting claims cannot both win. A claimant records receipt to confirm return; admins may record a documented handover. No visual score approves a claim. Private evidence is visible only to its claimant, the finder, and admins.

Matching remains CLIP with the existing category gates. Each accepted photograph produces a separately ranked list of candidate photographs, grouped by query photograph in the UI; no unvalidated multi-view score fusion is introduced. Closed/returned/hidden items are excluded, including stale saved results. Embeddings use content + model + preprocessing keys. Matching failure leaves reports saved and retryable, never rejected. A durable worker processes jobs; submitting a report also attempts its queued work in a background task for local convenience.

## Increments and checks

1. Schema/migrations and environment configuration; apply PostgreSQL migrations and test rollback on a disposable database.
2. Authentication/session/CSRF/authorization; test passwords, duplicate accounts, logout, role denial and throttling.
3. Reports and image persistence; test ownership, multipart validation, metadata stripping, crops and state transitions.
4. Matching integration; test with deterministic synthetic encoder fixtures and keep real retrieval evidence separate.
5. Claims and audit; test review permissions, conflicting transitions, private evidence, return confirmation.
6. Recipient-only notifications and read status.
7. Responsive HTML/CSS/JS landing/auth/report/browse/detail/dashboard/claims/notification/admin views; preserve /gallery and move pair lab to /lab.
8. Full regression suite, PostgreSQL integration, security tests and live UI checks. Document deployment limitations and local Windows setup.
