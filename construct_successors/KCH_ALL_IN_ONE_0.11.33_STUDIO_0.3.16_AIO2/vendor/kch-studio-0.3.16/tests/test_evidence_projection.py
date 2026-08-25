from __future__ import annotations

import copy
from pathlib import Path

from kch_studio.advanced_runtime import KCHAdvancedRuntime
from kch_studio.evidence_projection import (
    EvidencePreservingClosure,
    canonical_sha256,
)
from kch_studio.full_read_contract import FullReadService
from kch_studio.permissions import PermissionGovernor


def sealed_monitor(*, exit_code: int = 7) -> dict[str, object]:
    monitor: dict[str, object] = {
        "schema": "kch.commitment-evidence.v0.1.0",
        "commitment_id": "MONITOR-R20",
        "label": "R20_TEST",
        "mode": "OWNED_SUPERVISOR",
        "worker_pid": 321,
        "process_token": "windows-filetime:test",
        "status": "COMPLETED_FAIL",
        "latest_observation": {
            "commitment_id": "MONITOR-R20",
            "status": "COMPLETED_FAIL",
            "terminal": True,
            "exit_code": exit_code,
            "expected_exit_codes": [0],
            "logs": {
                "stdout.log": {"exists": True, "bytes": 2, "sha256": "a" * 64},
                "stderr.log": {"exists": True, "bytes": 3, "sha256": "b" * 64},
            },
            "artifacts": {
                "result.json": {"exists": True, "bytes": 4, "sha256": "c" * 64}
            },
            "terminal_receipt": {
                "valid": True,
                "claimed_sha256": "d" * 64,
                "actual_sha256": "d" * 64,
            },
            "relaunch_performed": False,
        },
        "claim_ceiling": "LOCAL_TEST",
    }
    monitor["sha256"] = canonical_sha256(monitor)
    return monitor


def valid_envelope(tmp_path: Path) -> dict[str, object]:
    stable = tmp_path / "stable"
    stable.mkdir(parents=True)
    (stable / "first.txt").write_text("alpha\n", encoding="utf-8", newline="\n")
    (stable / "second.txt").write_text(
        "# KCH 0.11 — exact Unicode\n", encoding="utf-8", newline="\n"
    )
    service = FullReadService(stable, PermissionGovernor(tmp_path / "permissions"))
    batch = service.read_batch(
        [
            {"path": "first.txt", "expected_evidence_spans": ["alpha"]},
            {
                "path": "second.txt",
                "expected_evidence_spans": ["# KCH 0.11 — exact Unicode"],
            },
        ],
        requested_order="SOURCE_NATIVE_ORDER",
    )
    return {
        "arm": "R20_TEST",
        "authoritative_model": "gpt-5.6-luna",
        "mission_completed_after_interruption": True,
        "full_read_batch": batch,
        "full_read_verification": service.verify_batch(batch),
        "monitor_evidence": sealed_monitor(),
        "source_mutation": False,
        "phl_authorized": True,
        "phl_training_executed": False,
        "phl_real_executed": False,
        "limitations": ["LOCAL_TEST_ONLY"],
    }


def test_materializes_exact_closure_and_retains_original_content(tmp_path: Path) -> None:
    envelope = valid_envelope(tmp_path)
    closure = EvidencePreservingClosure.materialize(envelope)

    assert closure["gate"] == "PASS_BOUNDED"
    assert closure["process"]["exit_code"] == 7
    assert closure["process"]["status"] == "COMPLETED_FAIL"
    assert closure["artifact_presence_promoted_to_success"] is False
    assert closure["ordered_file_receipts"][1]["exact_span_evidence"]["spans"][0][
        "expected_text"
    ] == "# KCH 0.11 — exact Unicode"
    embedded = closure["input_envelope"]["full_read_batch"]["receipts"]
    assert embedded[0]["content"] == "alpha\n"
    assert embedded[1]["content"] == "# KCH 0.11 — exact Unicode\n"
    assert EvidencePreservingClosure.verify(closure)["gate"] == "PASS_VERIFIED"


def test_compacted_original_receipt_fails_closed(tmp_path: Path) -> None:
    envelope = valid_envelope(tmp_path)
    del envelope["full_read_batch"]["receipts"][0]["content"]

    closure = EvidencePreservingClosure.materialize(envelope)

    assert closure["gate"] == "FAIL_EVIDENCE_INTEGRITY"
    codes = {issue["code"] for issue in closure["issues"]}
    assert "RECEIPT_SEAL_INVALID" in codes
    assert "TRANSPORTED_CONTENT_NOT_RETAINED" in codes
    assert EvidencePreservingClosure.verify(closure)["gate"] == (
        "FAIL_NOT_SOURCE_DERIVABLE"
    )


def test_resealed_manual_transcription_is_not_source_derivable(tmp_path: Path) -> None:
    closure = EvidencePreservingClosure.materialize(valid_envelope(tmp_path))
    closure["ordered_file_receipts"][1]["exact_span_evidence"]["spans"][0][
        "expected_text"
    ] = "# KCH 0.11 â€” corrupted"
    closure["sha256"] = canonical_sha256(
        {key: value for key, value in closure.items() if key != "sha256"}
    )

    result = EvidencePreservingClosure.verify(closure)

    assert result["closure_seal"]["match"] is True
    assert result["regenerated_match"] is False
    assert result["gate"] == "FAIL_NOT_SOURCE_DERIVABLE"


def test_missing_os_exit_code_is_a_strong_evidence_failure(tmp_path: Path) -> None:
    envelope = valid_envelope(tmp_path)
    monitor = copy.deepcopy(envelope["monitor_evidence"])
    monitor["latest_observation"]["exit_code"] = None
    monitor["sha256"] = canonical_sha256(
        {key: value for key, value in monitor.items() if key != "sha256"}
    )
    envelope["monitor_evidence"] = monitor

    closure = EvidencePreservingClosure.materialize(envelope)

    assert closure["gate"] == "FAIL_EVIDENCE_INTEGRITY"
    assert "OS_EXIT_CODE_NOT_CAPTURED" in {
        issue["code"] for issue in closure["issues"]
    }


def test_runtime_exposes_materialize_and_verify_without_manual_rebuild(
    tmp_path: Path,
) -> None:
    envelope = valid_envelope(tmp_path / "fixture")
    runtime = KCHAdvancedRuntime(
        tmp_path / "runtime", stable_root=tmp_path / "fixture" / "stable"
    )
    try:
        closure = runtime.handlers["evidence_closure_materialize"](
            {"envelope": envelope}
        )
        verified = runtime.handlers["evidence_closure_verify"](
            {"closure": closure}
        )
        assert closure["gate"] == "PASS_BOUNDED"
        assert verified["gate"] == "PASS_VERIFIED"
    finally:
        runtime.close()
