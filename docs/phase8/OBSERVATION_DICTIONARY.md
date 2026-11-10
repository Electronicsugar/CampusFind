# Observation dictionary and validation

Templates: [empty CSV](../../research/phase8/observations-empty.csv),
[TEST ONLY example](../../research/phase8/observations-TEST-ONLY.csv).
The example contains fictional tooling input, not student results.

One row per session/task. Required exact ordered header is supplied in the template;
unknown fields (including names/emails) are rejected. Do not add free-text columns.

| Field | Values / meaning |
| --- | --- |
| session_code | S plus 3–6 digits; pseudonymous; no names or identifiers |
| task_id | U01–U09 |
| device_class | mobile, tablet, desktop |
| input_method | keyboard, touch, mouse, screen_reader, mixed; no diagnosis |
| completion_status | independent, assisted, failed, not_attempted |
| assistance_level | none, minor_hint, substantial; independent requires none, assisted requires a hint |
| duration_seconds | Finite nonnegative seconds; blank if missing; includes interruptions |
| timing_method | measured, estimated, not_recorded; latter requires blank duration, others require value |
| recoverable_error_count / critical_error_count | Nonnegative integers; 0 is observed none, not missing |
| ai_uncertainty_understood | yes/no/blank for suggestions not being identity proof |
| claim_process_understood | yes/no/blank for private human review |
| approval_receipt_understood | yes/no/blank for approval not implying receipt |
| returned_understood | yes/no/blank for authorized physical handover confirmation |
| difficulty_rating | 1 very easy through 5 very difficult; blank if declined/unassessed |
| observer_notes_redacted | blank or navigation, crop, validation, uncertainty, claim, recovery, accessibility, other; codes only |

Not_attempted requires no assistance, blank duration and zero errors. Comprehension
blank means not assessed, not false. Critical incidents also go to the restricted
incident procedure; do not copy incident details to the CSV.

```powershell
.\.venv\Scripts\python.exe -m scripts.study_results research/phase8/observations-empty.csv
.\.venv\Scripts\python.exe -m scripts.study_results research/phase8/observations-TEST-ONLY.csv
```

The tool prints deterministic JSON to stdout and returns nonzero on invalid input.
Errors contain line numbers/field names, never rejected cell text. Header-only input
has zero sessions; missing header is invalid. Duplicate session/task rows are invalid.
Invalid records are excluded and counted; fix them before interpreting summaries.
Attempt denominator excludes not_attempted and invalid rows. Independent/failure
rates divide their counts by valid attempts; zero denominator is null. Assisted
completion is a count. Duration median/min/max use timed valid attempts (including
failures); timed count and estimated count are explicit. Error totals and each
comprehension yes/no/missing count use valid attempts. Sessions count distinct codes
in valid rows, not unique people if repeat sessions exist. Missing_cells counts
blank/missing cells including optional cells; it is not a count of invalid records.
Keep raw counts prominent and do not interpret missing or invalid attempts as success.
Observer review remains required; allowlists do not certify de-identification.
