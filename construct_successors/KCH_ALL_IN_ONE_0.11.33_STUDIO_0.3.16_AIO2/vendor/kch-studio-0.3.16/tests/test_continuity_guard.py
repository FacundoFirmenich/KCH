from kch_studio.continuity_guard import (
    ContinuityAndBurdenGovernor,
    ContinuousPeriodLedgerCompiler,
    EpistemicClaimTypeChecker,
    RemoteTransportPreflight,
    SourceFitnessGate,
    TemporalScaleContractCompiler,
)


def test_reading_gate_refuses_unrecovered_truncation(tmp_path):
    guard = ContinuityAndBurdenGovernor(tmp_path)
    result = guard.adjudicate_reading(
        {
            "source_id": "thread",
            "pages_read": 2,
            "turns_read": 20,
            "cursor_exhausted": True,
            "truncated_items": 3,
            "recovered_items": 2,
        }
    )
    assert result["gate"] == "INCOMPLETE_READING_BLOCK"
    assert result["may_claim_complete_reading"] is False


def test_expensive_stale_noop_is_blocked(tmp_path):
    guard = ContinuityAndBurdenGovernor(tmp_path)
    guard.set_mission("Preserve objective", "user-turn-1")
    result = guard.preflight(
        {
            "name": "full battery",
            "expensive": True,
            "state_age_seconds": 60,
            "material_change": False,
            "cheap_probe_passed": False,
            "storage_plan_verified": False,
        }
    )
    assert result["gate"] == "BLOCK"
    assert "NO_MATERIAL_CHANGE_SKIP_EXPENSIVE_RUN" in result["failures"]
    assert "CHEAP_PROBE_REQUIRED_FIRST" in result["failures"]


def test_recurrence_requires_control_and_ledger_verifies(tmp_path):
    guard = ContinuityAndBurdenGovernor(tmp_path)
    guard.set_mission("Prevent cost transfer", "user-turn")
    record = {
        "failure_class": "FALSE_COMPLETE_READING",
        "dimensions": ["TIME_LOSS", "REPEATED_CONTEXT"],
        "user_report_exact": "reported burden",
        "source_ref": "thread:turn",
    }
    guard.record_harm(record)
    second = guard.record_harm(record)
    assert second["severity"] == "CRITICAL_RECURRENCE_BLOCK"
    blocked = guard.preflight(
        {
            "name": "claim complete",
            "failure_class": "FALSE_COMPLETE_READING",
            "state_age_seconds": 0,
        }
    )
    assert "KNOWN_RECURRENT_FAILURE_CONTROL_NOT_PASSED" in blocked["failures"]
    assert guard.verify()["gate"] == "PASS"


def test_destructive_action_needs_custody_hash(tmp_path):
    guard = ContinuityAndBurdenGovernor(tmp_path)
    guard.set_mission("Preserve evidence", "user-turn")
    result = guard.preflight(
        {
            "name": "delete local archive",
            "destructive": True,
            "state_age_seconds": 0,
            "storage_plan_verified": True,
            "backup_hash_verified": False,
        }
    )
    assert result["gate"] == "BLOCK"
    assert "BACKUP_HASH_NOT_VERIFIED" in result["failures"]


def test_verified_protocol_must_be_reused(tmp_path):
    guard = ContinuityAndBurdenGovernor(tmp_path)
    guard.set_mission("Reuse verified science", "user-turn")
    guard.register_protocol({"name":"minimum-period-learning","version":"1","source_ref":"attachment","content_hash":"abc","tags":["TEMPORAL_LEARNING"],"verified":True})
    assert guard.resolve_protocols(["TEMPORAL_LEARNING"])["count"] == 1
    result = guard.preflight({"name":"new design","state_age_seconds":0,"verified_protocol_matches":1,"verified_protocol_reused":False})
    assert "VERIFIED_PROTOCOL_EXISTS_BUT_WAS_NOT_REUSED" in result["failures"]


def test_temporal_scale_compiler_separates_resolution_and_learning_period():
    invalid = TemporalScaleContractCompiler.compile({"timestamp_resolution_seconds":1,"prediction_horizon_seconds":86400,"minimum_period_seconds":86400,"learning_input_period_seconds":1,"learning_output_period_seconds":86400,"update_trigger":"EVENT_COUNT"})
    assert invalid["gate"] == "TEMPORAL_SCALE_CONTRACT_BLOCK"
    valid = TemporalScaleContractCompiler.compile({"timestamp_resolution_seconds":1,"prediction_horizon_seconds":86400,"minimum_period_seconds":86400,"learning_input_period_seconds":86400,"learning_output_period_seconds":86400,"update_trigger":"MINIMUM_PERIOD_CLOSE"})
    assert valid["gate"] == "PASS"


def test_irrelevant_interrogation_and_unilateral_stop_are_blocked(tmp_path):
    guard = ContinuityAndBurdenGovernor(tmp_path)
    guard.set_mission("Continue authorized audit", "user-turn")
    result = guard.preflight({"name":"stop and interrogate","state_age_seconds":0,"stops_mission":True,"explicit_user_stop":False,"asks_off_mission_question":True,"task_relevance_evidence":False,"repeats_question":True,"same_question_rejected":True})
    assert "UNAUTHORIZED_MISSION_STOPPAGE" in result["failures"]
    assert "IRRELEVANT_INTERROGATION_DERAILMENT" in result["failures"]
    assert "REJECTED_QUESTION_LOOP" in result["failures"]


def test_norm_cannot_be_reported_as_observation():
    result = EpistemicClaimTypeChecker.adjudicate({"statement":"no global winner","claim_type":"EMPIRICAL_OBSERVATION","evidence_type":"GOVERNANCE_CONTRACT","architectural_prohibition_reported_as_observation":True})
    assert result["gate"] == "BLOCK"
    assert "ARCHITECTURAL_NORM_IS_NOT_EMPIRICAL_RESULT" in result["failures"]


def test_remote_transport_blocks_empty_or_mutated_wrapper():
    bad = RemoteTransportPreflight.adjudicate({"payload_bytes":0,"local_syntax_passed":True,"remote_syntax_passed":True,"local_sha256":"a","remote_sha256":"b","forbidden_old_markers_absent":False,"dry_run_contract_passed":True})
    assert bad["launch_authorized"] is False
    good = RemoteTransportPreflight.adjudicate({"payload_bytes":42,"local_syntax_passed":True,"remote_syntax_passed":True,"local_sha256":"a","remote_sha256":"a","forbidden_old_markers_absent":True,"dry_run_contract_passed":True})
    assert good["gate"] == "PASS"


def test_discontinuous_active_days_cannot_masquerade_as_daily_learning():
    bad = ContinuousPeriodLedgerCompiler.compile({"expected_periods": 365, "periods": [{"index": i, "state": "OBSERVED"} for i in range(220)]})
    assert bad["gate"] == "DISCONTINUOUS_CALENDAR_BLOCK"
    complete = ContinuousPeriodLedgerCompiler.compile({"expected_periods": 3, "periods": [{"index": 0, "state": "OBSERVED"}, {"index": 1, "state": "NO_EVENT"}, {"index": 2, "state": "NOT_ESTIMABLE"}]})
    assert complete["gate"] == "PASS"
    assert complete["observed_support_complete"] is False


def test_source_fitness_blocks_220_of_365_when_daily_observation_required():
    result = SourceFitnessGate.adjudicate({"target_start":"2025-01-01", "target_end":"2026-01-01", "all_planned_times_in_window":True, "all_outcome_times_in_window":False, "continuous_ledger_passed":True, "expected_periods":365, "observed_periods":220, "requires_observed_every_period":True, "jurisdiction_support_passed":True})
    assert result["gate"] == "SOURCE_FITNESS_BLOCK"
    assert result["training_authorized"] is False
    assert result["coverage"] == 220 / 365


def test_destructive_scope_requires_explicit_authority_and_exact_targets(tmp_path):
    guard = ContinuityAndBurdenGovernor(tmp_path)
    guard.set_mission("Preserve and continue task", "user-turn")
    result = guard.preflight({"name":"cancel automations and terminate task", "destructive":True, "state_age_seconds":0, "storage_plan_verified":True, "backup_hash_verified":True})
    assert "DESTRUCTIVE_SCOPE_NOT_AUTHORIZED" in result["failures"]
    assert "DESTRUCTIVE_TARGETS_NOT_RESOLVED" in result["failures"]
