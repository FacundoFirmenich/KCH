from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

import reconstruct_v06_runtime_quorum as v15
import reconstruct_large_v06_bundle_v0152 as v152

SOURCE_COMMIT = v152.SOURCE_COMMIT
SCOPE = "HISTORICAL_CODE_ONLY_CHUNKWISE_BASE64_BUNDLE_QUORUM"
PREDECESSOR = "h152runtimequorum:fcb759b5a4a39f5009e4ac8e4b8aeb351032cd8f4ba40f9987670fc989627a77"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_id(prefix: str, value: Any) -> str:
    return prefix + ":" + hashlib.sha256(canonical(value)).hexdigest()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def validate_authority(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "status": "ACTIVE_UNTIL_SINGLE_SUCCESSOR_TERMINATES",
        "single_use": True,
        "scope": SCOPE,
        "source_commit": SOURCE_COMMIT,
        "predecessor_failed_receipt_id": PREDECESSOR,
        "predecessor_failure": "BASE64_CHUNKS_CONCATENATED_BEFORE_DECODING",
        "transport_semantics": "STRICT_BASE64_DECODE_EACH_EXACT_GIT_BLOB_THEN_CONCATENATE_DECODED_BYTES",
        "transport_repair_authorized": False,
        "byte_insertion_authorized": False,
        "byte_deletion_authorized": False,
        "byte_substitution_authorized": False,
        "scientific_data_access_authorized": False,
        "scientific_model_execution_authorized": False,
        "null_runtime_execution_authorized": False,
        "sealed_test_access_authorized": False,
        "publication_authority": False,
        "promotion_authority": False,
        "canonicalization_authority": False,
        "retrospective_mutation_authority": False,
    }
    for key, required in expected.items():
        if value.get(key) != required:
            raise RuntimeError(f"authority mismatch at {key}: {value.get(key)!r} != {required!r}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--output-code", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    output = args.output_code.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    authority = validate_authority(args.authority)
    receipt: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_15_3_CHUNKWISE_BUNDLE_RUNTIME_QUORUM_RECEIPT",
        "started_at_utc": utc_now(),
        "source_commit": SOURCE_COMMIT,
        "predecessor_failed_receipt_id": PREDECESSOR,
        "transport_semantics": "STRICT_BASE64_DECODE_EACH_EXACT_GIT_BLOB_THEN_CONCATENATE_DECODED_BYTES",
        "transport_repair_performed": False,
        "byte_mutation_performed": False,
        "scientific_data_accessed": False,
        "scientific_model_execution_performed": False,
        "null_runtime_execution_performed": False,
        "sealed_test_accessed": False,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": SCOPE,
    }
    exit_code = 50
    temp: Path | None = None
    try:
        v15.git(repo, "cat-file", "-e", f"{SOURCE_COMMIT}^{{commit}}")
        source_rows = []
        decoded_parts = []
        for ordinal, (path, expected_blob) in enumerate(v152.CHUNKS.items()):
            observed = v15.git(repo, "rev-parse", f"{SOURCE_COMMIT}:{path}").decode("ascii").strip()
            if observed != expected_blob:
                raise RuntimeError(f"Git blob mismatch for {path}: {observed} != {expected_blob}")
            raw = v15.git(repo, "show", f"{SOURCE_COMMIT}:{path}")
            normalized = b"".join(raw.split())
            try:
                decoded = base64.b64decode(normalized, validate=True)
            except binascii.Error as exc:
                raise RuntimeError(f"strict Base64 decode failed for exact chunk {ordinal}: {exc}") from exc
            decoded_parts.append(decoded)
            source_rows.append({
                "ordinal": ordinal,
                "path": path,
                "git_blob_sha1": observed,
                "raw_bytes": len(raw),
                "raw_sha256": sha(raw),
                "normalized_base64_bytes": len(normalized),
                "normalized_base64_sha256": sha(normalized),
                "decoded_bytes": len(decoded),
                "decoded_sha256": sha(decoded),
                "decoded_first_8_hex": decoded[:8].hex(),
                "decoded_last_8_hex": decoded[-8:].hex(),
            })
        payload = b"".join(decoded_parts)
        transforms = ["STRICT_BASE64_DECODE_EACH_EXACT_GIT_BLOB", "CONCATENATE_DECODED_PARTS_IN_DECLARED_ORDER"]
        if payload.startswith(b"\x1f\x8b"):
            try:
                payload = gzip.decompress(payload)
            except (gzip.BadGzipFile, EOFError, OSError) as exc:
                raise RuntimeError(f"chunkwise-decoded gzip failed CRC/EOF validation: {exc}") from exc
            transforms.append("GZIP_CRC_VALIDATED_DECOMPRESS")
        temp = Path(tempfile.mkdtemp(prefix="kch-helical-v0153-", dir=output.parent))
        extracted = temp / "extracted"
        extracted.mkdir(parents=True)
        archive_type, members = v15.extract_archive(payload, extracted)
        inventory = v152.persist_inventory(extracted, output)
        missing = inventory["required_symbols_missing"]
        outcome = "HISTORICAL_RUNTIME_SOURCE_QUORUM_PASS" if not missing else "HISTORICAL_RUNTIME_PARTIAL_SOURCE_ONLY"
        exit_code = 0 if not missing else 30
        receipt.update({
            "outcome": outcome,
            "exit_code": exit_code,
            "authority_id": authority["authority_id"],
            "source_chunks": source_rows,
            "decoded_concatenation_bytes": sum(row["decoded_bytes"] for row in source_rows),
            "selected_payload_bytes": len(payload),
            "selected_payload_sha256": sha(payload),
            "selected_payload_first_32_hex": payload[:32].hex(),
            "selected_payload_last_32_hex": payload[-32:].hex(),
            "transformations": transforms,
            "archive_type": archive_type,
            "archive_member_count": len(members),
            "archive_members": members,
            "historical_identity_claim": "EXACT_CHUNKWISE_DECODED_LARGE_V0_6_BUNDLE_NOT_V0_8_4_IDENTITY",
            **inventory,
        })
    except Exception as exc:
        receipt.update({"outcome": "FAIL_CLOSED_NO_VALID_TRANSPORT", "exit_code": 50, "error_type": type(exc).__name__, "error": str(exc)})
        exit_code = 50
        if output.exists():
            shutil.rmtree(output)
    finally:
        if temp is not None and temp.exists():
            shutil.rmtree(temp)
        receipt["completed_at_utc"] = utc_now()
        receipt["authority_consumed"] = True
        receipt["authority_terminal_status"] = "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED"
        receipt["receipt_id"] = content_id("h153runtimequorum", receipt)
        write_json(args.receipt.resolve(), receipt)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
