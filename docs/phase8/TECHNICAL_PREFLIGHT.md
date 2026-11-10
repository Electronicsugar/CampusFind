# VIII-A.2 technical preflight — 2 November 2026

This is an operator runbook, not an authorization or a deployed pilot. Do not use
real participant accounts or data. Participant deployment remains NOT_VERIFIED.
Retain [existing operations](../PILOT_OPERATIONS.md) and the VIII-A procedures.

## Audit / minimal changes

| Requirement | Existing implementation / evidence | Gap / action | Risk / who can complete |
| --- | --- | --- | --- |
| Profiles, DB separation | Settings production/development; test-only SQLite; disposable test schemas | New read-only scripts.pilot_preflight requires explicit profile, secret env name and expected host/port/database/user | High; checker tests automated, actual target provision requires operator authorization |
| Private storage | Random keys, authorization, re-encoding, durable deletion | Checker rejects repository/sync/public paths, missing dirs, symlinks/junctions and backup nesting; ACL/sync-client exclusions remain manual | High; operator verifies non-synced roots/ACL |
| TLS/CSRF/session/Host | Settings + platform/auth + serve exact proxy IPs | HTTPS TestClient negative cases executed; actual certificate/proxy not provisioned | High; operator TLS/network team |
| Three users / state changes | test_platform and test_pilot already cover many boundaries | test_preflight adds direct third-user actions, duplicate return, HTTPS controls and simulated outage | High; isolated checks automated |
| Worker recovery | Durable PENDING, advisory locks, process-crash test, heartbeat | Reuse tests; no production supervisor/alerts installed | High; operator configures service and delivery |
| Model readiness | Existing benchmark loads 20 images and fixed old output | New optional one-input CLIP/NanoDet canary avoids benchmark duplication/downloads | Medium; executed locally, not recognition evidence |
| Backup/restore | Existing guarded new-database drill | Extend offline drill to verify restored revision and anonymous auth denial | High; executed disposable databases only |
| Rehearsal | Existing U01–U09 and observation tool | New rehearsal runbook maps actual fixtures/evidence and pending checks | Medium; researcher-only technical checks, human moderation dry run pending |

No production app changes, new dependencies or migrations. New preflight file is
offline, removable without runtime impact. Recovery utility change affects only
its own disposable rehearsal. Tests and docs are reversible file additions/edits.

## Explicit profiles and isolation

| Profile | Configuration | Permitted data |
| --- | --- | --- |
| Development | Existing .env, loopback dev cookies | Developer data only; never pilot |
| Automated tests | Settings(testing=True), UUID schemas/temp dirs; ui_test_server SQLite | TEST ONLY fixtures |
| Researcher dry run | Dedicated PostgreSQL DB/app role, production app settings, exact restricted HTTPS origin; explicit separate config/env | Generated objects and synthetic evidence only |
| Future authorized student pilot | Separately authorized DB/app/migration roles, non-synced storage/backups, production settings, campus-approved TLS/access/retention | Only approved participant data after authorization |

No dry-run/pilot profile may silently import development .env secrets. The checker
does NOT call Settings.from_env/load_env or provision anything. An example plan is
[preflight-example.json](../../research/phase8/preflight-example.json); placeholders
must be replaced by an authorized operator and its checks must fail until secrets
and directories exist. Never use an example password. Output contains check names
and statuses only, never DSNs/secret values. A minimum password length is only a
weak-secret heuristic, not proof of entropy, rotation or non-reuse.

## Operator provisioning (not executed for a real pilot)

First obtain explicit target approval: hostname/port, NEW database name, app role,
migration role, origin, storage and backup roots. Verify no existing database/role
shares those names using an administrator's restricted console. Do not paste results
with secrets into reports. A pre-existing/ambiguous name is a STOP, not a reset.
Portable PostgreSQL is supported; Docker is not required.

In an authorized PostgreSQL console, using unique approved identifiers (replace
names consistently; this is a procedure, not an idempotent provisioning script):

```sql
CREATE ROLE cf_rehearsal_migrate LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE cf_rehearsal_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
-- Use the console's private password prompt (psql \password), not SQL literals.
CREATE DATABASE cf_rehearsal OWNER cf_rehearsal_migrate;
REVOKE ALL ON DATABASE cf_rehearsal FROM PUBLIC;
GRANT CONNECT ON DATABASE cf_rehearsal TO cf_rehearsal_app;
-- Reconnect explicitly to cf_rehearsal as the migration role.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO cf_rehearsal_app;
ALTER DEFAULT PRIVILEGES FOR ROLE cf_rehearsal_migrate IN SCHEMA public
  GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO cf_rehearsal_app;
ALTER DEFAULT PRIVILEGES FOR ROLE cf_rehearsal_migrate IN SCHEMA public
  GRANT USAGE,SELECT ON SEQUENCES TO cf_rehearsal_app;
```

Load fresh distinct app/migration DSNs from an approved secret mechanism into the
current operator process (never command-line literals). Grant only schema/data
privileges; do not make app owner/member of migration role. Restrict CONNECT/HBA to
approved service principals and network sources. Apply migrations as migration role,
then grant existing tables/sequences privileges if migrations predate defaults.
Never run migrations while worker/web writes are active. Never alter a shared DB.

Approved private roots must be outside OneDrive/other sync software and public web
roots. An example Windows operator procedure (run only for NEW approved targets):

```powershell
# Replace paths and identities with approved values. Stop if target already exists.
New-Item -ItemType Directory C:\CampusFindPrivate\Rehearsal\images
New-Item -ItemType Directory C:\CampusFindBackups\Rehearsal
# Operator reviews ACL before/after; service/backup identities need only their roots.
icacls C:\CampusFindPrivate\Rehearsal /inheritance:r
icacls C:\CampusFindPrivate\Rehearsal /grant:r 'DOMAIN\ApprovedService:(OI)(CI)M' 'DOMAIN\ApprovedOperator:(OI)(CI)F'
icacls C:\CampusFindBackups\Rehearsal /inheritance:r
icacls C:\CampusFindBackups\Rehearsal /grant:r 'DOMAIN\ApprovedBackupOperator:(OI)(CI)F'
```

This example does not verify ACL inheritance on parent directories, cloud-client
configuration, EFS/BitLocker or backup encryption. Verify them explicitly. Do not
remove needed SYSTEM/administrator recovery access; have the operator approve the
result. No such directory/ACL was provisioned by this increment.

From project root, with approved secrets already in process environment:

```powershell
.\.venv\Scripts\python.exe -m scripts.pilot_preflight --config C:\ApprovedConfig\rehearsal.json
# Optional read-only connection checks expected identity, revision, ownership/DDL flags:
.\.venv\Scripts\python.exe -m scripts.pilot_preflight --config C:\ApprovedConfig\rehearsal.json --connect
$env:DATABASE_URL=$env:CF_DRY_MIGRATION_URL
.\.venv\Scripts\python.exe -m alembic upgrade head
# Switch process environment explicitly; do not fall back to .env.
$env:DATABASE_URL=$env:CF_DRY_DATABASE_URL
$env:CAMPUSFIND_ENV='production'
$env:CAMPUSFIND_ORIGIN='https://approved-rehearsal-host.example.invalid'
$env:CAMPUSFIND_SECURE_COOKIE='true'
$env:CAMPUSFIND_STORAGE='C:\CampusFindPrivate\Rehearsal\images'
# Set CAMPUSFIND_RETENTION_DAYS to the approved rehearsal value before starting.
.\.venv\Scripts\python.exe -m backend.worker
# Separate supervised process with the SAME explicit app environment:
.\.venv\Scripts\python.exe -m scripts.serve --port 8000 --proxy-ip 127.0.0.1
```

Re-run --connect after migration; do not grant DDL to app to obtain a green result.
The tool checks role flags/ownership/public CREATE but does not fully enumerate
inherited memberships or all object grants: operator must inspect role membership,
RLS/HBA/database isolation. SQL checks are read-only and exceptions are redacted.
Remote DBs need verify-full TLS and approved CA; remote transport remains NOT_VERIFIED.

Actual launcher still uses its existing config conventions: populate ALL required
settings explicitly and start with a clean process environment. The JSON checker
does not apply settings or prove that a running service used them. Compare service
environment privately with the reviewed plan; do not export it into logs.

## HTTPS/security preflight

Use approved trusted HTTPS termination and exact Host/origin, restricted campus
admission, explicit proxy IPs and documented body/time limits from PILOT_OPERATIONS.
No wildcard trust, TLS-verification bypass or CSRF exceptions. Check trusted cert
chain, Secure/HttpOnly/SameSite cookie, wrong Host/origin rejection, missing CSRF,
anonymous protected requests, admin denial and three-user evidence denial. Direct
forged forwarded headers must not influence trusted identity: serve defaults to no
proxy trust; only configured proxy IPs can forward. TestClient tests are not a live
proxy/TLS handshake. Actual proxy termination remains NOT_VERIFIED.

PASS/FAIL apply to executed checks; WARNING means a reviewable configuration
condition (e.g. no forwarded proxy IPs), NOT_VERIFIED means a control not measured.
Exit zero means no detected FAIL, not permission to recruit; check every status.

## Supervision/monitoring and reversal

Operator starts DB -> migration check -> worker -> web -> HTTPS/readiness -> canary.
Use an approved Windows service supervisor/scheduled task with restart on failure,
dedicated account, explicit working directory/environment and no visible windows.
No supervisor was installed/verified here. Stop intake/web first, allow active job
completion, gracefully stop worker, then maintenance. PostgreSQL transaction rollback
leaves interrupted PENDING work recoverable; FAILED jobs need explicit retry after
cause correction. A stuck native model call may outlast cooperative time limits.

Monitor /health/ready, admin operations queue age/FAILED count, deletion backlog,
worker heartbeat, disk space and DB connections. Verify restricted log ACL and
retention; never collect bodies, evidence, passwords or tokens. In-test operational
log redaction passed; deployed log files and alert delivery are NOT_VERIFIED.
Assign operator/incident contacts and test an alert acknowledgement before sessions.

Reversal: stop only identified rehearsal processes, inventory exact synthetic
artifacts/DBs, obtain operator approval for teardown; never drop by prefix/wildcard,
overwrite backups, force-disconnect unknown clients or run pg_restore --clean.
The disposable recovery drill cleans only its own generated database names. Keep
real pilot resources until approved retention/withdrawal obligations are satisfied.
