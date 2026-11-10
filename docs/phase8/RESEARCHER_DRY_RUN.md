# Researcher-only rehearsal — VIII-A.2

No participants, consented sessions or human usability timings were collected.
This increment executed an automated API/technical rehearsal plus focused browser
accessibility smoke, not a complete moderated human U01–U09 session. The latter
remains pending a named researcher and the restricted rehearsal deployment.
Reuse [protocol](USABILITY_STUDY_PROTOCOL.md), [task cards](USABILITY_TASKS.md),
[dictionary](OBSERVATION_DICTIONARY.md) and existing observation templates unchanged.

## Fixture preparation / execution

For fast regression only, run .venv\Scripts\python.exe -m scripts.ui_test_server.
It creates a NEW UUID directory in .local/ui-tests with SQLite and two generated
bottle images labelled TEST ONLY. It is not the participant PostgreSQL environment.
Do not reuse its .local metadata file as evidence of current server identity:
check the new process/URL. Stop only your identified server after smoke testing.
No real .env database is used by this script's Settings override. Account factories
in tests/test_platform.py are synthetic only; do not deploy their passwords.

The three-user tests create A LOST and B FOUND reports with two images each;
C is unrelated, with direct identifiers used for negative tests. Each test has a
fresh UUID schema/storage. Existing complete_student_journey_through_retention and
matching pagination tests supply state/notification and paging coverage. No scripted
reset of a populated environment was added. For a future researcher-browser run,
issue separate coordinator-controlled synthetic A/B/C accounts in the approved
dry-run profile and use only the current enumerated fixture inventory.

| Task | Executed technical evidence | Rehearsal action still needed |
| --- | --- | --- |
| U01 lost / multi-photo / selection | API factory submits two explicitly confirmed full images; frontend_selection covers crop acceptance | Human browser review/publish with supplied angles; observe start/end and assistance without coaching |
| U02 found | API factory creates B's two-photo FOUND report | Human verify type comprehension and safe description |
| U03 browse/pagination | Existing report/match paging regressions, active cohort image authorization | Populate >25 enumerated staged reports in dedicated dry run using factory-equivalent APIs; observe search/paging and older links |
| U04 uncertain | Real installed-model canary; existing status/selection presentation tests | Run actual matching on staged angles; inspect real status. If uncertain cannot be reproduced, mark task fixture-unavailable or use a separate TEST ONLY static discussion card; never inject fake inference into app |
| U05 private claim | A creates synthetic evidence, C denied evidence/actions by direct IDs | Observe pending state comprehension using only synthetic clue card |
| U06 finder review | B approves; existing tests also cover rejection/conflicts and admin rules | Counterbalance approve/reject scenario; document fixture state before timing |
| U07 receipt | B denied return, A returns, duplicate return rejected; frontend_handover cancel/focus tests | Physically pass staged item, cancel dialog first, then confirm; human comprehension not inferred from APIs |
| U08 recovery | Session expiry/relogin, simulated engine outage, frontend network/draft/duplicate tests | Same-tab browser recovery and real network interruption still unexecuted this increment; check My Reports before retry; reload/close loses draft |
| U09 accessibility | Fresh browser 320px menu Enter opens, Escape closes and restores menuToggle focus; equal scroll/client width 305; 768px width 753; desktop protected route/gallery renders | Screen reader, zoom 200%/400%, actual touch, contrast audit, reduced-motion visual response, report/dialog keyboard path remain pending |

The 15px difference between nominal viewport and measured client width is browser
scrollbar space, not overflow. Viewport override was reset after testing. Code
already includes focus rules, dialog focus restoration, status roles, 44px targets
and reduced-motion CSS; code presence is not a performed accessibility audit.
No WCAG certification or real-device usability claim. No moderator start/end task
times were invented; only measured technical model/restore timings are reported.

## Recording and reset instructions

Copy the EMPTY observation template to an approved private study directory using
a new versioned name, not into this synced repository. Assign session codes without
names; use one row/session/task. Record observed assistance/error categories using
the existing dictionary; leave unassessed fields blank. If the team only rehearses
data entry with made-up values, keep that file TEST ONLY and separate forever from
study results. The existing TEST ONLY example validated again with no errors; its
duration and responses are illustrative and not new measurements.

```powershell
.\.venv\Scripts\python.exe -m scripts.study_results research/phase8/observations-empty.csv
.\.venv\Scripts\python.exe -m scripts.study_results research/phase8/observations-TEST-ONLY.csv
```

Before any human dry run, verify task cards' preconditions, role and inventory,
practice agreed start/end signals, classify a shared example of minor versus
substantial help, and rehearse stop escalation. Decide who observes versus operates
the finder account. Evidence must never be shown through a shared observer screen
to unrelated users. Do not record passwords or evidence in notes; coded redacted
themes only. Stop immediately on privacy/authorization/isolation failure and follow
PRIVACY_AND_SAFETY. Pending incident contacts must be assigned before such sessions.

For resets, stop only identified rehearsal processes, resolve staged claims and
review exact fixture inventory, then use authorized app deletion for synthetic
records. Do not issue broad SQL deletes or wildcard filesystem deletion. Database
test fixtures clean their own temporary UUID schema/storage; guarded restore drill
removes its exact new DBs. Private production artifacts require approved retention
and deletion ledger procedures. Operator securely disposes verified test-only
artifacts/backups after review, without mixing participant/dev records.
