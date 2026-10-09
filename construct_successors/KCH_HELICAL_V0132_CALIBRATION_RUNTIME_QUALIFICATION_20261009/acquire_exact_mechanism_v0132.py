from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import helical_public_acquisition as public
import helical_remote_gate as gate


def canonical_id(prefix: str, body: dict[str, Any]) -> str:
    material = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(material).hexdigest()}"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    snapshot, metadata_receipt, synthetic_snapshot = public.public_request_json(gate.SNAPSHOT_URL, args.timeout)
    output = args.output_dir / gate.MECHANISM_BASENAME
    download_receipt = public.public_stream_download(
        public.EXPECTED_DOWNLOAD_URL,
        output,
        args.timeout,
        expected_bytes=public.EXPECTED_BYTES,
    )
    observed_sha = download_receipt["sha256"]
    observed_bytes = int(download_receipt["bytes"])
    if observed_sha != public.EXPECTED_SHA256 or observed_bytes != public.EXPECTED_BYTES:
        raise RuntimeError("exact source identity drift after acquisition")

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_13_2_EXACT_SOURCE_ACQUISITION_RECEIPT",
        "adapter": "MENDELEY_PUBLIC_API_EXACT_IDENTITY",
        "dataset_id": gate.DATASET_ID,
        "dataset_version": gate.DATASET_VERSION,
        "doi": gate.DOI,
        "required_file": gate.MECHANISM_BASENAME,
        "file_id": public.EXPECTED_FILE_ID,
        "content_id": public.EXPECTED_CONTENT_ID,
        "source_bytes": observed_bytes,
        "source_sha256": observed_sha,
        "metadata_receipt": metadata_receipt,
        "download_receipt": download_receipt,
        "synthetic_snapshot_sha256": hashlib.sha256(synthetic_snapshot).hexdigest(),
        "provider_identity_match": True,
        "authenticated_api_used": False,
        "credentials_supplied": False,
        "source_persistence": "EPHEMERAL_PURGE_REQUIRED_AFTER_SCHEMA_INSPECTION",
        "cohort_partition_constructed": False,
        "train_calibration_test_partition_constructed": False,
        "sealed_test_scored": False,
        "model_fit_performed": False,
        "scientific_result": None,
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    body["receipt_id"] = canonical_id("h132schemaacq", body)
    write_json(args.receipt, body)
    print(json.dumps({"receipt_id": body["receipt_id"], "source_sha256": observed_sha, "source_bytes": observed_bytes}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
