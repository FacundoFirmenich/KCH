"""Execute the unchanged v1.5 development gate with auditable operational bounds."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")

def main():
    out = Path(os.environ["OUT"])
    safe = out / "safe"
    safe.mkdir(parents=True, exist_ok=True)
    result_path = safe / "TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_5.json"
    receipt_path = safe / "CONTINUITY_EXECUTION_RECEIPT.json"
    if result_path.exists() or receipt_path.exists() or (out / "raw").exists():
        raise RuntimeError("refusing stale output: use a fresh OUT directory")
    manifest = json.loads((HERE / "FROZEN_INPUTS.json").read_text())
    checks = [{"path": p, "expected_sha256": h, "actual_sha256": digest(ROOT / p)}
              for p, h in manifest["sha256"].items()]
    receipt = {
        "format": "KCH_INTEGRAL_CONTINUITY_EXECUTION_V1",
        "frozen_parent": manifest["parent_commit"],
        "execution_commit": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "input_checks": checks,
        "inputs_match": all(c["actual_sha256"] == c["expected_sha256"] for c in checks),
        "socket_default_timeout_seconds": 90,
        "scientific_runtime_modified": False,
        "interpretation": "CONDITIONAL_TRANSITION_COMPARISON_WITH_ENDPOINT_ACTIVITY_NOT_EX_ANTE_FORECAST",
        "independent_units": "THREE_DEVELOPMENT_HARPS_NOT_192_INDEPENDENT_COMPONENT_TRANSITIONS",
        "authority_ceiling": "NONE",
        "scientific_confirmation": False,
        "status": "PREFLIGHT",
    }
    write(receipt_path, receipt)
    if not receipt["inputs_match"]:
        receipt["status"] = "FROZEN_INPUT_MISMATCH"
        write(receipt_path, receipt)
        return 90
    socket.setdefaulttimeout(90)
    rc = 99
    try:
        runpy.run_path(str(ROOT / ".github/helical_v15/temporal_lift_development.py"), run_name="__main__")
        rc = 0
    except SystemExit as exc:
        rc = int(exc.code or 0)
    except Exception as exc:
        receipt["exception"] = {"type": type(exc).__name__, "message": str(exc)}
        traceback.print_exc()
    finally:
        shutil.rmtree(out / "raw", ignore_errors=True)
        receipt["raw_directory_absent"] = not (out / "raw").exists()
    receipt["runtime_exit_code"] = rc
    receipt["status"] = "RUNTIME_FAILURE"
    if result_path.exists():
        report = json.loads(result_path.read_text())
        body = dict(report)
        claimed = body.pop("receipt_id")
        actual = "h15lift:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        identities = [
            {"harp": s["harp"], "requested": s["requested_time_tai"],
             "actual_harp": s["record"]["HARPNUM"], "actual_time": s["record"]["T_REC"],
             "match": s["harp"] == s["record"]["HARPNUM"] and s["requested_time_tai"] == s["record"]["T_REC"]}
            for t in report["trajectories"] for s in t["snapshots"]
        ]
        receipt.update({"result_sha256": digest(result_path), "result_receipt_id": claimed,
                        "result_content_hash_valid": claimed == actual, "snapshot_identity_checks": identities,
                        "outcome": report["outcome"], "complete_snapshot_count": len(identities)})
        consistent = (claimed == actual and all(x["match"] for x in identities)
                      and report["scientific_confirmation"] is False
                      and report["authority_ceiling"] == "NONE"
                      and report["fresh_2026_holdout_accessed"] is False
                      and report["flare_outcomes_accessed"] is False
                      and report["protocol_sha256"] == manifest["sha256"][manifest["protocol_path"]])
        if not consistent:
            rc, receipt["status"] = 90, "RECEIPT_OR_IDENTITY_MISMATCH"
        elif rc == 31 and report["outcome"] == "INSUFFICIENT_TEMPORAL_SUPPORT":
            receipt["status"] = "VALID_RECEIPT_INSUFFICIENT_SUPPORT_NOT_SCIENTIFIC_NULL"
        elif rc == 0 and len(identities) == 15 and report["outcome"] != "INSUFFICIENT_TEMPORAL_SUPPORT":
            receipt["status"] = "VALID_DEVELOPMENT_RESULT_NO_CONFIRMATION"
        else:
            rc, receipt["status"] = 90, "EXIT_RESULT_CONTRADICTION"
    elif rc in (0, 31):
        rc, receipt["status"] = 90, "MISSING_RESULT_RECEIPT"
    receipt["wrapper_exit_code"] = rc
    write(receipt_path, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return rc

if __name__ == "__main__":
    sys.exit(main())
