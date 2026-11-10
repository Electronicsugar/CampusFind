# Controlled pilot operations

No public deployment was performed. Production here means fail-closed pilot
configuration, not a claim of completed institutional deployment or penetration testing.

## Configuration and admission

Install pinned requirements in the existing virtual environment. Store secrets
outside source control with OS permissions restricted to the service operator.
Do not place live photos, PostgreSQL data or backups in a cloud-synced folder.

| Variable | Pilot setting |
| --- | --- |
| `CAMPUSFIND_ENV` | `production` |
| `DATABASE_URL` | Dedicated non-superuser PostgreSQL role; database ownership for the separate migration operator as appropriate |
| `CAMPUSFIND_ORIGIN` | Exact `https://` origin, without path/query/credentials |
| `CAMPUSFIND_SECURE_COOKIE` | `true` |
| `CAMPUSFIND_STORAGE` | Explicit absolute private directory outside web root/cloud sync |
| `CAMPUSFIND_RETENTION_DAYS` | Campus-approved 1–365 days; existing reports retain their original expiry |
| `CAMPUSFIND_TIMEZONE` | Campus IANA timezone, default `Asia/Kolkata` |
| `CAMPUSFIND_EMAIL_DOMAINS` | Optional development signup restriction; does not verify email control |
| `CAMPUSFIND_BACKGROUND_MATCHING` | Production ignores this and uses the separate worker |
| `CAMPUSFIND_PG_BIN` | Optional PostgreSQL client binary directory for backup tools |

Open registration is **disabled in production**. A coordinator must verify each
participant offline and issue an account through `python -m scripts.create_pilot_user
email@campus.edu --name "Student name"`. The command privately prompts for a password;
never pass passwords on command lines or through chat. Deliver access through an
approved private campus channel. Administrator promotion remains a separate local
operator command from Phase 4. No online role-escalation route was added.
Verified email/SSO and secure account recovery remain required before open enrollment.
There is no automated password reset or institutional identity verification.

## HTTPS and reverse proxy

Run `python -m scripts.serve --port 8000 --proxy-ip 127.0.0.1` behind a trusted local
HTTPS reverse proxy. The launcher binds only to loopback, disables raw access logs,
limits concurrent HTTP connections to 64, and trusts only explicitly supplied IP
addresses. Without `--proxy-ip`, forwarded headers are ignored. Never use wildcard
proxy trust. The proxy must replace forwarded client/protocol headers, preserve the
configured Host and reject unrecognized hostnames. Example Nginx location settings:

```nginx
client_max_body_size 76m;
client_body_timeout 30s;
proxy_read_timeout 150s;
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Configure certificates, HTTPS listeners and a default-host rejection server with
the campus administrator. The snippet is not a complete TLS deployment. Proxy body
limits complement application byte-count limits; impose edge connection/request
limits and disk-spool quotas. The HTTPS/reverse-proxy path has configuration tests,
but no live certificate/proxy deployment was provisioned or validated here.
See [Uvicorn proxy settings](https://uvicorn.dev/settings/).

`start.ps1` is for local development and deliberately uses insecure localhost
cookies. Do not use it as the production launcher. Production startup:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m backend.worker
# In a separate supervised process:
.venv\Scripts\python.exe -m scripts.serve --port 8000 --proxy-ip 127.0.0.1
```

Use the institution's service supervisor with restart-on-failure and a working
directory set to this project. Send graceful SIGTERM where supported and allow
more than five minutes for an active matching job; on Windows process termination
rolls back the transaction and the durable PENDING job can be replayed. A global
PostgreSQL advisory lock allows one matching CPU job per database across workers.
One job is bounded to five minutes at batch boundaries; a single model/native call
cannot be forcibly preempted by that cooperative bound. Failed jobs require explicit
retry after correcting the cause. Parent rows remain locked during a job; conflicting
writes fail after a three-second lock wait and can be retried. PostgreSQL statement
timeouts are 30 seconds. This is a known scalability constraint.

## Health, telemetry and alerts

- `/health/live`: process reachability only.
- `/health/ready`: database/migration revision/private-storage checks, plus a live
  worker heartbeat in production. Returns generic 503 on failure, no internal paths.
- `/api/v1/admin/operations`: admin-only queue counts, oldest pending age, deletion
  backlog, worker age and process-local HTTP counters/durations.
- Structured request/job messages contain route templates, status, duration and
  counts, never URLs with query strings, emails, report text, photos or claim evidence.

HTTP metrics reset on restart and are not shared between server processes. The
worker heartbeat allows six minutes for long jobs; it does not prove model quality
or successful processing of every job. Monitor FAILED jobs, persistent PENDING age,
deletion backlog, disk space, PostgreSQL connections and readiness failures. Model
absence preserves reports but produces FAILED matching jobs; readiness does not load
or benchmark vision models. Set log retention/access rules and test alerts before use.

## Backup and safe recovery

`python -m scripts.backup --output <new-private-backup-directory>` creates a custom
PostgreSQL dump, referenced image copies and a SHA-256 manifest. The destination must
be new and outside image storage. An exclusive advisory guard waits for app/worker
file mutations, then a repeatable-read snapshot is exported for `pg_dump`; this avoids
DB/photo inconsistencies. Writers may receive temporary 503 during backup. Operator
SQL, old code and external filesystem writers do not honor the guard: stop those
writers or stop all services for an offline backup. Never run migrations concurrently.

Backup tools operate on the public application schema. A missing photo or checksum
mismatch prevents the completion manifest. An incomplete directory must not be used
for recovery. The manifest checks integrity, not authenticity or encryption. Backups
contain password hashes, sessions, private photos and evidence: restrict access,
encrypt at rest with approved tooling, and implement a separate retention schedule.
Restoring an old backup can resurrect deleted data and sessions; before enabling
traffic, replay deletion obligations and revoke sessions. This policy needs campus
approval and a rehearsed operator runbook.

The tested portable drill is `python -m scripts.recovery_drill --output <new-result.json>`.
It uses only newly created `cf_restore_<random>` databases and synthetic photos,
validates restored rows/hashes/private evidence, rejects corruption, then removes
those exact disposable databases. It never restores into an existing database and
never uses `DROP ... FORCE`. Creation requires a separate local database operator;
the web application remains a non-superuser. Real recovery should likewise restore
into a fresh, isolated database/storage directory, validate, revoke sessions and
then explicitly switch service configuration. Keep the old instance offline for
rollback. Do not use `pg_restore --clean` against the live database.

This drill verifies logical backup/restore, not encrypted off-machine backup delivery,
large-scale disaster recovery, disk-loss recovery, or measured production RPO/RTO.
[PostgreSQL pg_dump documentation](https://www.postgresql.org/docs/17/app-pgdump.html)
describes exported snapshots and custom archives.

## Migration and rollback

Back up first. Stop web/worker processes for migration; run Alembic `upgrade head`
and `check`, then readiness and smoke tests. New migrations are additive caches,
operational tables and indexes. Schema upgrade/downgrade tests run only in disposable
schemas. For rollback, stop services and run the previous compatible application
against the additive schema or switch to a validated restored database. Do not
automatically downgrade a database with user records: review data loss implications.

## Pilot boundary

Start with an operator-supervised small cohort and about 100 active reports, then
observe actual photo/model latency, lock contention and queue age before increasing
capacity. This is an operational recommendation, not an enforced limit or a validated
maximum. The 5,000-report test is a single-query infrastructure test, not a 5,000-user
end-to-end campus simulation. All-pairs storage grows with lost × found photographs;
multi-photo reports multiply it. Do not promise capacity from synthetic timings.
Independent physical-instance recognition and no-match calibration remain blocked
on new held-out real-object photographs. Claims always require human verification.
