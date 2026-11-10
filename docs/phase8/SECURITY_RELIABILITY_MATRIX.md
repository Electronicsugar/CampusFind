# Security/reliability readiness matrix

VIII-A.2 fresh additional evidence in tests/test_preflight.py:

| Scenario | Exact additional test | Evidence boundary |
| --- | --- | --- |
| A/B/C direct IDs, unauthorized edits/evidence/actions, duplicate return, notification and deleted image | test_three_user_direct_boundaries_and_duplicate_transitions | API integration on disposable SQLite/PostgreSQL; active cohort reports/images intentionally member-visible |
| Expired session and authorized retry | test_session_expiry_denies_direct_request_and_relogin_succeeds | Real fixture auth; not browser refresh persistence |
| SQL failure and restoration | test_database_outage_is_generic_and_recovers_without_server_stop | Synthetic engine fault, not real server/network shutdown |
| HTTPS cookie, Host/origin/CSRF, registration and log redaction | test_https_cookie_csrf_host_forwarded_and_logs | HTTPS TestClient; proxy-address parser rejects wildcard; no live TLS/proxy verification |
| Safe config, repeated inspection, redaction, wrong-target/path refusal | test_static_preflight_repeated_redacted_and_no_connection; test_preflight_refuses_unsafe_targets; test_preflight_missing_secret_paths_and_empty; test_placeholder_config_cannot_pass | Offline checks; actual ACL, role memberships, service environment still operator-owned |
| DB checker failure redaction/cleanup | test_database_inspection_is_read_only_and_redacts_errors | Mock connection failure; actual read-only SQL verification of a dedicated pilot not executed |
| Canary failure classes | test_canary_missing_loading_and_runtime_stages | Synthetic artifacts/stubs; real installed-model canary executed separately |

New guarded restore evidence: [RECOVERY_DRILL_REPORT](RECOVERY_DRILL_REPORT.md).
Original rows below identify remaining deployment preflights; historical VII
browser results remain historical. No existing approval gate is auto-closed.

Tests below are actual functions in tests/test_platform.py (P) or test_pilot.py
(O). Fresh suite results are in the baseline/report. Historical browser evidence
means Phase VII isolated acceptance, not a new participant deployment check.
No security certification is asserted. “Preflight” blocks participants until verified.

| Scenario / existing protection | Automated test | Browser/manual evidence | Gap / pilot impact / follow-up / blocks? |
| --- | --- | --- | --- |
| Anonymous reports and private images: current auth/expiry | P test_private_images_multiphoto_metadata_and_report_permissions | VII login gate | Test deployed proxy with anonymous client; privacy preflight YES |
| Evidence unauthorized access: claim parties/admin only | P test_claim_privacy_review_conflicts_return_notifications | VII two-role claim workflow | Third-account deployed check pending; privacy preflight YES |
| Cross-user report changes: owner checks | P test_private_images_multiphoto_metadata_and_report_permissions | Automated only | Deployed two-account preflight pending; YES |
| Unauthorized/self claim approval and return authority | P test_claim_privacy_review_conflicts_return_notifications | VII finder/claimant handover | Recheck fixture role assignments; YES preflight |
| CSRF/origin rejection | P test_migration_auth_hash_cookie_csrf_logout; O test_trusted_host_and_origin_production | Node request header test | Live HTTPS/Host proxy unverified; YES |
| Session expiry/revocation | P test_edit_validation_crop_and_session_expiration; test_duplicate_registration_and_revoked_session | VII draft reauthentication | Memory-only reload loss; run U08; warning |
| Duplicate submission: frontend busy guard | tests/frontend_app.cjs | VII reporting | Ambiguous commit can duplicate on retry; My Reports first; warning/U08 |
| Interrupted uploads: atomic file/database rollback | O test_failed_atomic_upload_leaves_no_photo | Frontend mocked network failure | Real device dropped-upload recovery unexecuted; preflight required |
| Invalid images/size/consent | P test_invalid_upload_rolls_back_database_and_files; test_security_headers_missing_consent_and_upload_limit | Automated only | Proxy body limits need verification; YES preflight |
| Worker interruption/durable pending/cache | O test_matching_interruption_rolls_back_and_retries; test_postgres_actual_worker_process_crash | VII queued/finished states | Dedicated production worker/alerts not deployed; YES |
| Missing model preserves report | P test_model_failure_preserves_report_and_retry_job | Automated only | Run approved installed-model canary before sessions; YES preflight |
| Database unavailable: generic 503/rollback/readiness | backend/database.py, operations.py; O test_readiness_metrics_and_fail_closed_registration | Code inspected only for outage path | Controlled dedicated-instance outage rehearsal missing; YES preflight |
| Retention/deletion: expiry redaction, durable file cleanup | P test_retention_removes_images_and_evidence; O test_file_deletion_failure_is_durable_and_retried; test_expired_evidence_redacted_without_worker | VII no destructive real tests | Approved retention/withdrawal backup obligations pending; YES |
| Backup/restore: guarded new-database drill | O test_postgres_duplicate_worker_and_backup_guard; scripts/recovery_drill.py | Historical Phase V drill only; not rerun VIII-A | Encrypted off-machine restore, RPO/RTO and session revocation rehearsal pending; YES |
| Rate limits | P test_rate_limit_failed_auth | Automated only | Restricted-network limits/alert tuning unverified; preflight YES |
| Admin restriction/moderation/audit | P test_withdraw_reopen_admin_hide; O test_admin_whitespace_reason_rejected | Automated only | Designated admin/access review pending; YES |

Do not simulate attacks/outages on the populated development app. Use a dedicated
staged PostgreSQL instance and operator-controlled network. Record observed status,
test identity and date without credentials or evidence text. Stop conditions and
incident clearance: [privacy](PRIVACY_AND_SAFETY.md).
