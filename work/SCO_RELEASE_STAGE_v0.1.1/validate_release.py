from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from kch_sco.csi import lower_superchat
from kch_sco.ledger import SCOService
from kch_sco.models import sha256_json


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--csi", type=Path, required=True)
    parser.add_argument("--envelopes", type=Path, required=True)
    parser.add_argument("--adapters", type=Path, required=True)
    parser.add_argument("--phl-gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite: {args.output}")

    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src"
    unit = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    unit_total = unit.stderr.count(" ... ok") + unit.stdout.count(" ... ok")
    service = SCOService(args.state)
    integrity = service.verify()
    projection = service.projection("sco.kch-pre2g-continuation.20260809")
    graph = service.graph_diagnostics("sco.kch-pre2g-continuation.20260809")
    bundle = load(args.bundle)
    csi = load(args.csi)
    envelopes = load(args.envelopes)
    adapters = load(args.adapters)
    phl = load(args.phl_gate)
    expected_uris = {
        "codex://threads/019fd938-8000-7121-9078-d196bdd15ae4",
        "codex://threads/019fe6b4-c2dd-7880-847e-d1fd16ea67a2",
    }
    providers = {item["provider"] for item in adapters["providers"]}
    csi_recomputed = lower_superchat(bundle)
    checks = {
        "unit_tests_21_of_21": unit.returncode == 0 and unit_total == 21,
        "ledger_integrity_pass": integrity["gate"] == "PASS" and not integrity["defects"],
        "real_superchat_exactly_one": projection["superchats"] == 1,
        "real_nodes_exactly_two": projection["nodes"] == 2,
        "real_edge_exactly_one": projection["edges"] == 1,
        "real_work_order_and_receipt_exact": projection["work_orders"] == 1 and projection["receipts"] == 1,
        "real_work_order_completed": projection["order_states"] == {"COMPLETED": 1},
        "exact_native_uris_preserved": {item["native_uri"] for item in bundle["nodes"]} == expected_uris,
        "native_content_absent": bundle["native_chat_content_included"] is False,
        "native_memory_absent": bundle["native_memory_included"] is False,
        "authority_not_created_in_bundle": bundle["authority_created"] is False,
        "sovereignty_policies_exact": all(item["context_policy"] == "SCOPED_DISCLOSURE_ONLY" and item["memory_policy"] == "NATIVE_MEMORY_PRESERVED" for item in bundle["nodes"]),
        "mandatory_transfer_prohibitions_present": all({"FULL_CONTEXT_MERGE", "NATIVE_MEMORY_COPY", "IMPLICIT_AUTHORITY_TRANSFER"}.issubset(edge["disclosure_contract"]["forbidden_transfers"]) for edge in bundle["edges"]),
        "graph_diagnostics_clean_for_first_dag": graph["active_nodes"] == 2 and graph["active_edges"] == 1 and graph["cycles"] == [],
        "pre_receipt_dispatch_envelope_was_blocked_honestly": len(envelopes) == 1 and envelopes[0]["automatic_dispatch_performed"] is False and envelopes[0]["dispatch_blocker"] == "HOST_BRIDGE_REQUIRED",
        "provider_reference_families_declared": providers == {"CODEX", "CHATGPT", "CLINE", "COWORK", "OPENCODE"},
        "unverified_bridges_remain_unavailable": all(item["standalone_dispatch"] == "UNAVAILABLE_NOT_TESTED" for item in adapters["providers"] if item["provider"] in {"CLINE", "COWORK", "OPENCODE"}),
        "csi_only_uses_existing_primitives": {item["kind"] for item in csi["raw_csi_program"]} == {"OPEN_SESSION", "SEAL_IDENTITAS", "ADD_DATUM", "MODE_ON"},
        "csi_preserves_sovereignty_and_authority": csi["authority_created"] is False and csi["native_contexts_merged"] is False and csi["native_memories_replaced"] is False and csi["execution_authorized"] is False,
        "csi_reproducible_from_bundle": csi_recomputed == csi,
        "phl_predecessor_gate_is_bounded_pass": phl["gate"] == "PASS_BOUNDED" and phl["checks_passed"] == phl["checks_total"] == 16,
        "phl_source_state_was_preserved": phl["source_hashes_before"] == phl["source_hashes_after"],
        "bundle_hash_valid": bundle["bundle_sha256"] == sha256_json({key: value for key, value in bundle.items() if key != "bundle_sha256"}),
    }
    gate = "PASS_BOUNDED" if all(checks.values()) else "FAIL"
    result = {
        "schema": "kch.sco.validation-result.v0.1.0",
        "gate": gate,
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "unit_test_count": unit_total,
        "unit_test_returncode": unit.returncode,
        "integrity": integrity,
        "projection": projection,
        "graph": graph,
        "bundle_sha256": bundle["bundle_sha256"],
        "csi_program_sha256": csi["raw_csi_program_sha256"],
        "state_sha256": sha256_file(args.state),
        "claim": "A functional local sovereign-chat orchestration plane and a real two-Codex-task graph are demonstrated; live cross-provider dispatch and comparative outcome superiority are not demonstrated.",
        "limitations": [
            "Codex references were host-observed, but standalone automatic dispatch remains blocked.",
            "Cline, Cowork and OpenCode support is limited to validated native-reference contracts and dispatch envelopes.",
            "No native chat content or memory was ingested; semantic work quality cannot be compared in this gate.",
            "No distributed consensus, crash recovery campaign or multi-host transport gate was run.",
            "SCO is an integration candidate for KCH, not yet a globally admitted KCH release.",
        ],
        "artifact_hashes": {
            "portable_bundle": sha256_file(args.bundle),
            "csi_lowering": sha256_file(args.csi),
            "pre_receipt_envelopes": sha256_file(args.envelopes),
            "provider_matrix": sha256_file(args.adapters),
            "phl_gate_result": sha256_file(args.phl_gate),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gate": gate, "checks": f"{result['checks_passed']}/{result['checks_total']}", "unit_tests": unit_total, "output": str(args.output)}, ensure_ascii=False))
    return 0 if gate == "PASS_BOUNDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
