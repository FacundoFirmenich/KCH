from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from common_v09 import canonical_json_bytes, content_id, sha256_file, utc_now, write_json_atomic

PARENT_BLOCK_ID = "kb:3973f266998127a801d098eb53fe69e0ad2284e1a760bb599114c00913468817"
PREDECESSOR_EVENT_HASH = "a77088958feb96d3d7e11b0845728c0b4239be7710362dc0194d9672fea7288b"
PROTOCOL_ID = "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
V08_ZIP_SHA256 = "9a21f12697669b9fe8b37cc587f9ea9bb700e9950117cc882387085a0d044042"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    live = json.loads((root / "receipts/local_exact_byte_attempt/GATE_EXECUTION_RECEIPT_V0_9.json").read_text())
    negative = json.loads((root / "receipts/negative_sandbox_test/NEGATIVE_TEST_ADJUDICATION.json").read_text())
    dry = json.loads((root / "receipts/dry_run_test/GATE_EXECUTION_RECEIPT_V0_9.json").read_text())

    runtime_hashes = {
        path.name: sha256_file(path)
        for path in sorted((root / "runtime").glob("*"))
        if path.is_file()
    }
    created = utc_now()
    payload = {
        "format": "KCH_HELICAL_V0_9_EXACT_BYTE_TO_BLIND_SUCCESSOR_PAYLOAD",
        "outcome": "REMOTE_EXECUTOR_READY_LOCAL_NETWORK_BLOCK_PRESERVED",
        "scientific_protocol_version": "0.8.0_UNCHANGED",
        "protocol_id": PROTOCOL_ID,
        "transactional_resumable_acquisition": True,
        "fault_git_blob_verification": True,
        "fault_expected_git_blob_sha1": "fb164770b529695544fa864abe2cc9dd8aa5793d",
        "fault_expected_bytes": 10622730,
        "pickle_whole_bytes_duplication_removed": True,
        "pickle_opcode_scan_streaming": True,
        "networkless_sandbox_negative_test": negative["status"],
        "dry_run_no_effect": dry["outcome"] == "DRY_RUN_NO_EFFECT",
        "local_exact_byte_attempt": live["outcome"],
        "local_exact_byte_attempt_receipt_id": live["gate_receipt_id"],
        "blind_eligibility_executed": False,
        "directional_fields_unsealed": False,
        "model_fit_executed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "remote_ephemeral_workflow_ready": True,
        "raw_sources_exported_by_workflow": False,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    lineage = {
        "parent_block_ids": [PARENT_BLOCK_ID],
        "predecessor_event_hash": PREDECESSOR_EVENT_HASH,
        "protocol_id": PROTOCOL_ID,
        "v0_8_release_zip_sha256": V08_ZIP_SHA256,
        "runtime_hashes": runtime_hashes,
    }
    body_without_id = {
        "schema_version": "0.9.successor.1",
        "block_type": "V9_EXACT_BYTE_TO_BLIND_EXECUTOR_SUCCESSOR_CANDIDATE",
        "created_at_utc": created,
        "maturity": "TRANSPORT_EXECUTOR_IMPLEMENTED_LOCAL_SECURITY_PASS_REMOTE_NETWORK_GATE_PENDING",
        "authority": {
            "ceiling": "NONE",
            "promoted": False,
            "canonicalized": False,
            "deployed": False,
            "publication_authority": False,
        },
        "lineage": lineage,
        "payload": payload,
    }
    block_id = content_id("kb", body_without_id)
    block = {"block_id": block_id, **body_without_id}
    graph = {
        "format": "KCH_HELICAL_V0_9_SUCCESSOR_GRAPH",
        "parent_block_ids": [PARENT_BLOCK_ID],
        "successor_block_id": block_id,
        "edge_type": "TRANSPORT_RUNTIME_SUCCESSOR_OF",
        "predecessor_mutated": False,
    }
    graph["graph_id"] = content_id("kbg", graph)
    write_json_atomic(root / "blocks/KWANBLOCK_V9_EXACT_BYTE_TO_BLIND_EXECUTOR.json", block)
    write_json_atomic(root / "blocks/KWANBLOCK_V9_SUCCESSOR_GRAPH.json", graph)

    event_without_hash = {
        "format": "KCH_HELICAL_V0_9_APPEND_ONLY_SUCCESSOR_EVENT",
        "sequence": 2,
        "created_at_utc": created,
        "event_type": "EXACT_BYTE_TO_BLIND_EXECUTOR_SUCCESSOR_CANDIDATE",
        "outcome": payload["outcome"],
        "block_id": block_id,
        "graph_id": graph["graph_id"],
        "protocol_id": PROTOCOL_ID,
        "prev_hash": PREDECESSOR_EVENT_HASH,
        "authority_ceiling": "NONE",
        "scientific_execution_performed": False,
    }
    event_hash = hashlib.sha256(canonical_json_bytes(event_without_hash)).hexdigest()
    event = {
        **event_without_hash,
        "event_hash": event_hash,
        "event_id": f"h9event:{event_hash}",
    }
    jsonl = root / "ledger/SUCCESSOR_EVENTS_V0_9.jsonl"
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    jsonl.write_text(json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    db = root / "ledger/SUCCESSOR_LEDGER_V0_9.sqlite3"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    try:
        con.execute("PRAGMA journal_mode=DELETE")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        con.execute("CREATE TABLE events(sequence INTEGER PRIMARY KEY, event_hash TEXT UNIQUE NOT NULL, prev_hash TEXT NOT NULL, event_type TEXT NOT NULL, block_id TEXT NOT NULL, payload_json TEXT NOT NULL)")
        con.executemany("INSERT INTO metadata(key,value) VALUES(?,?)", [
            ("format", "KCH_HELICAL_V0_9_SUCCESSOR_LEDGER"),
            ("predecessor_event_hash", PREDECESSOR_EVENT_HASH),
            ("authority_ceiling", "NONE"),
        ])
        con.execute(
            "INSERT INTO events(sequence,event_hash,prev_hash,event_type,block_id,payload_json) VALUES(?,?,?,?,?,?)",
            (2, event_hash, PREDECESSOR_EVENT_HASH, event["event_type"], block_id, json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        )
        con.commit()
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        db_event = json.loads(con.execute("SELECT payload_json FROM events WHERE sequence=2").fetchone()[0])
    finally:
        con.close()

    receipt = {
        "format": "KCH_HELICAL_V0_9_LEDGER_RECONCILIATION_RECEIPT",
        "status": "PASS" if integrity == "ok" and db_event == event else "FAIL",
        "predecessor_event_hash": PREDECESSOR_EVENT_HASH,
        "successor_event_hash": event_hash,
        "successor_event_id": event["event_id"],
        "block_id": block_id,
        "graph_id": graph["graph_id"],
        "sqlite_integrity_check": integrity,
        "sqlite_jsonl_semantic_identity": db_event == event,
        "append_only_predecessor_mutated": False,
        "jsonl_sha256": sha256_file(jsonl),
        "sqlite_sha256": sha256_file(db),
        "authority_ceiling": "NONE",
    }
    receipt["receipt_id"] = content_id("h9ledger", receipt)
    write_json_atomic(root / "receipts/LEDGER_RECONCILIATION_RECEIPT_V0_9.json", receipt)
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
