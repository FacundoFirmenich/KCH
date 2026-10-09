from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import reconstruct_v06_runtime_quorum as v15
import reconstruct_large_v06_bundle_v0152 as v152

SOURCE_COMMIT = "e458afe20b8172db5a04194224cf21df5ec00dc4"
SCOPE = "HISTORICAL_CODE_ONLY_LOCKED_SINGLE_BASE64_CHARACTER_REPAIR_QUORUM"
PREDECESSOR_RECEIPT = "h153runtimequorum:7e12205dbf3a006d671db9b5b98a7cf9e2cd01d61e58b939f5f8d76905eadbe0"
CANONICAL_REPAIR_BLOB = "e0d7b4fa396ed90ce5f6cdc31d1f574baa714185"
TARGET_CHUNK_PATH = ".github/helical_v06_bundle/chunk_01"
TARGET_CHUNK_BLOB = "7342fb7b130bafb07cfe0151a5cbd7d45bebdad1"
TARGET_BYTES = 18_000
TARGET_SHA256 = "361626dd19369a518a8ea1d3754ad33bebd35689442607cb2996e4f95f10f593"


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
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_authority(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "status": "ACTIVE_UNTIL_SINGLE_SUCCESSOR_TERMINATES",
        "single_use": True,
        "scope": SCOPE,
        "source_commit": SOURCE_COMMIT,
        "predecessor_failed_receipt_id": PREDECESSOR_RECEIPT,
        "predecessor_failure": "CHUNK_01_STRICT_BASE64_INCORRECT_PADDING_AT_17999_BYTES",
        "canonical_repair_source_git_blob_sha1": CANONICAL_REPAIR_BLOB,
        "target_chunk_path": TARGET_CHUNK_PATH,
        "target_chunk_source_git_blob_sha1": TARGET_CHUNK_BLOB,
        "observed_bytes_before": 17_999,
        "required_bytes_after": TARGET_BYTES,
        "required_sha256_after": TARGET_SHA256,
        "authorized_mutation": "INSERT_EXACTLY_ONE_BASE64_ALPHABET_CHARACTER_IF_AND_ONLY_IF_UNIQUE_SHA256_MATCH",
        "maximum_insertions": 1,
        "maximum_deletions": 0,
        "maximum_substitutions": 0,
        "ambiguous_repair_authorized": False,
        "unlocked_repair_authorized": False,
        "transport_repair_authorized": True,
        "repair_receipt_required": True,
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


def verify_canonical_repair(repo: Path, script: Path) -> dict[str, Any]:
    observed_blob = subprocess.check_output(["git", "-C", str(repo), "hash-object", str(script)], text=True).strip()
    if observed_blob != CANONICAL_REPAIR_BLOB:
        raise RuntimeError(f"canonical repair source blob mismatch: {observed_blob} != {CANONICAL_REPAIR_BLOB}")
    compile(script.read_text(encoding="utf-8"), str(script), "exec")
    return {
        "path": script.relative_to(repo).as_posix(),
        "git_blob_sha1": observed_blob,
        "bytes": script.stat().st_size,
        "sha256": sha(script.read_bytes()),
    }


def run_locked_repair(script: Path, input_path: Path, receipt_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(script), "--input", str(input_path), "--receipt", str(receipt_path)],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "canonical locked repair rejected the transport: "
            + (completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}")
        )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("format") != "KCH_SINGLE_MISSING_BASE64_CHAR_TRANSPORT_REPAIR_RECEIPT_V1":
        raise RuntimeError("unexpected canonical repair receipt format")
    if receipt.get("status") not in {"RECOVERED_EXACT_LOCKED_CHUNK", "ALREADY_EXACT"}:
        raise RuntimeError(f"unexpected canonical repair terminal status: {receipt.get('status')!r}")
    if receipt.get("expected_bytes") != TARGET_BYTES or receipt.get("expected_sha256") != TARGET_SHA256:
        raise RuntimeError("canonical repair target lock drift")
    if receipt.get("status") == "RECOVERED_EXACT_LOCKED_CHUNK":
        if receipt.get("insertion_performed") is not True:
            raise RuntimeError("recovered repair did not record one insertion")
        position = receipt.get("recovered_position")
        character = receipt.get("recovered_character")
        if not isinstance(position, int) or not (0 <= position <= 17_999):
            raise RuntimeError("recovered insertion position invalid")
        if not isinstance(character, str) or len(character) != 1 or character.encode("ascii") not in [bytes((value,)) for value in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"]:
            raise RuntimeError("recovered insertion character is not one Base64-alphabet byte")
    repaired = input_path.read_bytes()
    if len(repaired) != TARGET_BYTES or sha(repaired) != TARGET_SHA256:
        raise RuntimeError("repaired chunk does not satisfy exact locked bytes/SHA-256")
    return {
        **receipt,
        "process_returncode": completed.returncode,
        "process_stdout_sha256": sha(completed.stdout.encode("utf-8")),
        "process_stderr_sha256": sha(completed.stderr.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--canonical-repair", required=True, type=Path)
    parser.add_argument("--output-code", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    output = args.output_code.resolve()
    receipt_path = args.receipt.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    authority = validate_authority(args.authority)
    receipt: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_15_4_LOCKED_SINGLE_CHAR_REPAIR_RUNTIME_QUORUM_RECEIPT",
        "started_at_utc": utc_now(),
        "source_commit": SOURCE_COMMIT,
        "predecessor_failed_receipt_id": PREDECESSOR_RECEIPT,
        "transport_repair_authorized": True,
        "transport_repair_scope": "ONE_SHA256_LOCKED_BASE64_INSERTION_IN_CHUNK_01_ONLY",
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
    temporary_root: Path | None = None
    try:
        v15.git(repo, "cat-file", "-e", f"{SOURCE_COMMIT}^{{commit}}")
        repair_source = verify_canonical_repair(repo, args.canonical_repair.resolve())
        source_rows: list[dict[str, Any]] = []
        raw_chunks: list[bytes] = []
        for ordinal, (path, expected_blob) in enumerate(v152.CHUNKS.items()):
            observed_blob = v15.git(repo, "rev-parse", f"{SOURCE_COMMIT}:{path}").decode("ascii").strip()
            if observed_blob != expected_blob:
                raise RuntimeError(f"Git blob mismatch for {path}: {observed_blob} != {expected_blob}")
            body = v15.git(repo, "show", f"{SOURCE_COMMIT}:{path}")
            if path == TARGET_CHUNK_PATH:
                if observed_blob != TARGET_CHUNK_BLOB or len(body) != 17_999:
                    raise RuntimeError("target chunk identity/length drift before locked repair")
            raw_chunks.append(body)
            source_rows.append({
                "ordinal": ordinal,
                "path": path,
                "git_blob_sha1": observed_blob,
                "bytes_before": len(body),
                "sha256_before": sha(body),
                "is_repair_target": path == TARGET_CHUNK_PATH,
            })

        temporary_root = Path(tempfile.mkdtemp(prefix="kch-helical-v0154-", dir=output.parent))
        repaired_chunk_path = temporary_root / "chunk_01.locked-repair.input"
        repaired_chunk_path.write_bytes(raw_chunks[1])
        repair_receipt_path = temporary_root / "LOCKED_SINGLE_CHAR_REPAIR_RECEIPT.json"
        repair_receipt = run_locked_repair(args.canonical_repair.resolve(), repaired_chunk_path, repair_receipt_path)
        raw_chunks[1] = repaired_chunk_path.read_bytes()
        source_rows[1].update({
            "bytes_after": len(raw_chunks[1]),
            "sha256_after": sha(raw_chunks[1]),
            "repair_receipt_id": repair_receipt["receipt_id"],
            "recovered_position": repair_receipt.get("recovered_position"),
            "recovered_character": repair_receipt.get("recovered_character"),
        })

        transported = b"".join(raw_chunks)
        normalized = b"".join(transported.split())
        try:
            archive_payload = base64.b64decode(normalized, validate=True)
        except binascii.Error as exc:
            raise RuntimeError(f"strict Base64 decode failed after exact locked repair: {exc}") from exc
        extracted = temporary_root / "extracted"
        extracted.mkdir(parents=True)
        archive_type, archive_members = v15.extract_archive(archive_payload, extracted)
        inventory = v152.persist_inventory(extracted, output)
        missing = inventory["required_symbols_missing"]
        outcome = "HISTORICAL_RUNTIME_SOURCE_QUORUM_PASS" if not missing else "HISTORICAL_RUNTIME_PARTIAL_SOURCE_ONLY"
        exit_code = 0 if not missing else 30
        receipt.update({
            "outcome": outcome,
            "exit_code": exit_code,
            "authority_id": authority["authority_id"],
            "canonical_repair_source": repair_source,
            "source_chunks": source_rows,
            "locked_repair_receipt": repair_receipt,
            "transported_base64_bytes_after_repair": len(transported),
            "transported_base64_sha256_after_repair": sha(transported),
            "normalized_base64_bytes_after_repair": len(normalized),
            "normalized_base64_sha256_after_repair": sha(normalized),
            "decoded_archive_bytes": len(archive_payload),
            "decoded_archive_sha256": sha(archive_payload),
            "decoded_archive_first_32_hex": archive_payload[:32].hex(),
            "decoded_archive_last_32_hex": archive_payload[-32:].hex(),
            "archive_type": archive_type,
            "archive_member_count": len(archive_members),
            "archive_members": archive_members,
            "historical_identity_claim": "EXACT_V0_6_LARGE_BUNDLE_WITH_CANONICAL_SHA256_LOCKED_SINGLE_CHAR_TRANSPORT_REPAIR_NOT_V0_8_4_IDENTITY",
            **inventory,
        })
    except Exception as exc:
        text = str(exc)
        if "canonical locked repair" in text or "recovered insertion" in text or "locked bytes" in text:
            outcome = "FAIL_CLOSED_LOCKED_REPAIR_NOT_UNIQUE"
        elif "Base64" in text or "archive" in text or "transport" in text:
            outcome = "FAIL_CLOSED_TRANSPORT_INVALID_AFTER_LOCKED_REPAIR"
        else:
            outcome = "FAIL_CLOSED"
        receipt.update({"outcome": outcome, "exit_code": 50, "error_type": type(exc).__name__, "error": text})
        exit_code = 50
        if output.exists():
            shutil.rmtree(output)
    finally:
        if temporary_root is not None and temporary_root.exists():
            shutil.rmtree(temporary_root)
        receipt["completed_at_utc"] = utc_now()
        receipt["authority_consumed"] = True
        receipt["authority_terminal_status"] = "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED"
        receipt["receipt_id"] = content_id("h154runtimequorum", receipt)
        write_json(receipt_path, receipt)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
