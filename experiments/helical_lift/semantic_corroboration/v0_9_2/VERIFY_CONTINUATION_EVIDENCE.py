"""Independent hash, lineage and conservation checks for this continuation."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def identity(value, key, prefix):
    body = dict(value)
    declared = body.pop(key)
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    assert declared == prefix + ":" + hashlib.sha256(raw).hexdigest(), key


def main():
    work = Path(sys.argv[1])
    remote = work / "remote-run9/expanded"
    read = lambda path: json.loads(path.read_text())
    gate = read(remote / "receipts/GATE_EXECUTION_RECEIPT_V0_9.json")
    cleanup = read(remote / "receipts/RAW_SOURCE_CLEANUP_RECEIPT_V0_9_2.json")
    hold = read(remote / "eligibility/BLIND_INPUT_SEMANTIC_HOLD_V0_9_2.json")
    extract = read(remote / "blind/EXTRACTION_RECEIPT_V0_9.json")
    npz_check = read(remote / "blind/SAFE_NPZ_VERIFICATION_RECEIPT_V0_9.json")
    acquisition = read(remote / "receipts/ACQUISITION_RECEIPT_V0_9.json")
    for value, key, prefix in [(gate, "gate_receipt_id", "h9gate"), (cleanup, "receipt_id", "h9cleanup"),
                                (hold, "receipt_id", "h9semantichold"), (extract, "receipt_id", "h9extract"),
                                (npz_check, "receipt_id", "h9npz"), (acquisition, "receipt_id", "h9acq")]:
        identity(value, key, prefix)
    npz = remote / "blind/blind_columns.npz"
    assert digest(npz) == extract["output_sha256"] == npz_check["npz_sha256"] == hold["safe_npz_sha256"]
    field_checks = []
    with np.load(npz, allow_pickle=False) as data:
        assert set(data.files) == set(extract["field_receipts"])
        for field in data.files:
            a = data[field]
            assert a.ndim == 1 and not a.dtype.hasobject and len(a) == 1574113
            assert hashlib.sha256(a.tobytes()).hexdigest() == extract["field_receipts"][field]["data_sha256"]
            field_checks.append(field)
    assert acquisition["source_receipts"]["mechanism"]["sha256"] == extract["source_sha256"] == hold["source_sha256"]
    assert gate["outcome"] == hold["outcome"] == "BLOCKED_UNCERTIFIED_EVENT_TYPE_ENCODING"
    assert gate["semantic_hold_receipt_id"] == hold["receipt_id"]
    assert cleanup["status"] == "PASS" and cleanup["paths_remaining_after_cleanup"] == []
    assert cleanup["gate_receipt_id"] == gate["gate_receipt_id"]
    assert cleanup["execution_id"] == gate["execution_id"]
    previous = None
    for n, line in enumerate((remote / "receipts/STATE_TRANSITIONS_V0_9.jsonl").read_text().splitlines(), 1):
        event = json.loads(line)
        current = event.pop("event_hash")
        assert event["sequence"] == n and event["previous_hash"] == previous
        raw = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        assert current == hashlib.sha256(raw).hexdigest()
        previous = current
    assert previous == gate["final_transition_hash"]
    cor = work / "corroboration"
    contract = read(cor / "CONTRACT_FROZEN_BEFORE_JOIN.json")
    result = read(cor / "CORROBORATION_RESULT.json")
    identity(contract, "contract_id", "h9codecontract")
    identity(result, "receipt_id", "h9codecorroboration")
    assert result["contract_id"] == contract["contract_id"]
    assert result["contract_file_sha256"] == digest(cor / "CONTRACT_FROZEN_BEFORE_JOIN.json")
    assert result["source_npz_sha256"] == contract["source_npz_sha256"] == digest(npz)
    assert contract["script_sha256"] == digest(Path(__file__).with_name("CORROBORATE_EVENT_CODES_V0_9_2.py"))
    sources = read(cor / "SOURCE_DOWNLOAD_RECEIPTS.json")
    assert len(sources) == result["downloads_verified"] == 82
    for source in sources:
        path = work / "catalog-cache" / source["network"] / Path(source["path"]).name
        b = path.read_bytes()
        assert len(b) == source["bytes"] and digest(path) == source["sha256"]
        assert hashlib.sha1(f"blob {len(b)}\0".encode() + b).hexdigest() == source["git_blob_sha1"]
    for candidate in result["candidate_results"]:
        assert sum(candidate["counts"].values()) == result["rows"]
        assert candidate["consistent_rows"] + candidate["label_contradictions"] == candidate["matched_supported_rows"]
        assert candidate["matched_supported_rows"] + candidate["unmatched_or_ambiguous_rows"] == result["rows"]
        assert candidate["passed_all_frozen_checks"] is False
    assert result["unique_passing_bijection"] is None
    output = {"status": "PASS_VERIFICATION_ONLY", "scientific_status": "HOLD",
              "gate_receipt_id": gate["gate_receipt_id"], "corroboration_receipt_id": result["receipt_id"],
              "source_files_rehashed": len(sources), "source_bytes": result["download_bytes"],
              "safe_npz_sha256": digest(npz), "array_hashes_verified": sorted(field_checks),
              "event_count": result["rows"], "transition_chain_verified": True,
              "raw_source_cleanup_receipt_verified": True, "model_fitting_performed": False,
              "directional_fields_unsealed": False}
    (work / "INDEPENDENT_VERIFICATION.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
