# Standardized task cards — protocol v1

All fixtures are staged, accounts coordinator-issued, and evidence synthetic.
Common timing/assistance/error rules: [protocol](USABILITY_STUDY_PROTOCOL.md).
Start every task at ready after instruction. Eight-minute limit unless specified.
Researcher verifies preconditions privately; instructions describe goals, not clicks.
Moderator resets only enumerated staged fixtures after resolving claims; never
reset the real database. Each session/task has one observation; repeats get a new
session code and are reported as repeated attempts, not new independent people.

| ID | Participant-facing instruction | Preconditions / role / fixture | End event and errors to observe | Researcher notes / cleanup |
| --- | --- | --- | --- | --- |
| U01 | “You lost this staged bottle near the practice library. Report it using these two photographs so others can help.” | Student A signed in; new LOST fixture, two non-sensitive angles, approved details/date | Saved report visible with two confirmed selections; observe type, validation, selection/review confusion and duplicates | Do not teach crop controls; record full-frame versus crop comprehension. Keep report for U04; remove staged report after session obligations resolved |
| U02 | “You found this staged notebook at the practice desk. Share the find so its owner can identify it.” | Finder B, separate staged object/photos, no existing report | Saved FOUND report with confirmed selections; wrong type or private details published are errors | Check understanding of lost/found; keep fixture for browse, remove after claim lifecycle |
| U03 | “Find and inspect the practice notebook report among these reports.” | Student A; known target in paginated staged gallery with distractors | Target details and photo inspected; observe filter/nav/pagination mistakes | Prepare enough fixtures to require pagination; cleanup only enumerated staged distractors |
| U04 | “Look at the suggestions for your practice report. Explain what these results mean and what you would do next.” | Owner A; completed job, at least one actual uncertain result and similar different-unit candidate, prechecked by researcher | Participant explains identity uncertainty and next verification step; compare selected regions | Do not fabricate server output if category result differs: mark not_attempted/fixture unavailable. Capture comprehension before explanation; retain fixture until end |
| U05 | “You believe the practice found item is yours. Use the supplied fictional ownership details to ask for it back.” | Claimant A, not owner; active FOUND fixture; synthetic hidden-mark card | Pending private claim visible; public exposure, wrong target, or belief that AI approves are errors | Ask who sees evidence; retain pending claim for U06 |
| U06 | “As the finder, review this request and decide using this staged inventory card.” | Finder B; pending claim; card specifies valid evidence for approval or contradictory evidence for rejection; counterbalance branches in run log | Authorized APPROVED or REJECTED state matching card, with explanation | Never approve by similarity alone; prepare separate approved fixture if rejection branch used. Resolve remaining staged claims before disposal |
| U07 | “For this staged handover, inspect the receipt confirmation, cancel first, then complete it after we physically pass you the staged item.” | Claimant A, approved claim, item still with moderator | Cancellation leaves APPROVED; physical staged transfer then authorized confirmation yields Returned | Finder cannot confirm receipt; no real property. Verify notification/report state; staged Returned fixture can be disposed under approved policy |
| U08 | “Your session or connection was interrupted while reporting. Recover safely and check whether the report was saved.” | A; researcher-owned staged draft; simulate expiry or offline condition only on isolated environment; record which variant | Restored/recreated draft or saved report located without duplicate publication; errors include blind resubmit/data loss | Never interrupt real data; ambiguous upload: My Reports before retry. Restore connection/session and reconcile staged duplicates |
| U09 | “Using your preferred keyboard or assistive input, find the staged report and compare its pictures, then return to the report.” | A; known compare fixture; keyboard, optional screen reader/zoom/touch accessibility chosen with participant; 10 minute window | Comparison opened/dismissed, usable focus restored and target reached | Observe focus traps, labels, zoom/reflow; no diagnosis collection. Reset only temporary test viewport/zoom, preserve participant preferences |

Record startup/finish state codes and fixture inventory in the restricted session
run log, without evidence contents. Pause all tasks on a safety stop. If a fixture
cannot be prepared without altering production semantics, mark not_attempted and
record fixture-unavailable in the run log rather than inventing successful results.
