# Pilot environment and isolation

VIII-A.2 addendum: use [TECHNICAL_PREFLIGHT](TECHNICAL_PREFLIGHT.md) for explicit
development/test/researcher/pilot profiles, separate app/migration-role commands,
non-synced Windows storage/ACL review and the read-only configuration checker.
No dedicated participant DB/role/storage/TLS deployment was provisioned in VIII-A.2.
Disposable restoration and simulated outages were executed; see
[recovery evidence](RECOVERY_DRILL_REPORT.md). Do not treat those as a verified
restricted participant environment. Original isolation requirements below remain.

Status: procedure prepared; participant deployment **NOT VERIFIED**. Reuse
[PILOT_OPERATIONS](../PILOT_OPERATIONS.md) for exact configuration, HTTPS proxy,
worker supervision, backup guards and recovery commands. Do not duplicate or weaken
its requirements. No public deployment is authorized by VIII-A.

Regression: scripts/ui_test_server.py creates fresh UUID SQLite test directories
and synthetic pictures, binds loopback localhost:8017 and loads the real APIs.
Its Settings override enables test-only SQLite and open test accounts. It is not
approved for participants. Tests use localhost to separate cookies from the main
127.0.0.1 host. Never point this harness at real participant data.

Participant options: supervised campus workstation with a dedicated PostgreSQL
database/storage, or restricted campus-network HTTPS deployment behind a trusted
proxy. Both need operator verification, access restrictions and campus approval.
Do not treat plain localhost development as an equivalent secure multiuser pilot.
Use production settings and coordinator-issued accounts; no public registration.
Researcher, finder and claimant roles use separate accounts; issue least privilege.
Anonymous homepage access must reveal no private reports. Signed-in active reports
are intentionally visible to other members: use one study cohort/environment with
staged items, not an expectation of private report visibility between participants.
Private evidence is limited to claim parties/authorized administrators.

Before launch, operator records environment code, approved origin, database alias,
storage alias, model fingerprints, migration revision, worker heartbeat and fixture
inventory (no secrets). Verify database is dedicated, application role non-superuser,
storage/backups outside web roots and cloud sync, and logs omit request bodies.
This workspace is under OneDrive: it is not approved participant storage. Set an
explicit non-synced private directory and dedicated database before any sessions.
Keep the real development database and photos untouched. Inspect settings locally;
never copy DATABASE_URL credentials, .env, sessions or tokens into study records.

Use staged inventory codes and synthetic evidence approved in advance. Confirm
each account can see only its authorized evidence; do not reset a shared database
between participants. Prepare a fresh cohort instance or remove only enumerated
staged fixtures with the operator after claims are resolved. Maintain withdrawal
and backup obligations; an app deletion alone does not delete backups/caches.

Recovery: pause task timing and record an interruption code. For a crash/reload,
report drafts are memory-only; explain loss and offer a fresh staged attempt under
a new session code. For expired sessions, reauthenticate with the same account;
the report draft may survive in-tab navigation. For an interrupted/ambiguous upload,
check My Reports before retrying. Do not repeatedly submit. If duplicates exist,
operator reconciles only staged records after checking claims. For worker failures,
reports remain saved; correct model/worker cause before explicit retry. For database
or network unavailability, suspend writes and restore connectivity/readiness before
resuming; never infer that an error means a transaction did not commit.

Restore rehearsal uses scripts/recovery_drill.py only in its new guarded disposable
databases. An actual recovery must target a NEW isolated database and storage,
validate hashes/rows, revoke restored sessions and replay deletion obligations
before any switch. Never restore/clean/drop the populated application database.
The existing logical drill does not verify encrypted off-machine backup delivery,
campus RPO/RTO, large-scale recovery or proxy availability. All require operator
evidence before sessions. No destructive recovery was performed in VIII-A.
