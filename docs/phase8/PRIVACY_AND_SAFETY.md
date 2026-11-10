# Privacy, consent and safety

VIII-A.2 approval register (no approvals inferred):

| Responsible role (appointment pending) | Required evidence / decision | Status / consequence |
| --- | --- | --- |
| Institutional research authority / coordinator | Written authorization and determination of ethics review, recruitment limits | PENDING; no recruitment |
| Privacy custodian / institutional authority | Approved consent, retention by artifact class, withdrawal/deletion/backup policy | PENDING; no participant data |
| Authorized operator / network administrator | Dedicated PostgreSQL identity/grants, non-synced ACL-restricted storage, trusted TLS, access restrictions | NOT_VERIFIED; environment gate blocked |
| Operations/incident lead | Named escalation contacts, supervisor restart and alert acknowledgement evidence, restore/session-revocation drill | PENDING; operational gate blocked |
| Study/accessibility lead | Researcher-only human dry run, required input/assistive support and critical-barrier disposition | PENDING; affected study tasks cannot start |

Isolated tests in [technical report](PHASE8A2_REPORT.md) do not appoint these people
or approve their procedures. Keep the existing consent/retention boundaries below.

Institutional authorization/ethics requirements, authorized researchers, retention
duration, withdrawal contact and incident contact are **PENDING institutional decision**.
IIIT Surat approval is not asserted. Do not recruit until the coordinator resolves
these in writing and the environment gate passes.

Before consent, explain: voluntary staged-item usability study, planned duration,
tasks and observers; no effect on academic standing; may skip/stop without penalty;
AI suggestions are advisory; what observations are collected, who accesses them,
approved retention and how withdrawal is requested. Obtain the campus-approved
consent form separately from observations. Do not use app photo consent as research
consent. Recording video/audio/screenshots is OFF by default and needs separate
approval/consent. No actual participants or consents were collected in VIII-A.

Use session codes S001… and staged possessions. Avoid names, emails, student IDs,
credentials, faces, precise locations and personal documents in observations/photos.
Use synthetic non-sensitive ownership evidence. No real disputed property. Store
consent/contact-to-code mappings separately under approved custodians; observers
need only pseudonymous results. No unnecessary accessibility diagnoses: record
input method and volunteered functional barriers, not health characteristics.

Observation CSV accepts coded notes only. Keep any necessary narrative incident
record in a separate restricted approved store after redaction. A validator cannot
guarantee anonymity or make unsafe source records safe. Never copy passwords,
session tokens, complete request bodies, evidence text or email into logs/results.
Review exports manually. Encrypt/restrict approved research storage and backups;
grant only designated researchers; no external analytics or cloud uploads added.

Retention: institution sets exact duration and custodian before recruitment.
Configure app retention (existing range 1–365 days; default 180 is NOT study approval).
Define separate observation/consent/backup retention, then schedule supervised
disposal of images, manifests, embeddings, logs and copies. Withdrawal: stop task,
locate only code-linked data through authorized custodian, resolve active staged
claims safely, delete permitted records and record completion without evidence
contents. Backups need a deletion ledger and replay on restore; specify limits
of already aggregated anonymous results in consent. Do not promise impossible erasure.

STOP immediately on participant withdrawal, unauthorized evidence/photo access,
unexpected report visibility outside the approved cohort, unauthorized state
change, suspected bypass, corruption/loss, failed isolation or critical incident.
Stop capture and writes; do not explore/exfiltrate additional records. Record only
session/task/environment codes, time, event class and observed impact (no secrets).
Notify the designated campus incident lead via the approved channel; contacts and
notification deadlines are pending. Preserve minimum restricted diagnostic evidence
only under that lead. Resume only after cause correction, isolation/regression
verification and explicit incident-lead/coordinator clearance. Unrecoverable task
failure is also a critical measurement error, though not necessarily a security incident.
