from __future__ import annotations

import json
from pathlib import Path

from kch_studio.advanced_runtime import KCHAdvancedRuntime
from kch_studio.mis_service import MISService

WORK_ROOT = Path(__file__).resolve().parents[2]
REPORT = WORK_ROOT / "KCH_MIS03_REEXTRACT_v0.1.0" / "evidence" / "MIS_v0_3_EXPERIMENT_REPORT.json"


def formal_example() -> tuple[dict, list[str]]:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    example = report["loss_decision_example"]
    return example, sorted(example["prior"]["masses"])


def exact_request(example: dict, states: list[str], prior: dict[str, str]) -> dict:
    return {
        "schema": "kch.mis.v03.exact-decision-request.v0.1.0",
        "request_id": "software-contract-fixture-r1",
        "purpose_id": "SOFTWARE_CONTRACT_FIXTURE",
        "jurisdiction": "Labeled software-contract fixture; no empirical authority.",
        "evidence_ids": [],
        "states": states,
        "prior": prior,
        "likelihood": example["likelihood"],
        "actions": example["loss"]["actions"],
        "losses": example["loss"]["losses"],
        "tie_action": None,
    }


def test_prospective_mis_freezes_before_observation_and_verifies(tmp_path: Path) -> None:
    example, states = formal_example()
    service = MISService(runtime_root=tmp_path / "mis")
    created = service.create_study(
        study_id="study-fixture",
        title="Prospective software contract fixture",
        purpose_id="SOFTWARE_CONTRACT_FIXTURE",
        jurisdiction="Labeled software-contract fixture; no empirical authority.",
        states=states,
        alpha={state: "1/1" for state in states},
        policy={"fixture": True, "empirical": False},
        claim_ceiling="SOFTWARE_INTEGRATION_CONTRACT_ONLY",
    )
    prior = service.study_projection("study-fixture")["next_prior"]["masses"]
    frozen = service.freeze_decision(
        study_id="study-fixture", request=exact_request(example, states, prior)
    )
    observed = service.observe(
        study_id="study-fixture",
        observed_state=states[0],
        source_unit_hash="0" * 64,
    )
    assert created["no_outcomes_recorded"] is True
    assert frozen["outcome_known_when_frozen"] is False
    assert observed["causal_quality_adjudicated"] is False
    assert service.verify_runtime()["gate"] == "PASS"
    assert service.close_study("study-fixture")["claim_promotion_authorized"] is False


def test_mis_bridges_to_csi_phl_kwandata_and_rgg_without_training(tmp_path: Path) -> None:
    example, states = formal_example()
    runtime = KCHAdvancedRuntime(tmp_path / "runtime")
    try:
        certificate = runtime.handlers["mis_exact_decide"](
            {"request": exact_request(example, states, example["prior"]["masses"])}
        )
        csi = runtime.handlers["mis_dynamic_csi_lowering"]({"certificate": certificate})
        phl = runtime.handlers["mis_decision_register_phl"]({"certificate": certificate})
        kwandata = runtime.handlers["mis_kwandata_archive"]({"certificate": certificate})
        rigor = runtime.handlers["mis_rgg_adjudicate"](
            {
                "certificate": certificate,
                "rigor_request": {
                    "profile_id": "R3_INTERNAL_CHARACTERIZATION",
                    "action": "EXECUTE_REVERSIBLE",
                    "requested_claim": "INTERNAL_CHARACTERIZATION",
                    "parent_frozen": True,
                    "after_results": False,
                    "explicit_user_authority": False,
                    "reversible": True,
                    "new_branch_id": "",
                    "evidence_use": "DECISION_SUPPORT",
                    "protocols": [],
                },
            }
        )
        assert csi["authority_created"] is False
        assert phl["bridge"]["phl_state"] == "REGISTERED_REVIEWABLE_UNTRAINED"
        assert phl["training_executed"] is False
        assert kwandata["kwandata"]["state"] == "STRUCTURED"
        assert rigor["execution_authorized"] is False
        assert runtime.mis.verify_runtime()["gate"] == "PASS"
        assert runtime.phl.status()["effective_integrity"]["gate"] == "PASS"
    finally:
        runtime.close()


def test_phl_lock_blocks_mutations_but_keeps_reads_and_zero_training(tmp_path: Path) -> None:
    runtime = KCHAdvancedRuntime(tmp_path / "runtime")
    try:
        started = runtime.handlers["phl_session_start"](
            {"trigger": "EPHEMERAL_LOCK_CONTRACT_TEST_NO_FEEDBACK", "consent": "YES"}
        )
        session_id = started["public_session_id"]
        assert runtime.handlers["phl_status"]({})["active_public_session_id"] == session_id
        try:
            runtime.handlers["mis_study_create"]({})
        except PermissionError as exc:
            assert "BLOCKED_BY_PHL_EXCLUSIVE_LOCK" in str(exc)
        else:
            raise AssertionError("ordinary mutation was not blocked by active PHL")
        assert (
            runtime.handlers["phl_session_close"]({"public_session_id": session_id})["state"]
            == "CLOSED"
        )
        status = runtime.phl.status()
        assert status["training_executed"] is False
        assert status["bridge_consistent"] is True
    finally:
        runtime.close()
