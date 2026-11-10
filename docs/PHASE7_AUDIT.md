# Phase VII frontend audit

28 October 2026. Inspected app.html/app.css/app.js, shared detection.js, gallery.html,
index.html, platform assets/CSP, reports/matches/claims/auth API contracts and existing
frontend regressions. Preserve the production ordering, authorization and state machine.

| Priority | Finding | Planned correction |
| --- | --- | --- |
| High | Hash navigation discards report fields/photos; reload warning covers photos only | In-memory route draft, dirty-navigation/reload protection; no private drafts in local storage |
| High | Late load-more/filter/match/comparison responses can update a later route | Route/request guards and comparison cancellation |
| High | Crop suggestion preview buttons default to form submit | Explicit button type; preserve explicit crop acceptance |
| High | Expired session during submission leaves no recovery route | Reauthentication link while retaining current entries; resume draft after login |
| Medium | Profile buried inside dashboard; no current-page navigation indication | Dedicated Profile, Home/Report links, active navigation and mobile menu |
| Medium | Undifferentiated report form, no review summary or photo removal | Numbered sections, type selection, previews/status, removal and final review dialog |
| Medium | Per-photo matches repeat cards; worker state shown as technical status | Keep original per-photo order, compact candidate evidence, clear queued/failed/complete states; document duplicates |
| Medium | Claims show status codes without next-step guidance | Human-readable badges, status explanation, private evidence disclosure and claim deep links |
| Medium | Dashboard only lists reports; notification unread state relies on border color | Scope-labeled summary of loaded reports/claims and textual read/unread state |
| Medium | Small text/link targets; mixed spacing; no reduced-motion rule | Reusable tokens, 44px control target, focus, contrast, reflow and reduced-motion checks |
| Medium | Crop assistant script repeatedly appended; comparison regenerates previews | Load shared script once and bound preview cache; maintain authenticated image URLs |
| Low | Research tools use older branding and stale milestone wording | Keep tools functional; clarify research status, navigation and narrow-screen controls |

Design: light warm-white surfaces, deep green identity, restrained amber lost/status
accents, system typography, consistent spacing/cards/forms. No framework migration,
new fonts, animation library, public item previews or invented dashboard figures.

Accessibility target: [WCAG 2.2 AA](https://www.w3.org/TR/WCAG22/), including keyboard
operation, visible/unobscured focus, non-drag crop controls, status announcements and
320px reflow. Automated and manual checks will be documented; they do not constitute
complete screen-reader certification.
