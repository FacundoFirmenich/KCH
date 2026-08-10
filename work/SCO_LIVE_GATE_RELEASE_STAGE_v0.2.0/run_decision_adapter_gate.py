from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kch_phl_integration.contracts import sha256_json, validate_reviewable_decision
from kch_phl_integration.service import EffectiveIntegrationService


CLIENT = {"client_id": "sco-decision-adapter", "client_instance_id": "live-gate-v0.2.0"}


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(service, method, request_id, *args, **kwargs):
    return method(*args, client=CLIENT, request_id=request_id, expected_head_hash=service.head(), **kwargs)


def event_for(connection: sqlite3.Connection, event_type: str, key: str, value: str) -> sqlite3.Row:
    connection.row_factory = sqlite3.Row
    for row in connection.execute("SELECT * FROM events WHERE event_type=? ORDER BY sequence", (event_type,)):
        if json.loads(row["payload_json"]).get(key) == value:
            return row
    raise RuntimeError(f"event not found: {event_type} {key}={value}")


def work_order_decision(sco_state: Path) -> dict[str, Any]:
    with sqlite3.connect(sco_state) as connection:
        connection.row_factory = sqlite3.Row
        order_row = connection.execute("SELECT * FROM work_orders WHERE order_id='wo.sco-live-transport-01'").fetchone()
        node_row = connection.execute("SELECT * FROM nodes WHERE node_id='sco-disposable-live-probe-01'").fetchone()
        event = event_for(connection, "WORK_ORDER_ISSUED", "order_id", "wo.sco-live-transport-01")
    order = json.loads(order_row["record_json"])
    node = json.loads(node_row["record_json"])
    return {
        "schema": "kch.reviewable-decision.v0.2.0",
        "decision_id": "sco-decision:wo.sco-live-transport-01:issued",
        "emitted_at": event["occurred_at"],
        "component_id": "kch.sco",
        "decision_type": "SCO_WORK_ORDER_ISSUANCE",
        "initiator": event["actor"],
        "trigger": "USER_AUTHORIZED_DISPOSABLE_TASK_LIVE_GATE",
        "objective_contract_sha256": sha256_json(order),
        "purpose_id": "GATE_SCO_CODEX_LIVE_TRANSPORT_AND_KCH_DECISION_ADAPTER_v0.2.0",
        "jurisdiction": "One disposable Codex task and one bounded textual receipt.",
        "input_provenance_ids": [node["native_uri"], "SCO-LIVE-DISPATCH-20260809-01"],
        "source_event_ids": [event["event_id"]],
        "evidence_ids": ["sha256:36628d888851a6b429fcfa0eca1cccb4fa553bfb36167e1aca9afdf54773e6a8"],
        "active_rule_ids": ["SCOPED_DISCLOSURE_ONLY", "NATIVE_MEMORY_PRESERVED", "NO_IMPLICIT_AUTHORITY_TRANSFER"],
        "summary": "Issue one bounded textual-receipt work order to the explicitly authorized disposable Codex node.",
        "rationale": "The user authorized creation of a disposable target; the canonical lineage task remained read-only and the target received no native history or memory.",
        "alternatives_considered": ["DO_NOT_DISPATCH", "MUTATE_CANONICAL_LINEAGE_TASK_PROHIBITED"],
        "confidence_representation": {"kind": "DETERMINISTIC_LEDGER_AND_HOST_RECEIPT", "value": "OBSERVED", "meaning": "Identity and transport fields are exact; no semantic-quality inference."},
        "risk_class": "BOUNDED_DISPOSABLE_TEXT_TRANSPORT",
        "authority_granted": order["authority_granted"],
        "authority_exercised": order["authority_granted"],
        "claim_ceiling": order["claim_ceiling"],
        "consequence": "The target may return one exact textual receipt and perform no other action.",
        "reversibility": "The disposable task can be archived; immutable evidence remains preserved.",
        "stop_condition_ids": ["TARGET_IDENTITY_MISMATCH", "AUTHORITY_ESCALATION", "NONCE_MISMATCH", "CONTEXT_OR_MEMORY_EXPORT"],
        "source_uri": f"sco://sco.kch-pre2g-continuation.20260809/events/{event['event_id']}",
    }


def conflict_abstention_decision(sco_state: Path) -> dict[str, Any]:
    with sqlite3.connect(sco_state) as connection:
        conflict_count = connection.execute("SELECT COUNT(*) FROM conflicts WHERE sco_id='sco.kch-pre2g-continuation.20260809'").fetchone()[0]
        head = connection.execute("SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()[0]
    if conflict_count != 0:
        raise RuntimeError("conflict adjudication abstention is invalid when conflicts exist")
    projection = {"sco_id": "sco.kch-pre2g-continuation.20260809", "conflict_count": conflict_count, "head_hash": head}
    return {
        "schema": "kch.reviewable-decision.v0.2.0",
        "decision_id": "sco-decision:conflict-adjudication:abstain:no-conflict",
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "component_id": "kch.sco",
        "decision_type": "SCO_CONFLICT_ADJUDICATION_ABSTENTION",
        "initiator": "sco-decision-adapter",
        "trigger": "NO_CONFLICT_RECORD_PRESENT",
        "objective_contract_sha256": sha256_json(projection),
        "purpose_id": "GATE_SCO_CODEX_LIVE_TRANSPORT_AND_KCH_DECISION_ADAPTER_v0.2.0",
        "jurisdiction": "Current SCO ledger head only; zero persisted conflicts.",
        "input_provenance_ids": [f"sco-ledger-head:{head}"],
        "source_event_ids": [],
        "evidence_ids": ["sco-conflict-count:0"],
        "active_rule_ids": ["NO_ADJUDICATION_WITHOUT_CONFLICT", "PRESERVE_DIVERGENCE_IF_PRESENT"],
        "summary": "Abstain from conflict adjudication because the SCO ledger contains no conflict record.",
        "rationale": "Creating an adjudication outcome without competing receipts would invent a controversy and authority exercise.",
        "alternatives_considered": ["INVENT_CONFLICT_PROHIBITED"],
        "confidence_representation": {"kind": "DETERMINISTIC_LEDGER_QUERY", "value": "ZERO_CONFLICT_ROWS", "meaning": "Applies only to the exact ledger head."},
        "risk_class": "NO_ACTION_ABSTENTION",
        "authority_granted": [],
        "authority_exercised": [],
        "claim_ceiling": "NO_CONFLICT_PRESENT_AT_EXACT_LEDGER_HEAD",
        "consequence": "No adjudication event and no authority exercise are created.",
        "reversibility": "Not applicable; abstention changes no SCO state.",
        "stop_condition_ids": ["ANY_CONFLICT_RECORD_PRESENT"],
        "source_uri": f"sco://sco.kch-pre2g-continuation.20260809/head/{head}",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sco-state", type=Path, required=True)
    parser.add_argument("--personal-source", type=Path, required=True)
    parser.add_argument("--phl-replica", type=Path, required=True)
    parser.add_argument("--base-catalog", type=Path, required=True)
    parser.add_argument("--base-inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decisions-output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.phl_replica, args.output, args.decisions_output):
        if path.exists():
            raise SystemExit(f"refusing to overwrite: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    source_before = sha_file(args.personal_source)
    source = sqlite3.connect(f"file:{args.personal_source}?mode=ro", uri=True)
    replica = sqlite3.connect(args.phl_replica)
    source.backup(replica)
    replica.close()
    source.close()
    service = EffectiveIntegrationService(args.phl_replica)

    catalog = json.loads(args.base_catalog.read_text(encoding="utf-8"))
    sco_catalog = [
        {"service_id": "SCO", "method": "projection", "classification": "READ_ONLY", "evidence_ref": "kch_sco.ledger.SCOService.projection"},
        {"service_id": "SCO", "method": "graph_diagnostics", "classification": "READ_ONLY", "evidence_ref": "kch_sco.ledger.SCOService.graph_diagnostics"},
        {"service_id": "SCO", "method": "dispatch_envelopes", "classification": "READ_ONLY", "evidence_ref": "kch_sco.ledger.SCOService.dispatch_envelopes"},
        {"service_id": "SCO", "method": "add_node", "classification": "MUTATING", "evidence_ref": "kch_sco.ledger.SCOService.add_node"},
        {"service_id": "SCO", "method": "issue_work_order", "classification": "MUTATING", "evidence_ref": "kch_sco.ledger.SCOService.issue_work_order"},
        {"service_id": "SCO", "method": "ingest_receipt", "classification": "MUTATING", "evidence_ref": "kch_sco.ledger.SCOService.ingest_receipt"},
        {"service_id": "SCO", "method": "declare_conflict", "classification": "MUTATING", "evidence_ref": "kch_sco.ledger.SCOService.declare_conflict"},
        {"service_id": "SCO", "method": "retire_node", "classification": "MUTATING", "evidence_ref": "kch_sco.ledger.SCOService.retire_node"},
    ]
    for index, record in enumerate(catalog + sco_catalog):
        write(service, service.register_mutability, f"catalog-{index:02d}", record)
    inventory = json.loads(args.base_inventory.read_text(encoding="utf-8"))
    inventory.append({"component_id": "kch.sco", "registry_name": "KCH SuperChats Orchestrators (SCO)", "inventory_state": "DECISION_EMITTER", "evidence_ref": "GATE_SCO_CODEX_LIVE_TRANSPORT_AND_KCH_DECISION_ADAPTER_v0.2.0"})
    for index, record in enumerate(inventory):
        write(service, service.register_emitter, f"emitter-{index:02d}", record)
    decisions = [work_order_decision(args.sco_state), conflict_abstention_decision(args.sco_state)]
    validations = [validate_reviewable_decision(item) for item in decisions]
    for index, record in enumerate(decisions):
        write(service, service.register_decision, f"sco-decision-{index}", record)
    integrity = service.verify()
    gate_state = service.gate_state(expected_admitted_rows=17)
    projection = service.projection()
    source_after = sha_file(args.personal_source)
    checks = {
        "two_decisions_conformant": len(validations) == 2 and all(item["contract_state"] == "CONFORMANT" for item in validations),
        "sco_registered_as_decision_emitter": projection["emitter_states"].get("DECISION_EMITTER") == 3,
        "registry_v05_admitted_inventory_complete": projection["emitters"] == 17,
        "sco_mutability_methods_registered": projection["mutability_methods"] == len(catalog) + len(sco_catalog) == 25,
        "phl_replica_integrity_pass": integrity["gate"] == "PASS",
        "bounded_gate_preserved": gate_state["state"] == "PASS_EFFECTIVE_KCH_PHL_INTEGRATION_BOUNDED",
        "zero_feedback": projection["feedback"] == 0,
        "personal_source_unchanged": source_before == source_after,
    }
    args.decisions_output.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {
        "schema": "kch.sco.decision-adapter-gate-result.v0.2.0",
        "gate": "PASS_BOUNDED" if all(checks.values()) else "FAIL",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "decision_ids": [item["decision_id"] for item in decisions],
        "decision_hashes": [item["record_sha256"] for item in validations],
        "integrity": integrity,
        "gate_state": gate_state,
        "source_sha256_before": source_before,
        "source_sha256_after": source_after,
        "limitations": [
            "SCO decision adaptation is demonstrated only for work-order issuance and zero-conflict abstention.",
            "Twelve earlier KCH registry rows still have UNAVAILABLE_CONTRACT.",
            "The PHL state is an isolated replica; no personal policy activation or feedback occurred."
        ]
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gate": result["gate"], "checks": f"{result['checks_passed']}/{result['checks_total']}", "decisions": result["decision_ids"]}))
    return 0 if result["gate"] == "PASS_BOUNDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
