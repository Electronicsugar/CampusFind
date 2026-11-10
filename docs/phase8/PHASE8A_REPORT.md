# Phase VIII-A completion report — 2 November 2026

Final verification addendum: complete suite **136 passed, 3 skipped in 27.82s**.
All 18 new tool tests pass. PostgreSQL baseline **33 passed** and four Node
scripts pass as recorded below. Relative documentation links checked successfully.
The isolated browser test server was stopped after the smoke check.

## Executive decision

**Phase VIII-A engineering completion: PASS.** Preparation, offline measurement
validation, dataset collection checks, procedures and regression evidence are
delivered. **Authorization to begin real-student testing: BLOCKED.** Campus
approval/consent decisions and a secure dedicated participant deployment have not
been verified. Engineering completion does not authorize recruitment.

No participants were recruited, no participant observations collected, no AI
accuracy measurements claimed, no public deployment performed, and no production
application code, ranking, preprocessing, thresholds, cache keys, claims or security
rules were changed. VIII-B/C remain future work.

## Findings and reuse

[Baseline and gap analysis](PHASE8A_BASELINE.md) maps actual modules, routes,
migrations and reuse decisions. Historical pilot work already includes closed
production registration, controlled account issuance, durable workers, readiness,
privacy-conscious operational logs and guarded backup/restore scripts. These
are implementation facilities, not proof of deployed campus safeguards.
Schema-3 evaluation already distinguishes partition from retrieval role, enforces
instance/provenance isolation and checks relations, groups and near duplicates.
Duplicating that harness would risk inconsistent labels; the new wrapper only
adds collection completeness requirements. Historical VII counts matched fresh
baseline tests. Important discrepancy: the development workspace is cloud-synced,
which is unsuitable for participant photo/observation storage without relocation.

## Files added and purpose

All entries below are new offline/documentation files; production runtime behavior
is unchanged. No dependency or migration was added.

| File under project root | Purpose |
| --- | --- |
| docs/phase8/PHASE8A_BASELINE.md | Architecture audit, reuse decisions, baseline commands and isolation |
| docs/phase8/PILOT_ENVIRONMENT.md | Deployment boundaries, dedicated PostgreSQL/storage, recovery |
| docs/phase8/PRIVACY_AND_SAFETY.md | Consent, pending decisions, withdrawal, incident stop/escalation |
| docs/phase8/PILOT_READINESS_CHECKLIST.md | Evidence-based preflight and unresolved VII limitations |
| docs/phase8/USABILITY_STUDY_PROTOCOL.md | Two-stage study, observer procedure, assistance/timing/error rules |
| docs/phase8/USABILITY_TASKS.md | U01–U09 instructions, roles, fixture state, outcomes and cleanup |
| docs/phase8/OBSERVATION_DICTIONARY.md | CSV fields, denominators, missingness, privacy and tool usage |
| docs/phase8/DATASET_COLLECTION_PROTOCOL.md | Capture/identity methodology and schema-3 collection extension |
| docs/phase8/EVALUATION_DESIGN.md | Frozen independent evaluation and reproducibility requirements |
| docs/phase8/SECURITY_RELIABILITY_MATRIX.md | Actual test references, deployment gaps and blocking preflights |
| docs/phase8/PHASE8A_REPORT.md | This completion evidence and handoff |
| research/phase8/observations-empty.csv | Empty allowlisted observation template |
| research/phase8/observations-TEST-ONLY.csv | Fictional tool example, explicitly excluded from study evidence |
| research/phase8/manifest-TEST-ONLY.json | Schema illustration with no fabricated photographs |
| scripts/study_results.py | Offline validation and deterministic per-task counts/durations/comprehension |
| evaluation/collection.py | Completeness preflight reusing existing schema/file/label/split integrity |
| tests/test_phase8.py | Synthetic valid/invalid/empty/duplicate/privacy/CLI/partition regression cases |

## Study and dataset preparation

The protocol plans a 3–5 participant formative shakedown and approximately 8–12
additional participants after approved revisions. These are planning targets, not
sample-size guarantees. Observation CSV records pseudonymous session/task, input,
completion/help, measured/estimated time, errors, four comprehension decisions,
difficulty and coded notes. It rejects additional/private columns and free text;
observer redaction review still matters. No live telemetry or analytics collector.

Collection plans 30–50 physical units initially, multiple categories and distinct
units of identical models, varied captures and independently specified no-match
galleries. Same-partition query/gallery positives are permitted; cross-partition
instance/source/report/session reuse is rejected. Existing metrics and model/cache
fingerprints remain authoritative for future VIII-C. The illustrative manifest
references missing images deliberately and cannot be scored as evidence.

## Verification

Exact baseline commands and results: [baseline](PHASE8A_BASELINE.md). Baseline
118 passed / 3 skipped (24.54s), PostgreSQL 33 passed (29.02s), four Node scripts
passed. No failures. Default skips are PostgreSQL-only checks covered explicitly.
The PostgreSQL fixtures use random disposable schemas; SQLite uses temporary files.
No populated app database was reset or destructively tested.

After implementation, complete Python suite: 135 passed / 3 skipped (27.93s),
with the first 17 new tests. After adding CLI failure coverage, targeted new suite:
18 passed (1.24s). Final complete-suite count is recorded in the verification
addendum below. All four Node scripts passed again after implementation.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase8.py -q
.\.venv\Scripts\python.exe -m pytest -q
node tests/frontend_app.cjs
node tests/frontend_selection.cjs
node tests/frontend_presentation.cjs
node tests/frontend_handover.cjs
.\.venv\Scripts\python.exe -m scripts.study_results research/phase8/observations-empty.csv
.\.venv\Scripts\python.exe -m scripts.study_results research/phase8/observations-TEST-ONLY.csv
.\.venv\Scripts\python.exe -m evaluation.collection --development research/phase8/manifest-TEST-ONLY.json --independent research/phase8/manifest-TEST-ONLY.json
```

Empty template returned zero sessions/records and no validation errors. TEST ONLY
observation example validated; its numerical summary is fictional fixture output,
not study results. Collection illustration failed as expected with “Dataset image
missing”; this negative check verifies it cannot become invented accuracy evidence.
Synthetic temporary image fixtures exercise valid matched/no-match pairs, same-model
different-unit negatives, cross-partition leakage, conflicting models, duplicates,
missing annotations and paths. No encoder inference/download is needed.

Focused fresh browser smoke used scripts/ui_test_server.py on localhost:8017:
homepage rendered, lost-report CTA required login without exposing images, gallery
initialized controls, lab initialized both editors. No accounts/participant data
were used. Full two-role browser journey, device/accessibility and interruption
testing were NOT repeated in VIII-A because runtime behavior was unchanged;
their VII evidence is historical, and relevant regressions passed automatically.
No recognition benchmark, destructive restore, live TLS proxy, real-device or
screen-reader audit was executed. No environmental test blocker was encountered;
undeployed campus safeguards are readiness gaps, not software test failures.

## Readiness gates

| Gate | Status | Evidence | Blocker / next action |
| --- | --- | --- | --- |
| A regression integrity | PASS | Fresh Python/PostgreSQL/Node, synthetic tool tests, focused browser smoke | No unexplained regression; retain runtime behavior |
| B participant privacy | BLOCKED | Data boundaries, stop/withdrawal/consent procedures and safe template | Campus authorization, approved retention, custodian and contacts pending |
| C pilot environment | NOT_VERIFIED | Existing operations guide and new isolation procedure | Deploy restricted dedicated PostgreSQL/storage/HTTPS, then verify preflight |
| D measurement readiness | PASS_WITH_WARNINGS | Task cards, dictionary, empty/example CSV, tested summarizer | Researcher-only dry run needed; small-sample/observer bias remains |
| E recognition evaluation preparation | PASS_WITH_WARNINGS | Existing schema-3 harness, capture protocol, tested collection wrapper | Real consented independent photographs absent; no accuracy conclusion |
| F operational readiness | BLOCKED | Matrix/checklist and recovery/incident procedures | Designate operators; verify proxy, worker, access, restore and incident escalation |

## Security, limitations and VIII-B handoff

Preserved controls include auth/CSRF/origin/role boundaries, expiry, image/evidence
authorization, transactional claims and audited state changes. Automated tests
support those claims in isolated environments; they do not certify production
security. No new vulnerability was established by this preparation review. Live
TLS/proxy, restrictive hosting, encrypted backup delivery, deletion replay and
accessibility support are unverified and must not be assumed safe.

Known VII issues are explicitly mapped to study tasks in the checklist: duplicate
per-photo match cards, scoped dashboard counts, memory-only drafts, edit/crop draft
loss, old claim pagination, manual matching refresh, uncertainty category placement,
original review thumbnails and incomplete accessibility/device testing. These were
not silently redesigned. The tools validate structure/labels, not honest identity
annotations, complete de-identification or visual identifiability. Unknown labels
need review. Existing load_manifest reads image files before collection-specific
path checks; run only on trusted local study manifests, not untrusted uploads.

Next action: the campus study coordinator reviews this pack, appoints the operator
and privacy custodian, settles authorization/ethics/retention/contact decisions,
and assigns a dedicated non-synced pilot environment. Operator then completes
the unchecked readiness items and a researcher-only dry run. Only explicit campus
clearance permits VIII-B recruitment. VIII-C requires separately collected,
reviewed independent photographs and frozen evaluation settings. Neither starts here.
