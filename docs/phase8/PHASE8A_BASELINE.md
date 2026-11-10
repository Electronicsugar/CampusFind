# VIII-A baseline and gap analysis — 2 November 2026

No production code changes are planned. This is preparation, not recruitment or
recognition validation. The repository is a local working folder without Git;
therefore no commit-based diff or revision claim is available.

## Actual implementation

- [main.py](../../backend/main.py) serves `/`, `/gallery`, `/lab` and vision routes;
  [platform.py](../../backend/platform.py) installs application routers and assets.
- [auth.py](../../backend/auth.py): register/login/me/logout/profile under
  `/api/v1/auth`, Argon2 hashes, database sessions, CSRF, origin and throttling.
- [reports.py](../../backend/reports.py): items CRUD/state, private image access,
  validated 1–4 photos, explicit crop/full-frame selections and expiry.
- [matching.py](../../backend/matching.py), [worker.py](../../backend/worker.py):
  durable jobs, cached embeddings and existing CLIP/category ordering.
- [claims.py](../../backend/claims.py): private claims, approve/reject/withdraw/return,
  notifications and read actions. Finder/admin reviews; claimant confirms receipt
  or an admin records a verified handover with a note. No self-review approval.
- [admin.py](../../backend/admin.py): moderation/audit; [operations.py](../../backend/operations.py):
  liveness/readiness, role-protected operations and low-cardinality logs.
- [models.py](../../backend/models.py), [database.py](../../backend/database.py):
  PostgreSQL, transactions, lock limits and test-only SQLite. Three migrations:
  initial, pilot operations and matching cache. No new migration needed.
- [storage.py](../../backend/storage.py): re-encoded private files and durable cleanup;
  production access requires exact HTTPS origin, Secure cookies and explicit storage.
- Frontend app.html/app.css/app.js/app-ui.js, shared detection.js and inline research
  pages preserve Phase VII behavior. [Phase VII results](../PHASE7_RESULTS.md)
  records browser evidence and limitations; it is historical evidence.

## Reuse versus new work

| Requirement | Existing facility | Decision / gap |
| --- | --- | --- |
| Instance/model/report IDs, query/gallery roles | evaluation/dataset.py schema 3, integrity.py | Reuse unchanged |
| No-match, labeled hard negatives, metrics | positive_ids/relations; metrics.py; report_retrieval.py | Reuse; add collection completeness checks only |
| Split/file/pixel/session/provenance/pHash checks | integrity.screen_splits, catalog CLI | Reuse, do not prohibit valid same-partition retrieval pairs |
| JSON metrics/model fingerprints | phase6.py, run.py, phase3.py | Reuse; no new scoring engine |
| Synthetic browser fixtures | scripts/ui_test_server.py | Regression only; not a PostgreSQL participant pilot |
| Controlled accounts, backup/restore, retention | create_pilot_user.py, backup.py, recovery_drill.py, worker.py | Reuse operations runbook; no live reset |
| Usability tasks/results schema | No equivalent found in inspected scripts/docs | Add documents, CSV templates and offline scripts.study_results |
| Required capture fields/explicit no-match/portable collection paths | Schema 3 permits incomplete capture annotations | Add evaluation.collection wrapper; legacy readers unchanged |
| Participant approvals/secure hosting | Operations guidance exists, deployment approval evidence absent | Document pending gates; do not provision or infer approval |

## Fresh baseline

Executed from project root with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:CAMPUSFIND_TEST_POSTGRES='true'
try { .\.venv\Scripts\python.exe -m pytest tests/test_platform.py tests/test_pilot.py -q }
finally { Remove-Item Env:CAMPUSFIND_TEST_POSTGRES -ErrorAction SilentlyContinue }
node tests/frontend_app.cjs
node tests/frontend_selection.cjs
node tests/frontend_presentation.cjs
node tests/frontend_handover.cjs
```

Baseline: **118 passed, 3 skipped**, 24.54s; PostgreSQL **33 passed**, 29.02s;
all four Node scripts passed. The default skips are PostgreSQL-specific tests,
exercised in the explicit PostgreSQL run. No observed baseline failures or warnings.
Tests create temporary SQLite databases or random cf_test_ PostgreSQL schemas and
drop only those disposable schemas. Existing real reports were not fixtures.

Read the final [report](PHASE8A_REPORT.md) for post-addition checks. No model benchmark
was run, and historical accuracy or synthetic workflow evidence is not independent
recognition evidence.
