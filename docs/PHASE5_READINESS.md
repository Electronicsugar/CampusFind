# Phase 5 pilot-readiness report

Report completed 27 October 2026. Performance and recovery measurements were
recorded 23 October; regression checks were repeated on 27 October.

**Overall: PARTIALLY READY.** The local application has tested security, storage,
worker and performance improvements. Campus deployment still requires operator
configuration and verification. Physical-object recognition remains experimental.
No public deployment, new model download or production ranking change was made.

## Readiness by area

| Area | Status | Evidence and remaining requirement |
| --- | --- | --- |
| Student workflows | READY for tested local scope | Accounts, multi-photo reports, matches, private claims, review, receipt, notifications and retention exercised through API workflows. |
| Security | PARTIALLY READY | Confirmed audit findings fixed with regressions; independent penetration testing, dependency review and campus identity/recovery procedures remain outstanding. |
| Storage and transactional reliability | READY for tested local scope | Atomic writes, durable deletion retries, stale-data protection, rollback and worker-crash recovery tested. |
| Backup and recovery | PARTIALLY READY | Isolated logical restoration passed; encrypted off-machine backups, disk-loss recovery and production RPO/RTO remain untested. |
| Performance | PARTIALLY READY | Infrastructure workloads at 100/1,000/5,000 reports and real-CLIP mixed load at 100 reports measured; large balanced galleries and sustained campus traffic untested. |
| Frontend | PARTIALLY READY | Busy/error states, pagination, crop regressions and mobile checks completed; broader assistive-technology and student usability trials remain. |
| Deployment | PARTIALLY READY | Configuration, trusted proxy launcher, health checks and runbook implemented; campus HTTPS, service supervision, storage permissions and monitoring must be installed and verified. |
| Independently validated object recognition | BLOCKED | No adequate held-out dataset spanning different physical units, hard negatives and absent targets. |

READY refers only to the stated tested scope, not an unconditional production certification.

## Audit findings and implementation

The [initial audit](PHASE5_AUDIT.md) records the issues before changes.

| Finding | Change and principal files | Validation |
| --- | --- | --- |
| Expired text/evidence remained visible until worker cleanup | Immediate claim redaction and admin expiry filtering; `backend/claims.py`, `backend/admin.py` | Expired evidence and inaccessible report tests |
| Legacy uploads could be parsed before aggregate size enforcement | Streaming API body bounds and early-response security headers; `backend/platform.py` | Legacy upload limit and production security tests |
| Failed file deletion lacked durable recovery; partial writes could survive | Atomic JPEG writes, deletion queue and conservative orphan cleanup; `backend/storage.py`, `backend/worker.py`, migration 0002 | Interrupted write, deletion retry and orphan tests |
| Matching could race with crop, delete or report state changes | Consistent parent locking, refreshed image versions, guarded retries; `backend/matching.py`, `backend/reports.py` | Equivalence, interruption and PostgreSQL concurrency tests |
| Registration did not verify campus membership | Production self-registration closed; operator enrollment script `scripts/create_pilot_user.py` | Fail-closed registration and configuration tests |
| Missing operational controls | Trusted host/origin validation, explicit proxy IP, health/metrics, worker heartbeat; `backend/settings.py`, `backend/operations.py`, `scripts/serve.py` | Readiness, metrics authorization and host/origin tests |
| Excessive database and image work | Batched image reads and pair writes, persisted descriptors, bounded cache and indexes; migration 0003 | Exact bidirectional scoring/cache regression and benchmark below |
| Form/network and crop interaction issues | Busy announcements, duplicate-submit guard, actionable errors, focus, pagination and stale detection response protection; `frontend/app.js`, `frontend/detection.js` | Frontend regression scripts and browser checks |

Existing hashed sessions, Argon2 passwords, private-image authorization, CSRF/origin
checks, escaped output and decoded/re-encoded uploads are preserved. Authentication,
authorization, invalid input, missing models and concurrent claims remain covered.
This review is not a claim that every possible vulnerability has been eliminated.

## Performance evidence

Raw results: [baseline](benchmarks/phase5-baseline.json),
[optimized](benchmarks/phase5-optimized.json),
[real encoder](benchmarks/phase5-encoder.json),
[real-CLIP mixed load](benchmarks/phase5-mixed-real.json).

Host: Windows, Python 3.14.5, 20 logical/14 physical CPU cores, about 15.6 GiB RAM.
Database fixtures used isolated schemas and temporary storage, removed after runs.
Measurements are single-machine observations, not a capacity guarantee.

### Infrastructure comparison

One photo per report; one lost query against the remaining found reports. The
96×128 synthetic JPEG fixtures repeat 16 images and use a deterministic 512-dimensional
test encoder. Each size includes 10 browse/search requests, 32 requests with eight
concurrent callers, three uploads and one matching job. Search here means the report
browse API, not a new end-to-end visual search.

| Reports | Search median / p95 ms, before → after | Matching seconds, before → after | Matching SQL statements, before → after |
| ---: | --- | --- | --- |
| 100 | 17.80 / 27.75 → 7.81 / 16.57 | 2.430 → 0.331 | 901 → 17 |
| 1,000 | 25.49 / 49.27 → 11.25 / 24.89 | 28.234 → 1.811 | 9,001 → 71 |
| 5,000 | 24.82 / 31.64 → 11.57 / 20.08 | 241.848 → 8.441 | 45,001 → 311 |

Browse SQL statements fell from 28 to 4 per request at every size.

| Reports | Matching CPU seconds, before → after | Peak process RSS MiB, before → after | Concurrent browse median / p95 ms, before → after |
| ---: | --- | --- | --- |
| 100 | 1.500 → 0.172 | 127.44 → 127.71 | 204.68 / 257.91 → 58.30 / 138.20 |
| 1,000 | 18.188 → 1.172 | 132.95 → 131.66 | 215.05 / 356.36 → 77.25 / 212.98 |
| 5,000 | 182.844 → 5.656 | 148.80 → 139.20 | 156.74 / 266.27 → 77.09 / 190.65 |

| Reports | Upload median / p95 ms, before → after | Browse SQL statement median / p95 ms, before → after |
| ---: | --- | --- |
| 100 | 23.95 / 50.04 → 23.38 / 52.20 | 0.16 / 0.46 → 0.34 / 0.57 |
| 1,000 | 26.87 / 43.95 → 32.63 / 43.58 | 0.26 / 0.93 → 0.58 / 1.41 |
| 5,000 | 20.43 / 50.03 → 36.22 / 44.58 | 0.18 / 0.60 → 0.67 / 4.10 |

Fewer, larger SQL statements can take longer individually while reducing total
request time. Uploads did not improve uniformly; durable writes and coordination
have costs. Three upload samples are insufficient for robust tail estimates.

Repeated fixtures benefit the new cache: test-encoder calls fall to 16. The old
test encoder does not emulate CLIP's own internal cache. Therefore the matching
speedup is infrastructure evidence, **not a real-CLIP speedup claim**. RSS excludes
PostgreSQL and browser memory. No repeated trials or confidence intervals were recorded.

### Existing real CLIP on synthetic images

Twenty unique 1024×768 synthetic frames: model load 1.375 seconds; cold encoding
median/p95 69.71/82.73 ms; memory-cache hits 2.01/2.22 ms; CPU 6.344 seconds;
peak process RSS 390.20 MiB. These images have no identity labels.

A separate mixed workload used 100 unique synthetic photos, 50 lost and 50 found
reports, and all 100 queued jobs. The queue completed in 13.432 seconds, producing
5,000 directed pair rows (observed 446.68 jobs/minute). Individual job median/p95
was 33.45/44.19 ms; most jobs reused descriptors prepared by early jobs. The queue
duration includes that initial work. Concurrent browse median/p95 was 61.76/149.95
ms across 64 requests/eight callers. Three two-photo uploads measured 66.08/74.17 ms.
CPU including uploads was 26.172 seconds; peak worker process RSS was 505.59 MiB,
including fixture allocations. This is throughput evidence, not recognition accuracy.

### Preserved behavior and scaling limits

CLIP scores, category gates, directional relevance, tie breaking and human ownership
review are unchanged. Cache signatures include content hash, crop, model and
preprocessing versions. Persisted appearance descriptors avoid repeated decoding;
pair writes are batched and per-job memory caching is bounded. Pagination preserves
ranking order. Tests compare both scoring directions and multi-image behavior.

One PostgreSQL advisory lock bounds matching-job concurrency. A 300-second job
budget is checked between batches; it cannot interrupt a hung native inference call.
Pending jobs recover after process death; failed jobs require explicit retry.
All-pairs storage still grows with lost photographs × found photographs. The
5,000-report experiment is not a balanced 2,500-by-2,500 workload. No approximate
vector index or changed candidate shortlist was justified by these measurements.
Large, varied, multi-photo sustained workloads remain necessary before scaling.

## Backup, migration and crash recovery

`scripts/backup.py` coordinates application writers with a database advisory lock,
exports a consistent snapshot, copies referenced photos, checks content hashes and
writes a completion manifest. Incomplete backups are rejected. The manifest does
not provide encryption or authenticity. External writers and older application
versions must be stopped or coordinated separately.

The [final recovery drill](benchmarks/phase5-recovery-final.json) restored one
synthetic report and two photos, preserved private evidence, rejected deliberate
corruption and removed both disposable databases: **3.302 seconds**. An initial
restore failed because the fresh database already contained an empty public schema;
the drill now verifies that schema has no tables before removing it for restoration.
Successful restoration was then repeated. No live database was restored or destroyed.
A private pre-migration backup was retained; real user records were not test fixtures.
Additive migrations were applied and Alembic reported no schema drift.

Regression tests cover transactional interruption and an actual worker subprocess
exiting abruptly; the pending job can subsequently run again. Restoration timing
for this tiny fixture is not a production recovery-time objective.

## Verification

- Full Python suite on 27 October: **98 passed, 3 skipped**, 24.69 seconds.
  Skips require PostgreSQL and are exercised by the separate database run.
- PostgreSQL platform/pilot suite on 27 October: **32 passed**, 31.91 seconds,
  including the PostgreSQL-only concurrency and crash checks.
- `node tests/frontend_selection.cjs`: passed crop selection, confirmation,
  asynchronous suggestion and side-by-side comparison regressions.
- `node tests/frontend_app.cjs`: passed CSRF, network recovery, busy-state,
  duplicate-submission and escaped-text checks.
- Browser inspection on 23 October: mobile report form at 390×844 had no horizontal
  overflow; keyboard crop controls and main-content focus were checked. No console
  errors were observed. [Saved preview](../reports/phase5-preview.png).

The full student journey is an API integration test with a synthetic encoder:
register two students, submit multi-photo lost/found reports, generate suggestions,
inspect notifications, submit private evidence, approve, confirm receipt, delete,
expire and purge. Browser inspection supplements it; this is not a fully automated
browser journey or a screen-reader certification.

The 27 October sandbox attempt failed to create pytest temporary directories;
the full suite passed outside that restriction. This was an environment failure,
not an application assertion failure. Historical benchmark results were retained
rather than presented as newly rerun measurements.

## Deployment prerequisites and remaining risks

Follow [Pilot operations](PILOT_OPERATIONS.md) for exact variables, startup,
migration, backup and rollback procedures. Before accepting campus traffic:

1. Configure campus HTTPS, a trusted reverse proxy, secure cookies, exact origin,
   restricted storage permissions and protected database credentials.
2. Install web/worker service supervision and verify restart, heartbeat, queue-age,
   deletion-backlog and disk-space monitoring. Readiness checks do not load models;
   perform a model smoke test separately. Process metrics reset after restart.
3. Use verified operator enrollment. Open self-registration remains disabled in
   production; campus SSO/email verification and account recovery are unresolved.
4. Implement encrypted off-machine backups, retention/deletion obligations and a
   rehearsed restore-and-session-revocation process. Agree production RPO/RTO.
5. Run a campus security/dependency review and a small supervised student trial.
   About 100 active reports is a cautious starting recommendation, not an enforced
   limit or a validated maximum. Increase only after measuring actual workloads.

## Recognition evidence still needed

The earlier three development queries concern one physical object and cannot
establish general accuracy. Category gates can still mark correct results uncertain;
this phase deliberately does not introduce unvalidated thresholds or exceptions.
Similarity is never an identity probability or proof of ownership.

Collect consented photos of multiple physical units of the same product across
several categories, including smooth objects and units with scratches/stickers.
For each unit include different angles, lighting, backgrounds, scales and occlusion.
Include unrelated candidates, hard lookalikes and queries whose object is absent.
Maintain physical-unit labels and separate development and held-out evaluation
groups; never reuse tuning photos as independent evidence. Use the existing
[evaluation framework](EVALUATION.md) to compare retrieval and no-match policies.
Until that evidence exists, retain the current ranking and human verification.

## Reproducing verification

Run from the repository with the documented local database available:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:CAMPUSFIND_TEST_POSTGRES='true'
.\.venv\Scripts\python.exe -m pytest tests/test_platform.py tests/test_pilot.py -q
Remove-Item Env:CAMPUSFIND_TEST_POSTGRES
node tests/frontend_selection.cjs
node tests/frontend_app.cjs
```

The benchmark entry points are `scripts.pilot_benchmark`,
`scripts.benchmark_encoder`, `scripts.pilot_mixed_load` and
`scripts.recovery_drill`. Inspect their help and use new result paths; retain
historical files. Infrastructure and recovery scripts use guarded disposable
schemas/databases. Run only against the documented local test service.
