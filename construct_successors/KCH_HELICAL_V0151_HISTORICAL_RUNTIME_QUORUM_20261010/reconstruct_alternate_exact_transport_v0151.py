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

SOURCE_COMMIT = v15.SOURCE_COMMIT
PREDECESSOR_RECEIPT = "h15runtimequorum:a84e2effd93675f4758730631ba8e9d62d875ffe3be2cc15eb722e8893873193"
SCOPE = "HISTORICAL_CODE_ONLY_ALTERNATE_EXACT_TRANSPORT_ADJUDICATION"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_id(prefix: str, value: Any) -> str:
    return prefix + ":" + hashlib.sha256(canonical(value)).hexdigest()


def sha256_bytes(data: bytes) -> str:
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
        "predecessor_failure": "CHUNK_01_REDUNDANCY_MISMATCH",
        "selection_rule": "ACCEPT_ONLY_IF_EXACTLY_ONE_ROUTE_VALIDATES_OR_BOTH_PRODUCE_IDENTICAL_SOURCE_TREE",
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
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise RuntimeError(f"authority mismatch at {key}: {value.get(key)!r} != {expected_value!r}")
    if value.get("candidate_routes") != ["MAIN_CHUNK_01", "TEN_EXACT_CHUNK_01_SUBCHUNKS"]:
        raise RuntimeError("candidate route order drift")
    return value


def file_tree(root: Path) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        body = path.read_bytes()
        rows.append({"path": path.relative_to(root).as_posix(), "bytes": len(body), "sha256": sha256_bytes(body)})
    return rows, sha256_bytes(canonical(rows))


def probe_candidate(name: str, transported: bytes, work_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "route": name,
        "transported_bytes": len(transported),
        "transported_sha256": sha256_bytes(transported),
        "transport_repair_performed": False,
        "byte_mutation_performed": False,
        "valid": False,
    }
    candidate_root = work_root / name
    candidate_root.mkdir(parents=True, exist_ok=True)
    try:
        normalized = b"".join(transported.split())
        result["normalized_base64_bytes"] = len(normalized)
        result["normalized_base64_sha256"] = sha256_bytes(normalized)
        try:
            decoded = base64.b64decode(normalized, validate=True)
        except binascii.Error as exc:
            raise RuntimeError(f"strict Base64 decode failed: {exc}") from exc
        result["decoded_bytes"] = len(decoded)
        result["decoded_sha256"] = sha256_bytes(decoded)
        payload = decoded
        result["decompression"] = "none"
        if decoded.startswith(b"\x1f\x8b"):
            try:
                payload = gzip.decompress(decoded)
            except (gzip.BadGzipFile, EOFError, OSError) as exc:
                raise RuntimeError(f"gzip exact CRC/EOF validation failed: {exc}") from exc
            result["decompression"] = "gzip"
        result["archive_payload_bytes"] = len(payload)
        result["archive_payload_sha256"] = sha256_bytes(payload)
        extracted = candidate_root / "extracted"
        extracted.mkdir()
        archive_type, members = v15.extract_archive(payload, extracted)
        tree_rows, tree_sha = file_tree(extracted)
        result.update({
            "valid": True,
            "archive_type": archive_type,
            "archive_member_count": len(members),
            "regular_file_count": len(tree_rows),
            "source_tree_sha256": tree_sha,
            "source_tree": tree_rows,
            "extracted_root": str(extracted),
        })
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc)})
    return result


def persist_and_inventory(extracted: Path, output_code: Path) -> dict[str, Any]:
    if output_code.exists():
        shutil.rmtree(output_code)
    output_code.mkdir(parents=True)
    persisted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    definitions_by_file: dict[str, list[str]] = {}
    imports_by_file: dict[str, list[str]] = {}
    all_definitions: set[str] = set()
    python_count = 0
    for source in sorted(item for item in extracted.rglob("*") if item.is_file()):
        relative = source.relative_to(extracted)
        suffix = source.suffix.lower()
        size = source.stat().st_size
        if suffix not in v15.ALLOWED_SUFFIXES or size > v15.MAX_PERSISTED_FILE_BYTES:
            skipped.append({"path": relative.as_posix(), "bytes": size, "reason": "NON_CODE_OR_OVERSIZED"})
            continue
        target = output_code / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        body = target.read_bytes()
        persisted.append({"path": relative.as_posix(), "bytes": len(body), "sha256": sha256_bytes(body), "suffix": suffix})
        if suffix == ".py":
            python_count += 1
            found, imports = v15.definitions(target)
            key = relative.as_posix()
            definitions_by_file[key] = sorted(found)
            imports_by_file[key] = imports
            all_definitions.update(found)
    if python_count == 0:
        raise RuntimeError("selected exact transport contains no compilable Python source")
    missing = sorted(set(v15.REQUIRED_SYMBOLS) - all_definitions)
    found_required = sorted(set(v15.REQUIRED_SYMBOLS) & all_definitions)
    locations = {
        symbol: sorted(path for path, names in definitions_by_file.items() if symbol in names)
        for symbol in found_required
    }
    return {
        "persisted_code_file_count": len(persisted),
        "persisted_code_files": persisted,
        "skipped_member_count": len(skipped),
        "skipped_members": skipped,
        "python_file_count": python_count,
        "python_compile_pass": True,
        "definitions_by_file": definitions_by_file,
        "imports_by_file": imports_by_file,
        "required_symbol_count": len(v15.REQUIRED_SYMBOLS),
        "required_symbols_found": found_required,
        "required_symbol_locations": locations,
        "required_symbols_missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--output-code", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    output_code = args.output_code.resolve()
    receipt_path = args.receipt.resolve()
    output_code.parent.mkdir(parents=True, exist_ok=True)
    authority = validate_authority(args.authority)
    receipt: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_15_1_ALTERNATE_EXACT_TRANSPORT_ADJUDICATION_RECEIPT",
        "started_at_utc": utc_now(),
        "source_commit": SOURCE_COMMIT,
        "predecessor_failed_receipt_id": PREDECESSOR_RECEIPT,
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
        chunk_values: dict[str, bytes] = {}
        source_blobs: list[dict[str, Any]] = []
        for path, expected_blob in {**v15.MAIN_CHUNKS, **v15.SUBCHUNKS}.items():
            observed = v15.git(repo, "rev-parse", f"{SOURCE_COMMIT}:{path}").decode("ascii").strip()
            if observed != expected_blob:
                raise RuntimeError(f"Git blob mismatch for {path}: {observed} != {expected_blob}")
            body = v15.git(repo, "show", f"{SOURCE_COMMIT}:{path}")
            chunk_values[path] = body
            source_blobs.append({"path": path, "git_blob_sha1": observed, "bytes": len(body), "sha256": sha256_bytes(body)})

        main_route = b"".join(chunk_values[f".github/helical_v06/runtime_b64/chunk_{index:02d}"] for index in range(6))
        sub_route = b"".join(
            [chunk_values[".github/helical_v06/runtime_b64/chunk_00"]]
            + [chunk_values[f".github/helical_v06/runtime_b64/chunk_01_{index:02d}"] for index in range(10)]
            + [chunk_values[f".github/helical_v06/runtime_b64/chunk_{index:02d}"] for index in range(2, 6)]
        )
        temp = Path(tempfile.mkdtemp(prefix="kch-helical-v0151-", dir=output_code.parent))
        probes = [
            probe_candidate("MAIN_CHUNK_01", main_route, temp),
            probe_candidate("TEN_EXACT_CHUNK_01_SUBCHUNKS", sub_route, temp),
        ]
        valid = [probe for probe in probes if probe["valid"]]
        if not valid:
            outcome = "FAIL_CLOSED_NO_VALID_TRANSPORT"
            receipt.update({"outcome": outcome, "exit_code": 50, "source_blobs": source_blobs, "candidate_probes": probes})
            exit_code = 50
        elif len(valid) == 2 and valid[0]["source_tree_sha256"] != valid[1]["source_tree_sha256"]:
            outcome = "FAIL_CLOSED_AMBIGUOUS_TRANSPORT"
            receipt.update({"outcome": outcome, "exit_code": 50, "source_blobs": source_blobs, "candidate_probes": probes})
            exit_code = 50
        else:
            selected = valid[0]
            equivalence = "SINGLE_VALID_ROUTE" if len(valid) == 1 else "BOTH_VALID_IDENTICAL_SOURCE_TREE"
            inventory = persist_and_inventory(Path(selected["extracted_root"]), output_code)
            missing = inventory["required_symbols_missing"]
            outcome = "HISTORICAL_RUNTIME_SOURCE_QUORUM_PASS" if not missing else "HISTORICAL_RUNTIME_PARTIAL_SOURCE_ONLY"
            exit_code = 0 if not missing else 30
            clean_probes = [{key: value for key, value in probe.items() if key != "extracted_root"} for probe in probes]
            receipt.update({
                "outcome": outcome,
                "exit_code": exit_code,
                "authority_id": authority["authority_id"],
                "source_blobs": source_blobs,
                "candidate_routes_identical_bytes": main_route == sub_route,
                "candidate_probes": clean_probes,
                "selection_basis": equivalence,
                "selected_route": selected["route"],
                "selected_source_tree_sha256": selected["source_tree_sha256"],
                "historical_identity_claim": "EXACT_V0_6_SELECTED_TRANSPORT_ONLY_NOT_V0_8_4_IDENTITY",
                **inventory,
            })
    except Exception as exc:
        receipt.update({"outcome": "FAIL_CLOSED", "exit_code": 50, "error_type": type(exc).__name__, "error": str(exc)})
        exit_code = 50
        if output_code.exists():
            shutil.rmtree(output_code)
    finally:
        if temp is not None and temp.exists():
            shutil.rmtree(temp)
        receipt["completed_at_utc"] = utc_now()
        receipt["authority_consumed"] = True
        receipt["authority_terminal_status"] = "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED"
        receipt["receipt_id"] = content_id("h151runtimequorum", receipt)
        write_json(receipt_path, receipt)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
