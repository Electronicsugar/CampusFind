# Phase VIII-A.2 technical closure report — 2 November 2026

Final verification: **153 passed, 3 skipped in 32.65s** in the complete Python
suite; explicit PostgreSQL integration/preflight suite **50 passed in 33.74s**.
All four Node scripts passed after implementation. Relative documentation links
checked successfully. No final failing tests. The three default skips are exercised
by the explicit PostgreSQL suite. The temporary browser smoke server was stopped
after verification; no participant deployment was started.

## Executive decision

**VIII-A.2 engineering completion: PASS (safe preparation and isolated verification).**
**Technical pilot environment: NOT_VERIFIED.**
**Institutional participant authorization: PENDING.**
**Permission to start VIII-B student recruitment: NOT_AUTHORIZED.**

The offline checker, role/outage regressions, installed-model canary, strengthened
restore rehearsal and operator/researcher runbooks are delivered. A dedicated
participant database, restricted non-synced storage, TLS proxy, supervisor and alert
delivery were not provisioned. No authorization for a real pilot database/operator
appointment or participant deployment was established. Those gates remain open;
isolated tests do not close them. Full human researcher U01–U09 rehearsal also
remains pending; executed API/browser technical checks are distinguished below.

No real participants, credentials or photos were collected. No public deployment,
model downloads, telemetry provider, production app changes, migrations, ranking,
preprocessing/cache key changes or ownership/security-rule changes occurred.

## Audit and minimal changes

Reused Settings/serve exact origin and proxy controls, database-backed sessions,
closed production registration, coordinator account issuance, durable jobs/locks,
readiness/operations logs, test UUID schemas, backup snapshot guards and existing
study tasks/templates/tools. Existing schema-3 recognition preparation is unchanged.
[Technical preflight](TECHNICAL_PREFLIGHT.md) gives the reuse/gap/risk/owner table.

The former readiness endpoint checks DB/revision/storage/heartbeat but neither
verifies TLS/ACL nor proves that an explicitly intended database was selected.
scripts.pilot_preflight fills that narrow offline gap: explicit target/profile,
environment-secret name, expected host/port/database/user, separate storage/backup,
placeholder detection, static controls and optional read-only DB role/revision
queries. It deliberately never imports .env or provisions resources. Errors and
status reports omit DSNs and secret values. Configuration PASS is not deployment
PASS. The existing heavyweight fixed-output encoder benchmark was insufficient
for a small readiness check; the optional one-input CLIP/NanoDet canary reuses
installed production encoders without modifying weights or downloading anything.

Existing restoration verified bytes/rows but not restored HTTP access; the offline
drill now also checks migration revision and denies anonymous reports/images/claims.
Its API still accepts no destination DB and generates only new cf_restore_UUID
databases. Existing result destinations are refused before provisioning.

## Changed files

All changes are offline tooling/tests/docs; no production runtime behavior changes.

| File | Purpose / reversibility |
| --- | --- |
| scripts/pilot_preflight.py (new) | Read-only explicit-target checker + opt-in installed-model canary; removable without application impact |
| tests/test_preflight.py (new) | 17 synthetic config, A/B/C, session, HTTPS/logging, outage and canary-failure tests; existing integration fixture reused |
| scripts/recovery_drill.py | Add restored schema/anonymous-denial assertions and result fields; only its disposable execution changes |
| research/phase8/preflight-example.json (new) | Redacted placeholder plan; intentionally fails until operator provides approved configuration |
| docs/phase8/TECHNICAL_PREFLIGHT.md (new) | Gap audit, explicit profiles, least-privilege/Windows procedure, TLS/worker/alerts/reversal |
| docs/phase8/RECOVERY_DRILL_REPORT.md (new) | Executed drill commands/results/cleanup and unverified operational failure modes |
| docs/phase8/RESEARCHER_DRY_RUN.md (new) | U01–U09 fixture mapping, technical rehearsal evidence and pending human/accessibility tasks |
| docs/phase8/PHASE8A2_REPORT.md (new) | This report |
| docs/phase8/PILOT_ENVIRONMENT.md | Link explicit profiles and executed-vs-pending isolation evidence |
| docs/phase8/PILOT_READINESS_CHECKLIST.md | Add bounded technical checks; retain unchecked participant/approval gates |
| docs/phase8/PRIVACY_AND_SAFETY.md | Pending human-decision register with roles/evidence/consequences |
| docs/phase8/SECURITY_RELIABILITY_MATRIX.md | Exact new test references and limits |
| reports/phase8a2-recovery.json (new) | First successful guarded restore measurement |
| reports/phase8a2-recovery-auth.json (new) | Successful extended restore including revision and auth checks |

## Environment and security verification

No dedicated participant DB/roles/storage was created; safe operator SQL and
PowerShell instructions explicitly require approved NEW targets and fresh secrets.
App and migration roles are separate in the plan. Tests use random disposable
PostgreSQL schemas and temporary directories. The existing portable server was
not stopped for outage testing. Private test artifacts outside the repository
use temporary test roots; actual service ACLs/cloud-sync exclusion remain unverified.
The repository remains cloud-synced and unsuitable for participant private storage.

Three-user integration exercises A LOST reporter/claimant, B FOUND reporter/finder,
C unrelated authenticated user. Authorized actions succeed, C direct known-ID claim
actions/evidence and notifications are denied; A cannot edit B, B cannot confirm
receipt, A can return, duplicate return is 409, deleted photos are denied. Active
reports/images are intentionally visible to signed-in cohort members, not private
between participants. Evidence stays private. Existing anonymous, admin, concurrent
approval, retention, rate-limit and model-failure tests were reused.

Production-mode HTTPS TestClient verifies Secure/HttpOnly/SameSite cookies, wrong
Host/origin and missing-CSRF rejection, closed registration, and operational log
messages without fixture password/email/token. Forged forwarded headers do not
override cookie policy in that fixture; launcher parser rejects wildcard trust.
This is not a live Uvicorn reverse-proxy spoofing/handshake test. Actual trusted
certificates, forwarded-header routing, network admission and log ACL are NOT_VERIFIED.

## Recovery and model evidence

[Recovery report](RECOVERY_DRILL_REPORT.md) records each scenario, expected/actual
result, isolation, command, cleanup and residual risk. Executed: atomic failure
tests, mocked client connection failure, real fixture expiry/relogin, isolated
engine SQL-error/recovery, actual PostgreSQL worker-process crash/locks and guarded
backup/restore. Simulations are explicitly not live network outages or packet drops.
Queued-work resumption after a real DB connectivity outage remains unverified.

First restore: 1 report/2 photos/evidence, corruption rejection, exact new DB cleanup,
2.897s. Extended restore additionally verifies schema revision and anonymous HTTP
denials, 1.866s. Second invocation with the old output filename refused as expected.
No real backup/destination overwritten. Restoring to fresh disposable databases is
verified; encrypted off-machine delivery, RPO/RTO and operational deletion/session
revocation after real restore are not. Retention/deletion regression checks passed;
backup erasure requires separate approved policy and deletion ledger.

Real installed CLIP/NanoDet canary passed on one generated frame: load 1.388s,
combined inference 0.108s. No downloads/accuracy or capacity claim. Failure stages
distinguish missing artifact, load and runtime failures. Missing/incorrect artifact
contents can be a load failure; the checker cannot diagnose every configuration
cause without exposing internal errors. Production worker supervision/alerts remain
unverified despite durable worker tests and heartbeat implementation.

## Researcher rehearsal and accessibility

Technical API rehearsal covered two-photo LOST/FOUND, explicit confirmed selections,
private claim, finder approval, claimant return/duplicate denial, notification
boundaries and session retry. Existing pagination and student-journey tests are
reused. Human instruction comprehension/assistance consistency and U01–U09 timing
were not measured. Existing TEST ONLY observation file validated again; its values
remain fictional examples, not new observed results. No model output was injected.

Fresh isolated browser: homepage, login-gated report CTA and gallery rendered;
320px menu opened with Enter, Escape collapsed/restored focus to menuToggle;
document/client widths both 305px at nominal 320, both 753px at nominal 768;
desktop route smoke at 1280px. Override reset afterward. This was not a new full
two-role browser journey. Actual screen reader, 200%/400% zoom, touch devices,
complete contrast, reduced-motion visual and reporting/dialog keyboard audits are
pending. Existing relevant Node regression scripts passed. No WCAG certification.

## Fresh baseline and final verification

Baseline: **136 passed, 3 skipped**, 24.50s; PostgreSQL **33 passed**, 27.56s;
four Node scripts passed. Default skips are PostgreSQL-specific and covered by
the explicit PostgreSQL run. No baseline failures.

Intermediate final suite before the last two tests: **151 passed, 3 skipped**,
28.32s, all four Node scripts passed. New targeted suite after all additions:
**17 passed**, 2.58s. Earlier PostgreSQL extended run with 13 new cases: **46
passed**, 30.51s. Final full/PostgreSQL results are appended below once completed.

Initial new-test failures: checker raised SQLAlchemy ArgumentError on a missing
secret, fixed to a redacted FAIL; authorization test used an incomplete PATCH and
received 422, corrected to a valid payload and verified 403. No production auth
defect was inferred or patched. Final results do not conceal these corrections.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:CAMPUSFIND_TEST_POSTGRES='true'
try { .\.venv\Scripts\python.exe -m pytest tests/test_platform.py tests/test_pilot.py tests/test_preflight.py -q }
finally { Remove-Item Env:CAMPUSFIND_TEST_POSTGRES -ErrorAction SilentlyContinue }
node tests/frontend_app.cjs
node tests/frontend_selection.cjs
node tests/frontend_presentation.cjs
node tests/frontend_handover.cjs
.\.venv\Scripts\python.exe -m scripts.pilot_preflight --canary
.\.venv\Scripts\python.exe -m scripts.pilot_preflight --config research/phase8/preflight-example.json
.\.venv\Scripts\python.exe -m scripts.recovery_drill --output reports/phase8a2-recovery-auth.json
.\.venv\Scripts\python.exe -m scripts.study_results research/phase8/observations-TEST-ONLY.csv
.\.venv\Scripts\python.exe -m scripts.ui_test_server
```

The example config intentionally returns FAIL for placeholders/missing secret/dirs.
The existing recovery result path now intentionally refuses repeat execution;
use a new result filename for a new guarded drill. Canary and successful restore
commands above were actually executed; no dedicated-pilot --connect check ran.
No environment blocked the isolated checks. Actual pilot checks were NOT_EXECUTED
because no approved target/service/TLS environment was established, not because
passing tests certified it. No external attacks/scans were performed.

## Gates and outstanding responsibility

| Gate | Status | Evidence | Outstanding action | Responsible role (appointment not inferred) |
| --- | --- | --- | --- | --- |
| A regression | PASS | Fresh isolated suites and no app behavior edits | Retain evidence on approved deployment | Maintainer |
| B privacy | PARTIALLY_VERIFIED technically; authorization PENDING | Direct access/retention tests; procedures | Verify actual private ACL/storage and approve consent/retention | Privacy custodian/institution |
| C pilot environment | NOT_VERIFIED | Tested preparation checker, disposable DB tests | Authorize/provision dedicated restricted PostgreSQL/TLS/storage; execute read-only preflight | Authorized operator/network team |
| D measurement | PARTIALLY_VERIFIED | Existing tool validates, API/browser technical rehearsal | Human moderator U01–U09 dry run, remaining accessibility checks | Study/accessibility lead |
| E recognition prep | PASS for preparation | Existing VIII-A protocol/validator retained; installed canary | Collect independently reviewed data only in authorized future phase | Evaluation lead |
| F operations | PARTIALLY_VERIFIED; launch BLOCKED | Worker crash tests and real disposable restore | Supervisor, alerts, contacts, deployed recovery rehearsal and acknowledgement | Operations/incident lead |

No real-student gate is marked ready. The original readiness checkboxes for
institutional decisions, secure deployed environment and human rehearsal stay
unchecked. Known VII limitations and task mappings remain unchanged.

## Remaining blockers and exact handoff

Technical/operational: no dedicated least-privilege target or non-synced service
storage/backup ACL verified; live TLS/proxy/admission, role grants, worker supervisor,
alerts, real network-upload recovery and post-outage queued recovery unverified.
Accessibility: real device, screen reader/zoom/contrast and affected-task disposition
pending. Research: complete human moderator dry run and deterministic actual
uncertain fixture availability pending. Institutional: approval, consent, artifact
retention, withdrawal/incident contacts, operator/researcher appointments pending.

Next action: campus coordinator authorizes a named operator and a NEW restricted
researcher-only environment target. Operator follows TECHNICAL_PREFLIGHT, verifies
secret isolation, grants/ACL/TLS/service settings and executes remaining actual
checks with recorded evidence. Named researchers then rehearse U01–U09 with staged
objects and record genuine observations. Resolve critical barriers and obtain
written institutional recruitment/data authorization before any VIII-B activity.
Do not proceed to VIII-C or promote experimental retrieval.
