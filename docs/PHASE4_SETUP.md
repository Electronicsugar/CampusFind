# CampusFind local MVP

The application now has PostgreSQL-backed accounts, reports, multi-photo uploads, object selection, potential matches, private claims, notifications and moderation. `/` is the website; `/gallery` remains the original gallery and `/lab` the pair-comparison tool. Experiments and real-photo benchmark datasets are unchanged.

## Windows setup

From the repository root:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe scripts/setup_local.py
docker compose up -d
.venv\Scripts\python.exe -m alembic upgrade head
.\start.ps1
```

Skip virtual-environment creation/dependency installation if already done. `setup_local.py` refuses to overwrite `.env`. Never deploy the example password. Docker must be installed and running; Compose binds PostgreSQL only to `127.0.0.1:5433` with a persistent volume. `docker compose stop` preserves data; `down -v` deletes the volume.

Open `http://127.0.0.1:8000/`, register your account and create a report. Do not interchange `localhost` and `127.0.0.1`: cookies and the configured Origin must match. An alternate local preview is `start.ps1 -Port 8010`. The script runs migrations, starts a hidden matching/retention worker and launches the website. Stopping the website stops its worker. PostgreSQL is stopped separately.

Existing local CLIP/NanoDet files are reused. No model is automatically downloaded. Missing CLIP leaves reports saved with retryable matching status; missing NanoDet permits manual cropping.

### Portable PostgreSQL fallback used here

Docker's engine could not start. Official EDB PostgreSQL 17.11 Windows binaries were downloaded from `https://get.enterprisedb.com/postgresql/postgresql-17.11-3-windows-x64-binaries.zip`. Only the runtime directories were extracted to `.local/postgres/pgsql`. The cluster is `.local/pgdata`, uses SCRAM authentication, binds only to localhost and has a separate non-superuser application role. No Windows service or firewall configuration was installed.

```powershell
.venv\Scripts\python.exe -m scripts.local_postgres start
.\start.ps1 -PortableDatabase
# After stopping the website:
.venv\Scripts\python.exe -m scripts.local_postgres stop
```

The helper requires the runtime to exist; it does not download or overwrite a cluster. Use Compose or portable PostgreSQL, not both on port 5433. `.local` and `.env` are excluded from version control. This workspace is in OneDrive: before a campus pilot, move the database and photo storage outside cloud synchronization with restricted filesystem permissions. Back up PostgreSQL using database backup tools, not synchronization of live data files.

## Environment variables

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL using `postgresql+psycopg://`; no SQLite fallback |
| `POSTGRES_PASSWORD` | Local database role password, never exposed through the API |
| `CAMPUSFIND_ORIGIN` | Exact browser origin; local default `http://127.0.0.1:8000` |
| `CAMPUSFIND_SECURE_COOKIE` | `true` for HTTPS; insecure sessions are limited to documented local origins |
| `CAMPUSFIND_STORAGE` | Absolute private image directory; default `.local/private-images` |
| `CAMPUSFIND_EMAIL_DOMAINS` | Optional exact domain allowlist, not verified email ownership |
| `CAMPUSFIND_RETENTION_DAYS` | 1–365 days, default 180; recorded at report creation |
| `CAMPUSFIND_TIMEZONE` | IANA campus timezone for report dates, default `Asia/Kolkata`; timestamps remain UTC |

The `.env` loader accepts plain `KEY=value`, without interpolation or surrounding quotes. Environment variables take precedence. For deployment, use HTTPS/Secure cookies and a process supervisor for `uvicorn backend.main:app` and `python -m backend.worker`. `start.ps1` intentionally configures localhost HTTP only.

## Admin access

Register the intended account, then have the trusted local operator run:

```powershell
.venv\Scripts\python.exe -m scripts.make_admin admin@your-campus.example
```

The command promotes an existing account, records the action, and revokes its sessions. Log in again. Registration/profile updates cannot assign roles. There is no public admin bootstrap endpoint or built-in administrator password.

## Reports and claims

Reports require 1–4 images, accepted crop/full-frame choices, title/category/description, approximate location/date and retention consent. Limits: 15 MB and 24 megapixels per image, 45 MB combined. Images are oriented, resized to at most 2000 pixels on the longest edge and re-encoded as JPEG without EXIF/GPS. Random storage keys and original filenames are never returned. Authenticated report previews show the full photograph; the comparison dialog shows accepted regions.

Report transitions: `OPEN → MATCH_SUGGESTED` on relevant suggestions; active found reports become `CLAIM_PENDING` on a claim. Resolving all active claims returns them to `OPEN`; confirmed handover makes them `RETURNED`. Owners may close `OPEN`/`MATCH_SUGGESTED` reports and reopen `CLOSED` reports before expiry. Active claims block edits, closure and deletion. Returned items cannot reopen through the API. Closed/returned/hidden items are excluded from matching; closed/returned reports are visible only to their owner/admin.

Claims: `PENDING → APPROVED/REJECTED/WITHDRAWN`; `APPROVED → RETURNED/WITHDRAWN`. Finder/admin reviews non-public evidence and records a private note. Approval rejects conflicting pending claims and notifies their claimants. The claimant confirms physical receipt; an admin may record a verified handover with a note. Finders cannot silently confirm receipt for the claimant. Visual matches never approve ownership. Handover/contact details can be shared in private claim/review text; there is no public contact directory or messaging subsystem.

## Matching and efficiency

Submission commits the report and a durable job, then attempts background processing. The worker processes pending jobs. Failed jobs remain visible until the owner retries after resolving the model/storage problem. A PostgreSQL advisory transaction lock allows one platform matching job at a time. Existing native CLIP inference uses two threads and a bounded cache. Password hashing has a two-job per-process bound.

Each reference photograph has its own candidate-photograph ranking. The adapter calls the original `rank_gallery`, preserving category sections, CLIP similarity and appearance tie breaks. It does not blend models, metadata, local features or multi-view scores. Multi-image reports may appear more than once. Opposite-type active reports from other users are searched sequentially. Large galleries will require measured indexing and pagination work before broad deployment.

Persistent descriptors use prepared-pixel content, shape/dtype, model fingerprint and preprocessing version. They survive worker restarts and invalidate when pixels/crop/model change. Identity labels and filenames do not enter scoring. Memory caches contain bounded descriptors, not original photos. Deletion removes persistent images/descriptors; volatile entries leave memory through eviction or process restart.

Notifications are recipient-only and contain no evidence text. Potential-match notifications are deduplicated by pair/recipient. Saved match rows are filtered against current report visibility. Failures and empty results never reject reports or claim reliable no-match detection.

## Retention and operations

The worker removes expired images/descriptors, redacts expired report text/claim evidence, and removes expired sessions/throttle counters. Authorization blocks expired content immediately, even if the worker is stopped. Owners can delete earlier after resolving claims. Minimal action audit records remain. Files orphaned by interrupted operations are removed after a one-day grace. Operator-managed backups require their own retention/access policy; application deletion cannot erase unmanaged backups.

```powershell
.venv\Scripts\python.exe -m backend.worker --once
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
```

Do not downgrade useful databases without backups. Migration rollback tests use disposable schemas only.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
node tests/frontend_selection.cjs
node --check frontend/app.js
$env:CAMPUSFIND_TEST_POSTGRES='true'
.venv\Scripts\python.exe -m pytest tests/test_platform.py -q
Remove-Item Env:CAMPUSFIND_TEST_POSTGRES
```

SQLite is enabled only by explicit test settings. PostgreSQL tests create randomized `cf_test_…` schemas and remove only those schemas, never real reports or benchmark data. Synthetic fixtures test mechanics, not retrieval accuracy. This machine's sandbox blocks local PostgreSQL connections and can stall HTTP/thread tests; these run on the host.

## Before a campus rollout

This is a local MVP, not completed institutional deployment. Remaining operational work: verified campus email or SSO, secure account recovery, campus moderation/handover policies, HTTPS and trusted proxy configuration, private-directory/database permissions, backup/deletion tests, monitoring, independent security review and load testing. No institutional enrollment verification, external email/push delivery or automatic ownership verification is claimed. Retrieval accuracy still lacks independent physical-instance validation.

References: [OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [SQLAlchemy PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html), [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [PostgreSQL Windows distributions](https://www.postgresql.org/download/windows/).
