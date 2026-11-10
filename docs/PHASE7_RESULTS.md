# Phase VII results

Implementation and browser acceptance: 28–29 October 2026. Final regression and
local-server retry: 2 November 2026. Initial findings: [audit](PHASE7_AUDIT.md).

## Delivered

The existing FastAPI and vanilla HTML/JavaScript application now has a light,
green CampusFind design, responsive navigation, active-page indicators, a new
homepage, dedicated Profile, clearer browsing, and scoped dashboard summaries.
Administrator navigation remains role restricted.

Reporting has numbered sections without additional mandatory page transitions,
photo previews and removal, explicit per-photo selection status, keyboard crop
bounds, full-frame selection, NanoDet assistance, and a review dialog before
publishing. Drafts survive hash navigation and same-account reauthentication in
the current tab. Refresh/close warnings do not persist private drafts to storage.
Busy submissions block duplicate actions and hash navigation. Draft capture skips
disabled fields during an upload so cancelling a refresh warning cannot erase it.

Potential matches retain backend order and category sections. The UI explains
uncertainty, queued/failed/completed matching, and side-by-side selected crops.
There are no identity-probability percentages. Claims show human-readable states,
private evidence disclosures and role-specific next actions. Receipt uses an
accessible in-page confirmation with cancellation and focus restoration.
Notifications have textual read/unread labels and authorized claim deep links.

Shared detection preview buttons explicitly avoid form submission. The assistant
script loads once; route/request guards suppress stale updates. Cropped comparison
previews use a bounded eight-entry cache. Research tools retain their workflows,
with updated branding, home links and clearer server-processing wording.

Production ranking, thresholds, ownership transitions, CSRF and image authorization
are preserved. The only production backend edit adds app-ui.js to the static asset
allowlist. No framework, fonts, dependencies or model downloads were added.

## Verification

Final Python run: **118 passed, 3 skipped**, 31.87 seconds. PostgreSQL workflow run
before final retry: **33 passed**, 29.06 seconds. The 2 November repeat also
passed all **33 tests**, in 27.82 seconds.
The PostgreSQL tests use isolated schemas, not real reports.

All four Node scripts passed: frontend_app.cjs, frontend_selection.cjs,
frontend_presentation.cjs and frontend_handover.cjs. Coverage includes CSRF,
network/invalid-response errors, duplicate submissions, stale submission failures,
draft preservation while busy, explicit crop acceptance, async detector recovery,
selected-region comparisons, truthful status/count helpers, and handover
confirmation/cancellation/focus. JavaScript syntax checks passed.

Browser checks used an isolated SQLite test server (scripts/ui_test_server.py),
synthetic accounts and generated TEST ONLY bottle images. Actual APIs and installed
matching models were used; successful responses were not fabricated. Finder
reports and the second approved claim were prepared through real isolated APIs;
this was a combined browser/API test, not an entirely browser-created dataset.

| Browser workflow | Observed result |
| --- | --- |
| Registration/sign-in and protected report route | Returned to reporting after authentication |
| Two-photo lost report | Full frame plus keyboard crop explicitly confirmed; review and publish succeeded |
| Home/back navigation | Fields, consent, both photos and selections restored |
| Expired session on submission | Reauthentication restored draft and successful retry |
| Matching queued/completed | Real queued state followed by uncertain candidates; no identity claim |
| Compare selected regions | Both crops displayed; Escape restored trigger focus |
| Private claim and finder approval | Evidence, pending/approved guidance and review note displayed |
| Notification | Approval link focused claim; Mark read changed text to Read |
| Receipt | In-page cancel/Escape preserved action; explicit confirmation produced Returned |
| Mobile | 320px home and claims had equal document/client widths; menu Enter/Escape and navigation worked |
| Tablet | 768px home had equal document/client widths |
| Desktop | Homepage, reporting, matching and claim flows checked around 1280px |
| Research tools | Gallery controls rendered; comparison lab initialized both photo editors |

A browser-native confirmation stalled automation during the first receipt check.
It was replaced with the in-page dialog and retested successfully. The final
retry verified the public homepage and comparison lab on the main server.

Invalid uploads, rejected/conflicting claims, missing models, worker failures and
permissions are covered by backend regressions; these were not all manually
repeated in the browser. Network interruption is tested with frontend mocks.
Refresh during active upload has a warning and automated draft protection, but
was not independently exercised with a real interrupted upload. No claim of full
cross-browser or screen-reader certification is made.

## Screenshots

Before:

![Original homepage](../reports/phase7-before.jpg)

After (final local app):

![Homepage](../reports/phase7-final-home.jpg)

![Mobile homepage](../reports/phase7-home-mobile.jpg)

![Tablet homepage](../reports/phase7-home-tablet.jpg)

Synthetic workflows:

![Report review](../reports/phase7-report-review.jpg)

![Selected-region comparison](../reports/phase7-comparison.jpg)

![Returned claim on mobile](../reports/phase7-claim-mobile.jpg)

## Accessibility and performance

Reusable CSS tokens cover surfaces, text, spacing, borders, focus and radii.
Buttons/navigation use 44px targets; form labels, status announcements, visible
focus, numeric crop alternatives and reduced-motion styles are included. Native
HTML dialogs provide modal keyboard behavior. Manual keyboard checks covered
crop application, menus and comparison/handover dismissal and focus restoration.
WCAG 2.2 AA remains a target, not a completed conformance audit. Full contrast,
zoom, screen-reader and touch-device audits remain student-pilot work.

Uncompressed assets measured on final retry: app.js 43,557 bytes, app.css 16,924,
app-ui.js 5,126. These are sizes, not load-time or usability improvements. Lazy
card images, parallel dashboard reads and bounded preview caching reduce avoidable
work; no comparative browser performance benchmark was run.

## Remaining limitations and Phase VIII

- Match cards can repeat a report across query photos. Deduplication was deferred
  because it would change per-photo ranking and evidence semantics.
- Dashboard counts cover the first page (up to 25 reports/claims), explicitly
  labeled. Reports are newest-created first; an updated-time feed needs API work.
- Drafts are memory-only and are lost on refresh/closing. Edit/crop pages do not
  have the report form's draft restoration. Browser reload cannot recover an
  ambiguous successful upload; users are told to check My Reports before retrying.
- Old claim links may require loading older pages. Matching still requires manual
  refresh, and category checks can place useful results in uncertain sections.
- The review dialog shows original thumbnails with crop/full-frame labels; use
  the editor to inspect the exact crop before publishing.
- No general retrieval accuracy improvement follows from synthetic UI tests.

For Phase VIII, observe students completing reporting, finding, private claiming
and handover without coaching. Include keyboard and screen-reader users, real
mobile devices, weak connections, expired sessions, rejected claims and interrupted
uploads. Record completion, errors and comprehension of uncertainty. Validate
report-level match grouping before changing ordering, and gather independent
multi-instance photographs for recognition evaluation. Prioritize measured issues
before introducing new features.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:CAMPUSFIND_TEST_POSTGRES='true'
.\.venv\Scripts\python.exe -m pytest tests/test_platform.py tests/test_pilot.py -q
Remove-Item Env:CAMPUSFIND_TEST_POSTGRES
node tests/frontend_app.cjs
node tests/frontend_selection.cjs
node tests/frontend_presentation.cjs
node tests/frontend_handover.cjs
.\.venv\Scripts\python.exe -m scripts.ui_test_server
```

The acceptance server binds localhost:8017 and creates a fresh UUID directory
under .local/ui-tests. Use localhost rather than 127.0.0.1 to keep test session
cookies separate from the main application on port 8000. Do not use its synthetic
images for accuracy evidence.
