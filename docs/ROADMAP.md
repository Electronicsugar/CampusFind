# Agreed implementation roadmap

1. Current: local comparison lab, manual crop, original vs normalized SIFT baseline, inspect feature correspondences.
2. Next: collect different objects including identical product models; measure Recall@1, Recall@5 and false matches on unseen objects. Add DINOv2 candidate retrieval, compare LightGlue reranking, and support multiple views. No visible similarity percentages or blanket low-score exclusion from browsing. No identity claims from retrieval rank. Add assisted detection with manual correction after retrieval evaluation.
3. Full-stack foundation: React/Tailwind interface, FastAPI services, PostgreSQL and image storage, campus institutional-email authentication, lost/found reports and search. The current lightweight lab is temporary research UI.
4. Paper matching and notifications: use category, description, dates and location as supporting signals. Separate broad browsing from selective notification thresholds. Unread counts and notification history.
5. Claims: multiple claim requests, private claimant–finder/custodian conversations, evidence-based approval. Approving one rejects remaining pending claims atomically. Archive conversations as read-only after resolution. Finder/custodian is distinct from the unknown rightful owner.
6. Lifecycle: OPEN, PENDING, CLAIMED, UNRESOLVED, ARCHIVED. Ten-day no-claim expiry from the paper; configurable owner/custodian adjudication timeout; scheduled checks; administrator escalation, dispute review and audit history.

The paper's implemented matching uses metadata. Robust image instance retrieval is our evaluated extension, not a reported result from the paper. Two photographs alone cannot establish retrieval accuracy. Same-model hard negatives, changed backgrounds, low light, distance, rotation, partial views, and absent-target queries are required.

21 October 2026 update: first assisted-cropping increment implemented and tested.
NanoDet offers reviewed regions; all gallery photos require an explicit selection.
The full detector comparison is incomplete: Grounding DINO weights could not be
downloaded completely from the CDN, and SAM 2 is deferred. See PHASE1_RESULTS.md.
This does not validate instance retrieval or authorize advancing to campus workflows.

Retrieval experiment update: reproducible instance-labeled development harness,
independent-split leakage checks, preprocessing/fusion comparison, CPU DINOv2-small
comparison, development-only abstention fits and SIFT diagnostics are implemented.
No independent dataset is available, so ranking/model/preprocessing defaults remain
unchanged. Bounded descriptor caching is enabled after exact output-invariance
checks and measured latency reductions. See EVALUATION.md and RETRIEVAL_RESULTS.md.

Do not publish a website until requested. Develop each milestone locally and inspect results before advancing.

Milestone 02 implemented: local session gallery at /gallery; up to 12 candidates; per-image crop; coarse appearance ranking; optional percentages; keep low-score results; N/A at end; individual upload errors. No persistence or learned matching yet. Next evaluate with same-model negatives before upgrading retrieval.

Content relevance upgrade implemented: local CLIP model, semantic cosine ranking, separate relevant/uncertain/excluded candidates, and actual chart-vs-earbuds regression. Appearance percentages are diagnostics only. Continue with independent hard-negative evaluation before campus workflows.
