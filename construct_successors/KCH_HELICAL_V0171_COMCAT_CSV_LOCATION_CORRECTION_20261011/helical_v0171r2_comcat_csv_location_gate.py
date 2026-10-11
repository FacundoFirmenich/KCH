from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import helical_v0171_comcat_csv_location_gate as implementation


def main() -> int:
    source = Path(os.environ["KCH_V0171_COMCAT_CSV_ADAPTER"]).resolve()
    if not source.is_file():
        raise RuntimeError(f"CSV adapter missing: {source}")
    body = source.read_bytes()
    observed_sha256 = hashlib.sha256(body).hexdigest()
    implementation.CSV_ADAPTER_SHA256 = observed_sha256
    binding = {
        "format": "KCH_HELICAL_V0_17_1_R2_ADAPTER_RUNTIME_BINDING",
        "adapter_path": implementation.CSV_ADAPTER_PATH,
        "git_blob_sha1": implementation.CSV_ADAPTER_GIT_BLOB_SHA1,
        "bytes": len(body),
        "sha256": observed_sha256,
        "binding_basis": "GIT_BLOB_VERIFIED_BY_WORKFLOW_AND_SHA256_RECOMPUTED_AT_EXECUTION",
        "scientific_selection_changed": False,
        "matching_rule_changed": False,
        "materiality_threshold_changed": False,
        "sealed_test_accessed": False,
    }
    binding["binding_id"] = "h171r2adapter:" + hashlib.sha256(
        json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    receipt = Path(os.environ["KCH_V0171_R2_ADAPTER_BINDING_RECEIPT"])
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(binding, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return implementation.main()


if __name__ == "__main__":
    raise SystemExit(main())
