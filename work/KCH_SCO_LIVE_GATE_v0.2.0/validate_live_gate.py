from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from kch_sco.ledger import SCOService
from transport_guard import TransportGuard


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sco-state", type=Path, required=True)
    parser.add_argument("--transport-state", type=Path, required=True)
    parser.add_argument("--decision-result", type=Path, required=True)
    parser.add_argument("--bootstrap", type=Path, required=True)
    parser.add_argument("--native-response", type=Path, required=True)
    parser.add_argument("--host-receipt", type=Path, required=True)
    parser.add_argument("--failed-empty-state", type=Path, required=True)
    parser.add_argument("--v01-state", type=Path, required=True)
    parser.add_argument("--v01-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite: {args.output}")
    unit = subprocess.run([sys.executable, "-m", "unittest", "-q", "test_transport_guard.py"], capture_output=True, text=True, check=False)
    guard = TransportGuard(args.transport_state)
    guard_integrity = guard.verify()
    guard_status = guard.status("SCO-LIVE-DISPATCH-20260809-01")
    retry = guard.prepare(load(Path("dispatch_envelope.json")))
    service = SCOService(args.sco_state)
    sco_integrity = service.verify()
    projection = service.projection("sco.kch-pre2g-continuation.20260809")
    decision = load(args.decision_result)
    bootstrap = load(args.bootstrap)
    response_text = args.native_response.read_text(encoding="utf-8").strip()
    response = json.loads(response_text)
    host = load(args.host_receipt)
    manifest = load(args.v01_manifest)
    runtime_entry = next(item for item in manifest["files"] if item["path"] == "runtime/KCH_PRE2G_SCO_v0.1.0.sqlite3")
    with sqlite3.connect(args.failed_empty_state) as connection:
        failed_empty_counts = {
            "events": connection.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "commands": connection.execute("SELECT COUNT(*) FROM commands").fetchone()[0],
        }
    checks = {
        "transport_guard_tests_5_of_5": unit.returncode == 0 and "Ran 5 tests" in unit.stderr,
        "transport_guard_integrity_pass": guard_integrity == {"gate": "PASS", "defects": [], "dispatches": 1, "received": 1},
        "receipt_bound_to_exact_native_response_hash": guard_status["response_sha256"] == hashlib.sha256(response_text.encode("utf-8")).hexdigest() == host["native_response_sha256"],
        "retry_suppressed_without_resend": retry["idempotent_replay"] is True and retry["should_send"] is False and retry["state"] == "RECEIVED",
        "native_identity_and_nonce_exact": response["dispatch_id"] == "SCO-LIVE-DISPATCH-20260809-01" and response["nonce"] == "SCO-LIVE-NONCE-20260809-01" and host["thread_id"] == "019fe6f6-076b-7803-b3c3-88c6f29329f0",
        "authority_exact_no_escalation": response["authority_exercised"] == ["RETURN_BOUNDED_TEXT_RECEIPT"],
        "all_forbidden_actions_attested": set(response["forbidden_actions_observed"]) == {"FILESYSTEM_MUTATION", "EXTERNAL_NETWORK", "OTHER_THREAD_CONTACT", "CONTEXT_OR_MEMORY_EXPORT"},
        "host_reports_no_tool_markers": host["bootstrap_latest_tool_marker"] is None and host["transport_latest_tool_marker"] is None,
        "bootstrap_exact": bootstrap["node_state"] == "READY_FOR_SCOPED_WORK_ORDER" and bootstrap["bootstrap_nonce"] == "SCO-DISPOSABLE-20260809-01",
        "sco_integrity_pass": sco_integrity["gate"] == "PASS" and not sco_integrity["defects"],
        "sco_successor_projection_exact": projection["nodes"] == 3 and projection["edges"] == 2 and projection["work_orders"] == 2 and projection["receipts"] == 2 and projection["order_states"] == {"COMPLETED": 2},
        "decision_adapter_pass": decision["gate"] == "PASS_BOUNDED" and decision["checks_passed"] == decision["checks_total"] == 8,
        "zero_user_feedback": decision["gate_state"]["feedback"] == 0,
        "personal_state_unchanged": decision["source_sha256_before"] == decision["source_sha256_after"] == "a81724487739c37825e251c0de68a9aaf2033e2e14418f9aac8215f6a976527d",
        "sealed_v01_state_unchanged": sha_file(args.v01_state) == runtime_entry["sha256"],
        "failed_empty_replica_preserved": failed_empty_counts == {"events": 0, "commands": 0},
    }
    gate = "PASS_BOUNDED" if all(checks.values()) else "FAIL"
    result = {
        "schema": "kch.sco.live-gate-result.v0.2.0",
        "gate": gate,
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "disposable_thread_id": host["thread_id"],
        "disposable_native_uri": host["native_uri"],
        "bootstrap_turn_id": host["bootstrap_turn_id"],
        "transport_turn_id": host["transport_turn_id"],
        "dispatch_id": response["dispatch_id"],
        "native_response_sha256": host["native_response_sha256"],
        "sco_projection": projection,
        "sco_integrity": sco_integrity,
        "transport_integrity": guard_integrity,
        "decision_adapter_result": decision,
        "failed_preparation_evidence": {"state": str(args.failed_empty_state.resolve()), "sha256": sha_file(args.failed_empty_state), **failed_empty_counts},
        "claim": "One bounded, idempotency-guarded Codex textual transport cycle and SCO-to-KCH decision adaptation are demonstrated on isolated successor states.",
        "limitations": [
            "One disposable local Codex task only; no second independent target and no other provider.",
            "No independent operating-system audit of the disposable task; no-tool evidence is host metadata plus the task receipt.",
            "Codex exposed one shared turn identifier for request and response.",
            "Decision adaptation covers work-order issuance and zero-conflict abstention only.",
            "Twelve earlier KCH emitter contracts remain unavailable; overall KCH integration remains bounded.",
            "No comparative semantic-quality campaign against Projects was run."
        ],
        "artifact_hashes": {
            "sco_successor_state": sha_file(args.sco_state),
            "transport_state": sha_file(args.transport_state),
            "decision_result": sha_file(args.decision_result),
            "bootstrap": sha_file(args.bootstrap),
            "native_response": sha_file(args.native_response),
            "host_receipt": sha_file(args.host_receipt),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gate": gate, "checks": f"{result['checks_passed']}/{result['checks_total']}", "thread_id": result["disposable_thread_id"]}))
    return 0 if gate == "PASS_BOUNDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
