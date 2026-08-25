from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import logical_digest, sha256_file
from .contracts import ContractError, GateResult, OBSERVATION_SCHEMA, RECEIPT_SCHEMA, validate_snapshot, validate_state


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ContractError(f"{path.name} no es objeto JSON")
    return value


def verify_bundle(bundle: Path) -> dict[str, Any]:
    gates: list[GateResult] = []
    try:
        manifest = _load(bundle / "artifact_manifest.json")
        actual = []
        for row in manifest["files"]:
            path = bundle / row["path"]
            ok = path.is_file() and path.stat().st_size == row["bytes"] and sha256_file(path) == row["sha256"]
            gates.append(GateResult(f"artifact:{row['path']}", ok, "hash y tamano" if ok else "ausente o divergente"))
            if path.is_file():
                actual.append({"path": row["path"], "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        digest_ok = logical_digest(actual) == manifest["logical_digest"]
        gates.append(GateResult("manifest_logical_digest", digest_ok, "digest reproducido" if digest_ok else "digest divergente"))
        snapshot = _load(bundle / "source_snapshot.json")
        validate_snapshot(snapshot)
        gates.append(GateResult("all_sources_eof", True, f"{len(snapshot['sources'])} fuentes completas"))
        state = _load(bundle / "project_state.json")
        validate_state(state)
        gates.append(GateResult("state_contract", True, "ejes, procedencias y sondas presentes"))
        contract = _load(bundle / "continuity_contract.json")
        gates.append(GateResult("automatic_promotion_disabled", contract.get("automatic_promotion") is False, "promocion gobernada"))
        gates.append(GateResult("observed_trace_required", contract.get("destination_read_trace_required") is True, "no basta autodeclaracion"))
    except Exception as exc:
        gates.append(GateResult("contract_exception", False, f"{type(exc).__name__}: {exc}"))
    return {"schema": "kch.handoff-verification.v0.2.0", "passed": all(gate.passed for gate in gates), "gates": [gate.as_dict() for gate in gates]}


def _coverage_map(receipt: dict[str, Any], required: set[str]) -> bool:
    rows = receipt.get("understanding_map", [])
    if not isinstance(rows, list):
        return False
    observed = set()
    for row in rows:
        if not isinstance(row, dict):
            return False
        if len(str(row.get("explanation_es", "")).strip()) < 40:
            return False
        if not isinstance(row.get("provenance"), list) or not row["provenance"]:
            return False
        observed.add(str(row.get("id", "")))
    return observed == required


def _probe_coverage(receipt: dict[str, Any], required: set[str]) -> bool:
    rows = receipt.get("probe_answers", [])
    if not isinstance(rows, list):
        return False
    observed = set()
    for row in rows:
        if not isinstance(row, dict) or len(str(row.get("answer_es", "")).strip()) < 80:
            return False
        if not isinstance(row.get("provenance"), list) or not row["provenance"]:
            return False
        observed.add(str(row.get("probe_id", "")))
    return observed == required


def _observed_trace_ok(contract: dict[str, Any], observation: dict[str, Any]) -> bool:
    traces = observation.get("read_traces")
    if not isinstance(traces, list):
        return False
    expected_by_id = {source["source_id"]: source for source in contract["sources"]}
    observed_by_id = {trace.get("source_id"): trace for trace in traces if isinstance(trace, dict)}
    if set(observed_by_id) != set(expected_by_id):
        return False
    for source_id, expected in expected_by_id.items():
        observed = observed_by_id[source_id]
        if observed.get("source_uri") != expected["source_uri"] or observed.get("eof_observed") is not True:
            return False
        if expected["verification_mode"] in ("EXACT_PAGE_HASH", "DIALOGUE_EXACT_OUTPUTS_BOUNDED"):
            if observed.get("page_receipts") != expected["page_receipts"]:
                return False
        else:
            required = set(expected.get("required_item_ids", []))
            if not required <= set(observed.get("required_item_ids_observed", [])):
                return False
            if observed.get("native_calls_observed") is not True:
                return False
        if expected["verification_mode"].endswith("OUTPUTS_BOUNDED"):
            if observed.get("acknowledged_bounded_tool_outputs") != expected.get("truncation_signal_count"):
                return False
    return True


def gate_receipt(bundle: Path, receipt_path: Path, observation_path: Path) -> dict[str, Any]:
    contract = _load(bundle / "continuity_contract.json")
    receipt = _load(receipt_path)
    observation = _load(observation_path)
    required_understanding = set(contract["required_invariant_ids"] + contract["required_correction_ids"] + contract["required_binding_decision_ids"] + contract["required_evidence_boundary_ids"])
    source_thread_ids = {source["source_uri"].rsplit("/", 1)[-1] for source in contract["sources"]}
    destination_id = str(observation.get("destination_thread_id", ""))
    checks = [
        GateResult("receipt_schema", receipt.get("schema") == RECEIPT_SCHEMA, "schema exacto"),
        GateResult("observation_schema", observation.get("schema") == OBSERVATION_SCHEMA, "observacion de fuente"),
        GateResult("fresh_destination", bool(destination_id) and destination_id not in source_thread_ids, "thread distinto de todas las fuentes"),
        GateResult("handoff_identity", receipt.get("handoff_id") == contract["handoff_id"], "handoff exacto"),
        GateResult("bundle_binding", receipt.get("bundle_digest") == contract["bundle_digest"], "bundle exacto"),
        GateResult("mission_binding", receipt.get("mission_digest") == contract["mission_digest"], "mision exacta"),
        GateResult("receipt_byte_binding", observation.get("receipt_sha256") == sha256_file(receipt_path), "recibo observado coincide"),
        GateResult("receipt_observed_in_rollout", observation.get("receipt_exactly_observed") is True, "mismo JSON observado en el rollout nativo"),
        GateResult("native_read_trace", _observed_trace_ok(contract, observation), "todas las paginas observadas hasta EOF"),
        GateResult("no_pre_receipt_material_action", observation.get("pre_receipt_material_actions") == [], "abstencion observada"),
        GateResult("initial_abstention", receipt.get("action_taken") is False, "abstencion declarada"),
        GateResult("invariants", set(receipt.get("acknowledged_invariants", [])) == set(contract["required_invariant_ids"]), "cobertura exacta"),
        GateResult("corrections", set(receipt.get("acknowledged_corrections", [])) == set(contract["required_correction_ids"]), "cobertura exacta"),
        GateResult("binding_decisions", set(receipt.get("acknowledged_binding_decisions", [])) == set(contract["required_binding_decision_ids"]), "cobertura exacta"),
        GateResult("evidence_boundaries", set(receipt.get("acknowledged_evidence_boundaries", [])) == set(contract["required_evidence_boundary_ids"]), "cobertura exacta"),
        GateResult("understanding_map", _coverage_map(receipt, required_understanding), "explicacion y procedencia de cada item"),
        GateResult("distributed_probes", _probe_coverage(receipt, set(contract["required_assimilation_probe_ids"])), "sondas de toda la cronologia"),
        GateResult("next_action", receipt.get("next_action_id") in contract["allowed_next_action_ids"], "accion predeclarada"),
        GateResult("conflict_disclosure", isinstance(receipt.get("unresolved_conflicts"), list), "conflictos explicitos"),
        GateResult("substantive_understanding", len(str(receipt.get("concise_understanding_es", "")).strip()) >= 240, "comprension sustantiva"),
    ]
    passed = all(item.passed for item in checks)
    return {
        "schema": "kch.handoff-receipt-gate.v0.2.0", "passed": passed,
        "promotion": "ELIGIBLE_FOR_GOVERNED_PROMOTION" if passed else "REJECT_AND_REPAIR",
        "gates": [item.as_dict() for item in checks],
    }
