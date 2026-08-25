from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _seal(value: dict[str, Any], field: str = "sha256") -> dict[str, Any]:
    value[field] = canonical_sha256(
        {key: item for key, item in value.items() if key != field}
    )
    return value


def _seal_match(value: dict[str, Any], field: str) -> dict[str, Any]:
    claimed = value.get(field)
    calculated = canonical_sha256(
        {key: item for key, item in value.items() if key != field}
    )
    return {
        "field": field,
        "claimed": claimed,
        "calculated": calculated,
        "match": isinstance(claimed, str) and claimed == calculated,
    }


def _issue(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


class EvidencePreservingClosure:
    """Project task evidence without mutating or manually retranscribing receipts."""

    @staticmethod
    def materialize(envelope: dict[str, Any]) -> dict[str, Any]:
        source = copy.deepcopy(envelope)
        required = {
            "arm",
            "authoritative_model",
            "mission_completed_after_interruption",
            "full_read_batch",
            "full_read_verification",
            "monitor_evidence",
            "source_mutation",
            "phl_authorized",
            "phl_training_executed",
            "phl_real_executed",
        }
        missing = sorted(required - set(source))
        if missing:
            raise ValueError(f"envelope missing required fields: {', '.join(missing)}")

        batch = source["full_read_batch"]
        verification = source["full_read_verification"]
        monitor = source["monitor_evidence"]
        if not all(isinstance(item, dict) for item in (batch, verification, monitor)):
            raise TypeError("full-read and monitor evidence must be objects")
        receipts = batch.get("receipts")
        if not isinstance(receipts, list) or not receipts:
            raise ValueError("full_read_batch.receipts must be a non-empty list")

        issues: list[dict[str, str]] = []
        batch_seal = _seal_match(batch, "batch_payload_sha256")
        if not batch_seal["match"]:
            issues.append(_issue("BATCH_SEAL_INVALID", "full-read batch seal mismatch"))
        receipt_seals = []
        for ordinal, receipt in enumerate(receipts, start=1):
            if not isinstance(receipt, dict):
                raise TypeError("each full-read receipt must be an object")
            seal = _seal_match(receipt, "receipt_payload_sha256")
            receipt_seals.append(seal)
            if not seal["match"]:
                issues.append(
                    _issue(
                        "RECEIPT_SEAL_INVALID",
                        f"full-read receipt {ordinal} seal mismatch",
                    )
                )
            if receipt.get("complete_content_transported") is True and "content" not in receipt:
                issues.append(
                    _issue(
                        "TRANSPORTED_CONTENT_NOT_RETAINED",
                        f"receipt {ordinal} claims transported content but omits it",
                    )
                )

        expected_ordinals = list(range(1, len(receipts) + 1))
        ordinals = [receipt.get("ordinal") for receipt in receipts]
        requested_paths = list(batch.get("requested_paths", []))
        recorded_paths = [receipt.get("requested_path") for receipt in receipts]
        if ordinals != expected_ordinals:
            issues.append(_issue("ORDINALS_NOT_EXACT", "receipt ordinals are not contiguous"))
        if requested_paths != recorded_paths:
            issues.append(
                _issue("SOURCE_ORDER_NOT_EXACT", "recorded receipt order changed")
            )
        if batch.get("gate") != "PASS" or not batch.get(
            "complete_read_batch_claim_allowed"
        ):
            issues.append(_issue("FULL_READ_GATE_NOT_PASS", "complete reading not allowed"))
        if verification.get("gate") != "PASS_VERIFIED_AGAINST_SOURCE":
            issues.append(
                _issue("SOURCE_VERIFICATION_NOT_PASS", "batch is not source-verified")
            )
        verification_batch_seal = verification.get("batch_seal", {})
        if not verification_batch_seal.get("match") or (
            verification_batch_seal.get("claimed")
            != batch.get("batch_payload_sha256")
        ):
            issues.append(
                _issue(
                    "VERIFICATION_NOT_BOUND_TO_BATCH",
                    "verification does not bind the embedded batch seal",
                )
            )

        monitor_seal = _seal_match(monitor, "sha256")
        if not monitor_seal["match"]:
            issues.append(_issue("MONITOR_SEAL_INVALID", "monitor evidence seal mismatch"))
        observation = monitor.get("latest_observation")
        if not isinstance(observation, dict):
            raise ValueError("monitor_evidence.latest_observation must be an object")
        terminal_receipt = observation.get("terminal_receipt", {})
        if not observation.get("terminal") or not terminal_receipt.get("valid"):
            issues.append(
                _issue("TERMINAL_EVIDENCE_NOT_STRONG", "terminal receipt is not valid")
            )
        if not isinstance(observation.get("exit_code"), int):
            issues.append(
                _issue("OS_EXIT_CODE_NOT_CAPTURED", "terminal exit code is not an integer")
            )

        ordered_file_receipts = []
        for receipt in receipts:
            ordered_file_receipts.append(
                {
                    "ordinal": receipt.get("ordinal"),
                    "requested_path": receipt.get("requested_path"),
                    "path": receipt.get("path"),
                    "method": receipt.get("method"),
                    "encoding": receipt.get("encoding"),
                    "bytes": receipt.get("byte_count"),
                    "physical_lines": receipt.get("physical_lines"),
                    "sha256": receipt.get("sha256"),
                    "stable_across_independent_reads": receipt.get(
                        "stable_across_independent_reads"
                    ),
                    "complete_content_transported": receipt.get(
                        "complete_content_transported"
                    ),
                    "exact_span_evidence": copy.deepcopy(
                        receipt.get("exact_span_evidence")
                    ),
                    "source_receipt_payload_sha256": receipt.get(
                        "receipt_payload_sha256"
                    ),
                }
            )

        process = {
            "commitment_id": monitor.get("commitment_id"),
            "worker_pid": monitor.get("worker_pid"),
            "process_identity": monitor.get("process_token"),
            "status": observation.get("status"),
            "terminal": observation.get("terminal"),
            "exit_code": observation.get("exit_code"),
            "expected_exit_codes": copy.deepcopy(
                observation.get("expected_exit_codes")
            ),
            "terminal_receipt": copy.deepcopy(terminal_receipt),
            "logs": copy.deepcopy(observation.get("logs")),
            "artifacts": copy.deepcopy(observation.get("artifacts")),
            "relaunch_performed": observation.get("relaunch_performed"),
            "monitor_evidence_sha256": monitor.get("sha256"),
        }
        payload: dict[str, Any] = {
            "schema": "kch.evidence-preserving-task-closure.v0.1.0",
            "gate": "PASS_BOUNDED" if not issues else "FAIL_EVIDENCE_INTEGRITY",
            "claims_allowed": not issues,
            "arm": source["arm"],
            "authoritative_model": source["authoritative_model"],
            "mission_completed_after_interruption": source[
                "mission_completed_after_interruption"
            ],
            "ordered_file_receipts": ordered_file_receipts,
            "process": process,
            "artifact_presence_promoted_to_success": False,
            "source_mutation": source["source_mutation"],
            "phl_authorized": source["phl_authorized"],
            "phl_training_executed": source["phl_training_executed"],
            "phl_real_executed": source["phl_real_executed"],
            "limitations": copy.deepcopy(source.get("limitations", [])),
            "issues": issues,
            "source_seal_adjudication": {
                "batch": batch_seal,
                "receipts": receipt_seals,
                "monitor": monitor_seal,
            },
            "projection_contract": {
                "mode": "MECHANICAL_FIELD_PROJECTION_NO_MANUAL_TRANSCRIPTION",
                "original_receipts_retained": True,
                "source_seals_reused_for_projection": False,
                "projection_has_independent_seal": True,
                "adverse_process_outcome_preserved": True,
                "authority_created": False,
            },
            "input_envelope_sha256": canonical_sha256(source),
            "input_envelope": source,
            "claim_ceiling": (
                "EVIDENCE_PRESERVING_LOCAL_TASK_CLOSURE_ONLY_NOT_GENERAL_"
                "EFFICACY_OR_PRODUCTION_AUTHORITY"
            ),
        }
        return _seal(payload)

    @staticmethod
    def verify(closure: dict[str, Any]) -> dict[str, Any]:
        candidate = copy.deepcopy(closure)
        closure_seal = _seal_match(candidate, "sha256")
        envelope = candidate.get("input_envelope")
        if not isinstance(envelope, dict):
            raise ValueError("closure.input_envelope must be an object")
        regenerated = EvidencePreservingClosure.materialize(envelope)
        regenerated_match = candidate == regenerated
        source_gate_pass = regenerated["gate"] == "PASS_BOUNDED"
        verified = closure_seal["match"] and regenerated_match and source_gate_pass
        payload = {
            "schema": "kch.evidence-preserving-task-closure-verification.v0.1.0",
            "gate": "PASS_VERIFIED" if verified else "FAIL_NOT_SOURCE_DERIVABLE",
            "closure_seal": closure_seal,
            "regenerated_match": regenerated_match,
            "source_gate": regenerated["gate"],
            "claims_allowed": verified,
            "authority_created": False,
        }
        return _seal(payload)
