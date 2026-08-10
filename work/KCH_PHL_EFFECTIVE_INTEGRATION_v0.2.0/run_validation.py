from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from kch_phl_integration.service import ConflictError, EffectiveIntegrationService


CLIENT_CODEX = {"client_id": "codex", "client_instance_id": "gate-v0.2.0-codex"}
CLIENT_CLINE = {"client_id": "cline", "client_instance_id": "gate-v0.2.0-cline"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def optional_hash(path: Path) -> str:
    return sha256_file(path) if path.is_file() else "ABSENT"


def decision(decision_id: str, component_id: str, decision_type: str) -> dict[str, Any]:
    return {
        "schema": "kch.reviewable-decision.v0.2.0",
        "decision_id": decision_id,
        "emitted_at": "2026-08-09T00:00:00+00:00",
        "component_id": component_id,
        "decision_type": decision_type,
        "initiator": "KCH_PHL_EFFECTIVE_INTEGRATION_GATE_v0.2.0",
        "trigger": "INSTRUMENTED_GATE_PROBE_NOT_USER_DECISION",
        "objective_contract_sha256": "UNAVAILABLE",
        "purpose_id": "GATE_PHL_EFFECTIVE_KCH_INTEGRATION_v0.2.0",
        "jurisdiction": "isolated replica; contract and concurrency validation only",
        "input_provenance_ids": ["KCH_SUPER_MCP_FEDERATED_REGISTRY_v0.4.0"],
        "source_event_ids": [],
        "evidence_ids": ["GATE_PHL_EFFECTIVE_KCH_INTEGRATION_v0.2.0"],
        "active_rule_ids": ["NO_USER_FEEDBACK", "NO_POLICY_ACTIVATION", "NO_SOURCE_STATE_MUTATION"],
        "summary": "Exercise a strict decision envelope on the isolated gate replica.",
        "rationale": "The gate needs an observable emitter-to-ledger path; this probe is explicitly not a substantive KCH decision.",
        "alternatives_considered": ["UNAVAILABLE"],
        "confidence_representation": {
            "kind": "DETERMINISTIC_GATE_ASSERTION",
            "value": "NOT_A_PROBABILITY",
            "meaning": "Pass/fail pertains only to the instrumented route.",
        },
        "risk_class": "ISOLATED_REPLICA_ONLY",
        "authority_granted": ["WRITE_GATE_REPLICA"],
        "authority_exercised": ["WRITE_GATE_REPLICA"],
        "claim_ceiling": "INSTRUMENTED_INTEGRATION_PATH_ONLY",
        "consequence": "Adds one clearly marked probe record to the disposable/preserved replica.",
        "reversibility": "Delete the replica; the source state remains byte-identical.",
        "stop_condition_ids": ["SOURCE_HASH_CHANGED", "USER_FEEDBACK_PRESENT", "INTEGRITY_FAILURE"],
        "source_uri": f"gate://phl-effective-integration/{decision_id}",
    }


def mutate(service, method, request_id, *args, client=CLIENT_CODEX, **kwargs):
    return method(*args, client=client, request_id=request_id, expected_head_hash=service.head(), **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-state", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--replica", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for destination in (args.replica, args.output):
        if destination.exists():
            raise SystemExit(f"refusing to overwrite: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)

    source_sidecars = [Path(str(args.source_state) + suffix) for suffix in ("-wal", "-shm")]
    source_before = {"main": sha256_file(args.source_state), "wal": optional_hash(source_sidecars[0])}

    source = sqlite3.connect(f"file:{args.source_state}?mode=ro", uri=True)
    replica = sqlite3.connect(args.replica)
    source.backup(replica)
    replica.close()
    source.close()

    service = EffectiveIntegrationService(args.replica)
    initial = service.projection()
    initial_integrity = service.verify()
    checks: dict[str, bool] = {
        "source_initial_has_seven_decisions": initial["decisions"] == 7,
        "source_initial_has_zero_feedback": initial["feedback"] == 0,
        "source_initial_integrity_pass": initial_integrity["gate"] == "PASS",
    }

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    for index, record in enumerate(catalog):
        mutate(service, service.register_mutability, f"catalog-{index:02d}", record)
    for index, record in enumerate(inventory):
        mutate(service, service.register_emitter, f"emitter-{index:02d}", record)
    checks["mutability_catalog_exact"] = service.projection()["mutability_methods"] == len(catalog)
    checks["admitted_registry_inventory_exact"] = service.projection()["emitters"] == 16 == len(inventory)

    shared_head = service.head()
    first_record = decision("gate-kch-rgg-001", "kch.rgg", "RGG_PROFILE_SELECTION_PROBE")
    first = service.register_decision(first_record, client=CLIENT_CODEX, request_id="decision-rgg", expected_head_hash=shared_head)
    replay = service.register_decision(first_record, client=CLIENT_CODEX, request_id="decision-rgg", expected_head_hash=shared_head)
    checks["request_idempotency"] = replay["idempotent_replay"] and first["resulting_head_hash"] == replay["resulting_head_hash"]

    stale_rejected = False
    second_record = decision("gate-kch-kwanprompts-001", "kch.kwanprompts", "MESSAGE_CAPTURE_PROBE")
    try:
        service.register_decision(second_record, client=CLIENT_CLINE, request_id="decision-kp-stale", expected_head_hash=shared_head)
    except ConflictError:
        stale_rejected = True
    checks["multi_client_stale_write_rejected"] = stale_rejected
    mutate(service, service.register_decision, "decision-kp-fresh", second_record, client=CLIENT_CLINE)

    session = mutate(service, service.start_phl, "phl-start", trigger="GATE_EXCLUSIVE_LOCK_PROBE")["result"]["session_id"]
    mutation_counter: list[str] = []
    blocked = mutate(
        service,
        service.dispatch,
        "dispatch-mutating",
        "Super-MCP",
        "open_session",
        {"probe": True},
        lambda: mutation_counter.append("executed"),
    )
    read_counter: list[str] = []
    allowed = mutate(
        service,
        service.dispatch,
        "dispatch-read",
        "RGG",
        "resolve_profile",
        {"probe": True},
        lambda: read_counter.append("executed") or {"fixture": "READ_ONLY_ROUTE_ONLY"},
    )
    checks["phl_blocks_mutating_route_before_executor"] = not blocked["result"]["allowed"] and mutation_counter == []
    checks["phl_preserves_read_only_route"] = allowed["result"]["allowed"] and read_counter == ["executed"]
    mutate(service, service.close_phl, "phl-close", session)
    checks["phl_lock_closed_cleanly"] = service.projection()["active_phl_session_id"] is None

    final_integrity = service.verify()
    final_gate = service.gate_state(expected_admitted_rows=16)
    final_projection = service.projection()
    checks["final_integrity_pass"] = final_integrity["gate"] == "PASS"
    checks["zero_user_feedback_after_gate"] = final_projection["feedback"] == 0
    checks["bounded_gate_due_unavailable_contracts"] = final_gate["state"] == "PASS_EFFECTIVE_KCH_PHL_INTEGRATION_BOUNDED"
    checks["peer_divergence_detectable"] = service.compare_peer_head("0" * 64)["state"] == "DIVERGENT_LEDGER_COPY_DETECTED"

    checkpoint = sqlite3.connect(args.replica)
    checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    checkpoint.close()
    source_after = {"main": sha256_file(args.source_state), "wal": optional_hash(source_sidecars[0])}
    checks["source_state_byte_identical"] = source_before == source_after
    checks["all_expected_checks_present"] = len(checks) == 15

    gate = "PASS_BOUNDED" if all(checks.values()) else "FAIL"
    result = {
        "schema": "kch.phl-effective-integration-gate-result.v0.2.0",
        "gate": gate,
        "claim": "Effective transactional path demonstrated on an isolated replica; global emitter coverage is not demonstrated.",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "initial_projection": initial,
        "final_projection": final_projection,
        "integrity": final_integrity,
        "integration_gate_state": final_gate,
        "catalog_records": len(catalog),
        "inventory_records": len(inventory),
        "unavailable_contracts": final_projection["emitter_states"].get("UNAVAILABLE_CONTRACT", 0),
        "source_state": str(args.source_state.resolve()),
        "source_hashes_before": source_before,
        "source_hashes_after": source_after,
        "replica": str(args.replica.resolve()),
        "replica_sha256": sha256_file(args.replica),
        "limitations": [
            "No user PHL feedback was collected.",
            "No training packet or policy activation was performed.",
            "Twelve admitted registry rows still lack an inspected v0.2 decision-emitter contract.",
            "Two decision records are explicitly marked instrumentation probes, not substantive KCH decisions.",
            "Validation is local and replica-bounded; cross-process and distributed deployment remain outside this gate.",
        ],
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gate": gate, "checks": f"{result['checks_passed']}/{result['checks_total']}", "result": str(args.output), "replica_sha256": result["replica_sha256"]}, ensure_ascii=False))
    return 0 if gate == "PASS_BOUNDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
