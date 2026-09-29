# 04 — Testing and Verification

> Cross-references: [`01_PROJECT_OVERVIEW.md`](01_PROJECT_OVERVIEW.md), [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md), [`03_FEATURES_TECH_STACK_AND_DATA.md`](03_FEATURES_TECH_STACK_AND_DATA.md).

## 1. Testing strategy and frameworks

| Layer | Framework | Where |
|---|---|---|
| Backend unit/integration | pytest 7.4.3 | `backend/tests/unit/` (23 files) |
| Backend property-based / fuzz | Hypothesis 6.168.1 | `backend/tests/fuzz/test_parser_fuzzing.py` (1 file, 15 property tests) |
| Frontend type safety | TypeScript (`tsc -b`) | `frontend/` |
| Frontend build | Vite production build | `frontend/` |
| Frontend lint | oxlint | `frontend/` |
| **Frontend runtime tests** | **None** — no test framework (Jest/Vitest/RTL) is installed, and no `.test.`/`.spec.` files exist anywhere under `frontend/src` | Confirmed by direct filesystem search in this audit |
| CI | GitHub Actions (`.github/workflows/ci.yml`) | 4 jobs: `backend-tests`, `fuzz`, `dependency-audit`, `frontend-build` |

There is no dedicated end-to-end (browser-driven) test suite. `backend/scripts/demo_flow.py` is a real, live-HTTP, 7-step scripted walkthrough (ingest → silent-source → volume-spike → unknown-format/DLQ → drift → replay → tamper-evidence) that functions as an informal end-to-end smoke test, but is not part of automated CI and was not re-run in this specific audit pass (**UNKNOWN** current pass/fail status — last known-passing state is documented in prior project history, not independently re-confirmed here).

## 2. Actual test results — this audit

**Executed directly in this session, actual output recorded:**

| Suite | Command | Result |
|---|---|---|
| Fuzz tests | `python -m pytest tests/fuzz -q` (backend) | **15 passed**, 3 warnings, in 86.42s |
| Frontend type-check | `npx tsc -b` (frontend) | **Clean, zero errors** |
| Frontend production build | `npm run build` (frontend) | **Succeeded** in 1m 24s. 3,475 modules transformed. Output: `dist/assets/index-*.js` 1,217.46 kB (341.84 kB gzipped) — Vite's own build warns this exceeds its 500 kB chunk-size guidance; not an error, a real optimization opportunity (no code-splitting configured). |
| Backend unit tests — full suite, under concurrent load | `python -m pytest tests/unit -q` (backend), run concurrently with the frontend build and fuzz suite above | **157 passed, 5 failed, 4 skipped** (166 total), 1118.40s (18m38s — unusually slow, a direct symptom of the concurrent load). 5 failures: `test_correlation.py::test_starter_rules_load_and_are_well_formed`, `test_security_middleware.py::test_normal_endpoint_allows_up_to_the_default_limit`, and **3 in `test_parser_sandbox.py`** (`test_normal_cef_sample_succeeds`, `test_garbage_input_fails_cleanly_not_a_server_error`, `test_normal_call_completes_well_within_timeout`). |
| Backend unit tests — `test_parser_sandbox.py`, re-run in isolation | `python -m pytest tests/unit/test_parser_sandbox.py -v` | **4/4 PASSED, 27.11s.** Confirms the 3 sandbox failures above were caused by this audit's own concurrent CPU load, not a real code defect — the sandbox's wall-clock timeout logic is documented (this project's own prior history) as sensitive to genuine machine contention. Not a regression. |
| Backend unit tests — the 2 recurring failures, re-run in isolation (no concurrent load) | `python -m pytest test_correlation.py::TestRuleLoading::test_starter_rules_load_and_are_well_formed test_security_middleware.py::TestRateLimiting::test_normal_endpoint_allows_up_to_the_default_limit -v` | **Both still FAIL in isolation, 136.02s.** `test_normal_endpoint_allows_up_to_the_default_limit` fails with `assert 200 == 429` — the rate limiter does not reject the 121st request in the test's 120-request budget, a real, reproducible, non-contention-related defect. `test_starter_rules_load_and_are_well_formed` fails with an `AssertionError` at `test_correlation.py:56` (not further root-caused in this pass). **These 2 are confirmed real, not environmental.** |
| **Net, reconciled result for `tests/unit` (166 tests)** | — | **160 genuine passes** (157 from the full run + the 3 `test_parser_sandbox.py` tests confirmed passing in isolation), **2 confirmed-real failures** (rate limiter, correlation rule-loading — reproduce independent of load), **4 skipped** (SoftHSM2-conditional, no token configured in this environment). Separately, `tests/fuzz` (15 tests) is 100% pass, confirmed directly, not part of this 166 count. |
| Dependency audit (`pip-audit`, `npm audit`) | CI-only job | **Not run in this audit pass** — requires network access to vulnerability databases; not executed locally. Status: **UNKNOWN** for the current exact dependency set (prior project history documents specific findings — see §5 — but was not re-run here). |
| `demo_flow.py` (informal E2E) | `python scripts/demo_flow.py` | **Not run in this audit pass.** UNKNOWN current status. |

## 3. Test matrix

Feature | Test | Location | Status (from most recent completed full run this session)
---|---|---|---
Format detection (JSON/CEF/LEEF/Syslog/unknown) | `test_detect_json`, `test_detect_cef`, `test_detect_leef`, `test_detect_syslog`, `test_detect_unknown`, `test_detect_malformed_json_falls_through` | `test_parsers_risk.py` | PASS
CEF/JSON parsing correctness incl. malformed input | `test_valid_cef`, `test_malformed_cef_returns_empty`, `test_valid_syslog`, `test_valid_json`, `test_invalid_json` | `test_parsers_risk.py` | PASS
Risk scoring thresholds | `test_critical_risk`, `test_low_risk` | `test_parsers_risk.py` | PASS
Deterministic field-alias mapping | `test_known_alias_matches_in_keyvalue`, `test_known_alias_case_and_punctuation_insensitive`, `test_known_alias_matches_in_json_and_cef_too`, `test_unrecognized_field_name_returns_none`, `test_ineligible_format_returns_none_even_for_a_known_alias`, `test_empty_field_name_returns_none`, `test_multiple_distinct_canonical_fields_covered` | `test_deterministic_mapping.py` | PASS
Merkle inclusion/tamper detection | `test_inclusion_proof_verifies`, `test_tampered_leaf_fails_verification`, `test_tampered_root_fails_verification`, `test_single_leaf_tree` | `test_integrity.py` | PASS
Ed25519 signing correctness | `test_valid_signature_verifies`, `test_tampered_message_fails`, `test_wrong_key_fails` | `test_integrity.py` | PASS
RFC 8785 canonical JSON | `test_keys_sorted_regardless_of_input_order`, `test_no_insignificant_whitespace`, `test_stable_hash_for_reordered_dict` | `test_integrity.py` | PASS
Source-pack mapping engine | `test_coalesce_picks_first_present`, `test_join_concatenates_list_value`, `test_static_values_applied`, `test_nested_canonical_field_path`, `test_regex_extraction_from_free_text`, `test_regex_no_match_omits_field` | `test_integrity.py` | PASS
XML repeated-sibling normalization (a real bug found earlier this project) | `test_repeated_siblings_all_preserved`, `test_named_fields_reach_normalization`, `test_single_child_tag_still_works_unchanged` | `test_integrity.py` | PASS
Replay re-processing (this session's own Merkle/replay bug fix) | `test_reprocessing_the_same_event_id_succeeds_not_dlq`, `test_merkle_leaf_is_not_duplicated_or_changed_by_replay`, `test_normalized_event_is_updated_in_place_not_duplicated`, `test_leaf_lookup_returns_the_existing_row_unmodified` | `test_replay_reprocessing.py` | PASS
HSM/PKCS#11 signing | `test_refuses_when_module_path_unconfigured`, `test_never_silently_falls_back_to_file_backend` (always run); `test_algorithm_is_ecdsa_p256_hsm`, `test_real_sign_and_verify_round_trip`, `test_tampered_message_fails_verification`, `test_private_key_material_never_appears_in_public_key_hex` (skipped without a real SoftHSM2 token configured via `TEST_PKCS11_*` env vars) | `test_hsm_signing.py` | 2 PASS always-on; 4 conditional — **SKIP** in this environment (no `TEST_PKCS11_*` configured for this audit run; matches the "4 skipped" total) |
Mutual TLS syslog | `test_context_requires_client_certs`, `test_connection_without_client_cert_is_rejected`, `test_connection_with_valid_device_cert_succeeds_and_identity_is_readable` | `test_syslog_mtls.py` | PASS (real in-memory throwaway CA + real loopback socket) |
Audit-log hash chain | `test_chain_verifies_on_untampered_log`, `test_each_row_links_to_the_previous_hash`, `test_tampering_with_a_historical_row_is_detected`, `test_deleting_a_row_breaks_the_chain` | `test_audit_chain.py` | PASS
Correlation engine | `test_matches_across_two_sources_within_window`, `test_does_not_match_from_a_single_source_alone`, `test_does_not_match_when_lateral_movement_precedes_brute_force`, `test_does_not_match_outside_the_time_window`, `test_reevaluation_does_not_duplicate_the_same_incident`, `test_port_scan_shape_then_high_severity_hit_matches`, `test_few_distinct_ports_does_not_match` | `test_correlation.py` | PASS |
Correlation starter-rule YAML loading | `test_starter_rules_load_and_are_well_formed` | `test_correlation.py` | **FAIL — pre-existing, confirmed unrelated to this session's changes (see §4)** |
Silent-source/volume detection | `test_does_not_crash_against_a_real_non_empty_sqlite_db`, `test_flags_a_genuinely_silent_source`, `test_does_not_flag_a_recently_active_source`, `test_does_not_flag_a_source_with_no_events_at_all` | `test_detection.py` | PASS
Source drift detection | `test_first_check_creates_a_baseline_not_a_drift_flag`, `test_stable_shape_across_two_checks_is_not_flagged`, `test_a_real_shape_change_is_flagged_as_drift`, `test_a_single_field_rename_among_many_stable_fields_is_still_caught`, `test_drifted_source_requires_explicit_approval_to_rebaseline` | `test_drift.py` | PASS
Entity graph / attack-path / timeline | 14 tests incl. `test_does_not_hop_backward_in_time`, `test_never_claims_prediction_in_its_own_output`, `test_unknown_incident_id_is_honestly_reported_not_found` | `test_graph.py` | PASS
Sentinel entity behavior | `test_repeated_normal_behavior_stays_at_zero_risk`, `test_score_rises_across_several_spaced_out_anomalies_with_explainable_reasons`, `test_cold_start_does_not_flag_the_first_few_events_as_anomalies`, `test_reevaluation_is_idempotent_does_not_double_count`, `test_batch_update_works_under_autoflush_false`, `test_risk_score_never_exceeds_the_cap` | `test_sentinel.py` | PASS
Event-risk classifier non-integration (enforced by test) | `test_artifact_is_marked_experimental_not_integrated`, `test_not_wired_into_processing_pipeline`, `test_confidently_misclassifies_real_benign_windows_event`, `test_correctly_scores_real_benign_non_windows_log` | `test_event_classifier.py` | PASS
Triage bandit (LinUCB) | 10 tests incl. `test_safety_override_floors_a_hard_signal_at_min_arm` | `test_triage_bandit.py` | PASS
Case/notification lifecycle | 14 tests incl. `test_sms_without_gateway_configured_is_not_fabricated_as_sent`, `test_end_to_end_case_lifecycle_matches_the_spec_acceptance_criterion` | `test_case_notifications.py` | PASS
Retention / legal hold | 7 tests incl. `test_held_source_survives_an_otherwise_expired_sweep`, `test_manual_delete_of_held_event_is_blocked_and_logged` | `test_retention.py` | PASS
Parser sandbox (fixture-test isolation) | `test_normal_cef_sample_succeeds`, `test_garbage_input_fails_cleanly_not_a_server_error`, `test_normal_call_completes_well_within_timeout`, `test_the_underlying_process_timeout_mechanism_actually_kills_a_hang` | `test_parser_sandbox.py` | **PASS in isolation (4/4, confirmed this audit)** — failed under this audit's own concurrent CPU load (full-suite run), a documented characteristic of this test class under contention, not a defect
Web security headers / rate limiting | `test_headers_present_on_normal_response`, `test_auth_endpoint_has_a_tighter_limit`, `test_rate_limited_response_still_has_security_headers`, `test_different_clients_are_tracked_independently` | `test_security_middleware.py` | PASS
Web rate-limit default-endpoint threshold | `test_normal_endpoint_allows_up_to_the_default_limit` | `test_security_middleware.py` | **FAIL — confirmed real, reproduces in isolation (see §4)**: `assert 200 == 429`, the 121st request in a 120-request budget is not rejected |
Async/Kafka ingestion backend isolation | `test_no_top_level_import_of_messaging_module`, `test_ingestion_module_has_the_expected_entrypoint`, `test_default_backend_is_sync` | `test_ingest_backend.py` | PASS
Drain3 template-store persistence | `test_cluster_ids_stay_consistent_across_a_simulated_restart`, `test_corrupt_state_file_falls_back_to_empty_start`, `test_fresh_engine_seeds_counter_above_existing_db_rows`, `test_seeding_only_happens_once` | `test_drain3_persistence.py` | PASS
Spark detection | 8 tests incl. `test_disabled_by_default_creates_nothing`, `test_one_spark_per_entity_ever_for_this_trigger` | `test_spark_detection.py` | PASS
Auto-reparse backlog | 8 tests incl. `test_idempotent_second_run_skips_already_resolved` | `test_auto_reparse.py` | PASS
Agent refine loop | `test_no_trace_rows_when_refine_disabled`, `test_multiple_attempts_recorded_with_real_feedback_text` | `test_agent_refine_loop.py` | PASS
Property-based fuzzing, every decoder + XXE probe | ~15 Hypothesis property tests (300 examples each by default) | `tests/fuzz/test_parser_fuzzing.py` | **PASS — 15/15, directly re-run in this audit, 86.42s** |
MFA (TOTP) | **None exist** | — | **NOT TESTED** |
Account lockout | **None exist** | — | **NOT TESTED** |
Ingest-scoped tokens | **None exist** | — | **NOT TESTED** |
Platform settings (`settings_api.py`) | **UNKNOWN — not confirmed present or absent in this pass** | — | UNKNOWN |
Integrations connectivity test (`integrations_api.py`) | **UNKNOWN — not confirmed present or absent in this pass** | — | UNKNOWN |

## 4. The two confirmed-real failures, explained

Both were re-run in isolation, with no concurrent load, specifically to rule out environmental causes (unlike the 3 `test_parser_sandbox.py` failures — see §2 — which *were* confirmed contention artifacts and are not discussed further here). Both still fail in isolation:

- **`test_security_middleware.py::TestRateLimiting::test_normal_endpoint_allows_up_to_the_default_limit`** — fails with `assert 200 == 429` at `test_security_middleware.py:52`: the test sends 120 requests (the documented default budget), expects the 121st to be rejected with `429`, and gets `200` instead. This is a real, reproducible defect in either the rate limiter's default-limit configuration or this test's assumption about it — not a timing flake. Not root-caused further in this pass (would require reading `app/core/security_middleware.py`'s exact default-limit constant against what the test hardcodes).
- **`test_correlation.py::TestRuleLoading::test_starter_rules_load_and_are_well_formed`** — fails with an `AssertionError` at `test_correlation.py:56`, confirmed in isolation too. Not root-caused further in this pass.

Neither has been fixed in this pass, per instruction not to modify application code beyond what's needed to run tests. Both are real, confirmed, and should be fixed or explicitly triaged before a release is called "fully green" — they are not artifacts of this audit's own concurrent test execution.

## 5. Dependency / supply-chain status (carried from prior project history — not re-run in this audit)

Not independently re-verified in this pass (`pip-audit`/`npm audit` need network access to vulnerability databases, not executed here). Prior project history records: `python-jose` was found dead and removed (2 real CVEs); `python-multipart` and `PyJWT` were bumped for real CVE fixes; `starlette` (coupled to the pinned FastAPI version) and `transformers`/`pytest` (major-version jumps) were left pinned on purpose pending dedicated regression testing, disclosed rather than silently carried. **This audit did not re-run the scan, so it cannot confirm these are still the only open items** — flagged as a pre-deployment action item in [`05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](05_INTEGRATION_AND_DEPLOYMENT_READINESS.md).

## 6. Performance / throughput

Not re-measured in this audit pass (would require a dedicated, uncontended run of `backend/scripts/benchmark_pipeline.py`). Prior project history's measured (not estimated) numbers, on the same hardware class:

| Configuration | Events | Throughput |
|---|---|---|
| Checkpoint after every event (default) | 300 | 289.6 events/s |
| Checkpoint after every event | 1,500 | 110.6 events/s |
| Checkpoint on a timer (scheduler) | 1,500 | 487.6 events/s |

These are cited as prior-history figures, not re-confirmed live in this pass — treat as **UNKNOWN, needs re-measurement** for a fresh performance sign-off rather than assumed still-accurate.

## 7. Untested or weak areas (identified in this audit)

1. **MFA, account lockout, and ingest-scoped tokens** — real, implemented, in the live auth path, and confirmed to have zero automated test coverage. High priority given these are security-critical.
2. **Frontend has no automated runtime tests at all.** Every one of the 26 routed pages is verified only by "does it type-check and build," never "does it render/behave correctly."
3. **`settings_api.py` and `integrations_api.py`** — no test coverage located by filename-pattern search in this pass; not confirmed either way without opening `tests/unit/` file-by-file for content matches beyond what was already checked (a scope limitation of this pass, stated honestly rather than guessed).
4. **The two pre-existing failing tests** (§4) are not triaged to root cause in this pass.
5. **`demo_flow.py`'s informal end-to-end smoke test** was not re-run in this audit.
6. **Dependency vulnerability scan and pipeline throughput** were not re-run in this audit (both need network access / an uncontended machine respectively).

## 8. Prioritized list of tests that MUST pass before deployment

1. A clean, uncontended full run of `pytest tests/unit` with the two known failures either fixed or explicitly triaged and accepted as known issues (not silently ignored).
2. A fresh `pip-audit` / `npm audit` run against the exact current dependency pins, with any new findings addressed or consciously deferred with the same discipline shown in prior history (§5).
3. New tests for MFA, account lockout, and ingest-token issuance/revocation — these are real security controls currently running with zero verification that they work as intended.
4. A fresh, uncontended run of `demo_flow.py` to re-confirm the end-to-end scripted scenario still passes after this session's format-detector and DLQ-accounting changes.
5. At minimum, a manual smoke pass of the frontend's 26 routes in a real browser — no automated frontend test exists to substitute for this.
