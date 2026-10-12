from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common_v09 import content_id, git_blob_sha1, sha256_file, write_json_atomic  # noqa: E402
from kch_helical_dynamic_v08.eligibility import blind_eligibility, load_fault_index  # noqa: E402

ALLOWED = {
    "num", "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
}
REQUIRED = ALLOWED - {"num"}
SEALED = {
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
}
EXPECTED_FAULT_BLOB = "fb164770b529695544fa864abe2cc9dd8aa5793d"
EXPECTED_PROTOCOL_FILE_SHA256 = "9c988d22a0d0453e645677a8788bc4064b57991e1ec1a44001d5098d12388246"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def audit_protocol(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_PROTOCOL_FILE_SHA256:
        raise SystemExit("locked protocol physical SHA-256 mismatch")
    protocol = json.loads(raw.decode("utf-8"))
    stripped = dict(protocol)
    protocol_id = stripped.pop("protocol_id")
    declared_hash = stripped.pop("protocol_sha256")
    calculated = hashlib.sha256(canonical(stripped)).hexdigest()
    if protocol_id != f"h8p:{calculated}" or declared_hash != calculated:
        raise SystemExit("protocol content-address mismatch")
    if protocol.get("status") != "LOCKED_BEFORE_REAL_MECHANISM_ANGLE_ACCESS":
        raise SystemExit("protocol is not in the required locked state")
    return protocol, {
        "protocol_id": protocol_id,
        "protocol_content_sha256": calculated,
        "protocol_file_sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Blind v0.8 eligibility executed by the v0.9 exact-byte transport successor")
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--safe-npz", required=True, type=Path)
    parser.add_argument("--extraction-receipt", required=True, type=Path)
    parser.add_argument("--safe-npz-receipt", required=True, type=Path)
    parser.add_argument("--acquisition-receipt", required=True, type=Path)
    parser.add_argument("--fault-geojson", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    protocol, lock = audit_protocol(args.protocol)
    extraction = json.loads(args.extraction_receipt.read_text(encoding="utf-8"))
    npz_receipt = json.loads(args.safe_npz_receipt.read_text(encoding="utf-8"))
    acquisition = json.loads(args.acquisition_receipt.read_text(encoding="utf-8"))
    if acquisition.get("outcome") != "EXACT_BYTE_ACQUISITION_PASS" or acquisition.get("all_or_none_pass") is not True:
        raise SystemExit("acquisition receipt is not PASS")
    if acquisition.get("transaction_committed") is not True:
        raise SystemExit("acquisition transaction was not atomically committed")
    if extraction.get("angle_fields_accessed_for_selection") is not False or extraction.get("sealed_fields_emitted") != []:
        raise SystemExit("blind barrier violation in extraction receipt")
    if extraction.get("output_sha256") != sha256_file(args.safe_npz):
        raise SystemExit("NPZ hash mismatch")
    if npz_receipt.get("status") != "PASS" or npz_receipt.get("npz_sha256") != extraction.get("output_sha256"):
        raise SystemExit("safe-NPZ verification receipt mismatch")

    source_receipts = acquisition.get("source_receipts", {})
    mechanism_receipt = source_receipts.get("mechanism", {})
    fault_receipt = source_receipts.get("fault", {})
    fault_sha256 = sha256_file(args.fault_geojson)
    fault_blob = git_blob_sha1(args.fault_geojson)
    if mechanism_receipt.get("sha256") != extraction.get("source_sha256"):
        raise SystemExit("mechanism acquisition/extraction lineage mismatch")
    if fault_receipt.get("sha256") != fault_sha256:
        raise SystemExit("fault acquisition/runner lineage mismatch")
    if fault_blob != EXPECTED_FAULT_BLOB or fault_receipt.get("git_blob_sha1") != EXPECTED_FAULT_BLOB:
        raise SystemExit("fault Git-blob identity mismatch")

    with np.load(args.safe_npz, allow_pickle=False) as loaded:
        fields = set(loaded.files)
        if not REQUIRED.issubset(fields) or not fields.issubset(ALLOWED):
            raise SystemExit("safe NPZ fields violate blind allow-list")
        if fields & SEALED:
            raise SystemExit("sealed field present in blind NPZ")
        columns = {name: loaded[name].copy() for name in sorted(fields)}
        if any(value.dtype.kind == "O" or value.dtype.hasobject or value.ndim != 1 for value in columns.values()):
            raise SystemExit("unsafe array in safe NPZ")

    if columns["ev_bl"].dtype.kind in "iufb":
        hold = {
            "format": "KCH_HELICAL_EVENT_TYPE_ENCODING_HOLD_V0_9_1",
            "outcome": "BLOCKED_UNCERTIFIED_EVENT_TYPE_ENCODING",
            "reason": "The locked earthquake-not-blast filter must not treat unexplained numeric categories as earthquake labels.",
            "source_sha256": mechanism_receipt.get("sha256"),
            "ev_bl_dtype": columns["ev_bl"].dtype.str,
            "scientific_eligibility_executed": False,
            "directional_fields_unsealed": False,
            "model_fitting_performed": False,
            "authority_ceiling": "NONE",
        }
        hold["receipt_id"] = content_id("h9encodinghold", hold)
        write_json_atomic(args.output.parent / "EVENT_TYPE_ENCODING_HOLD_V0_9_1.json", hold)
        raise SystemExit("BLOCKED_UNCERTIFIED_EVENT_TYPE_ENCODING: provider codebook required")

    fault_index = load_fault_index(args.fault_geojson, expected_sha256=fault_sha256)
    result = blind_eligibility(columns, fault_index, protocol)
    if result.get("angle_fields_accessed") is not False:
        raise SystemExit("eligibility operator reported angle access")
    result["transport_successor"] = {
        "runtime_version": "0.9.0",
        **lock,
        "safe_npz_sha256": sha256_file(args.safe_npz),
        "extraction_receipt_id": extraction.get("receipt_id"),
        "safe_npz_verification_receipt_id": npz_receipt.get("receipt_id"),
        "acquisition_receipt_id": acquisition.get("receipt_id"),
        "mechanism_sha256": mechanism_receipt.get("sha256"),
        "fault_sha256": fault_sha256,
        "fault_git_blob_sha1": fault_blob,
        "direct_pickle_opened_outside_sandbox": False,
        "authority_ceiling": "NONE",
    }
    result["scientific_execution_authorized"] = bool(result.get("execution_authorized"))
    result["directional_unsealing_performed"] = False
    result["model_fitting_performed"] = False
    result["physical_helicity"] = "NOT_EVALUATED"
    result["promotion"] = "BLOCKED"
    result["canonicalization"] = "BLOCKED"
    result["transport_receipt_id"] = content_id("h9eligtransport", result)
    write_json_atomic(args.output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0 if result.get("execution_authorized") else 30


if __name__ == "__main__":
    raise SystemExit(main())
