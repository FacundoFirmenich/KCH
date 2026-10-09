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

SOURCE_COMMIT = "e458afe20b8172db5a04194224cf21df5ec00dc4"
SCOPE = "HISTORICAL_CODE_ONLY_LARGE_V06_BUNDLE_SOURCE_QUORUM"
PREDECESSOR_RECEIPT = "h151runtimequorum:8160f92267d3d92586f9330fe373c16ead114f0903a561210f0c94e4f53633cc"
CHUNKS = {
    ".github/helical_v06_bundle/chunk_00": "b3223afa0400d89c82930609be872190dc295b36",
    ".github/helical_v06_bundle/chunk_01": "7342fb7b130bafb07cfe0151a5cbd7d45bebdad1",
    ".github/helical_v06_bundle/chunk_02": "932a0bf8c4a12ace6f5798a4c7ac94ac63d56fdc",
    ".github/helical_v06_bundle/chunk_03": "47b0fcbcb291d2c8e4fb77fd458a66abe0bf5c0b",
    ".github/helical_v06_bundle/chunk_04": "ad7b938a60c27eda9e1ec0d6ef34954990063e91",
}


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
    exact = {
        "status": "ACTIVE_UNTIL_SINGLE_SUCCESSOR_TERMINATES",
        "single_use": True,
        "scope": SCOPE,
        "source_commit": SOURCE_COMMIT,
        "predecessor_failed_receipt_id": PREDECESSOR_RECEIPT,
        "predecessor_outcome": "FAIL_CLOSED_NO_VALID_TRANSPORT",
        "selection_rule": "NO_BYTE_REPAIR; ACCEPT_ONLY_SAFE_ARCHIVE_WITH_COMPILED_CODE_AND_SYMBOL_INVENTORY",
        "transport_repair_authorized": False,
        "recursive_decoding_limit": 2,
        "scientific_data_access_authorized": False,
        "scientific_model_execution_authorized": False,
        "null_runtime_execution_authorized": False,
        "sealed_test_access_authorized": False,
        "publication_authority": False,
        "promotion_authority": False,
        "canonicalization_authority": False,
        "retrospective_mutation_authority": False,
    }
    for key, expected in exact.items():
        if value.get(key) != expected:
            raise RuntimeError(f"authority mismatch at {key}: {value.get(key)!r} != {expected!r}")
    if value.get("source_paths") != list(CHUNKS):
        raise RuntimeError("source path order drift")
    return value


def candidate_streams(raw: bytes) -> list[tuple[str, bytes, list[str]]]:
    out: list[tuple[str, bytes, list[str]]] = [("RAW_CONCATENATION", raw, [])]
    seen = {sha(raw)}
    frontier = [("RAW_CONCATENATION", raw, [])]
    for depth in range(2):
        new: list[tuple[str, bytes, list[str]]] = []
        for name, body, steps in frontier:
            normalized = b"".join(body.split())
            try:
                decoded = base64.b64decode(normalized, validate=True)
                digest = sha(decoded)
                if digest not in seen:
                    seen.add(digest)
                    new.append((f"{name}__BASE64_{depth+1}", decoded, steps + ["STRICT_BASE64_DECODE"]))
            except (binascii.Error, ValueError):
                pass
            if body.startswith(b"\x1f\x8b"):
                try:
                    decoded = gzip.decompress(body)
                    digest = sha(decoded)
                    if digest not in seen:
                        seen.add(digest)
                        new.append((f"{name}__GZIP_{depth+1}", decoded, steps + ["GZIP_CRC_VALIDATED_DECOMPRESS"]))
                except (gzip.BadGzipFile, EOFError, OSError):
                    pass
        out.extend(new)
        frontier = new
    return out


def tree_digest(root: Path) -> tuple[list[dict[str, Any]], str]:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        body = path.read_bytes()
        rows.append({"path": path.relative_to(root).as_posix(), "bytes": len(body), "sha256": sha(body)})
    return rows, sha(canonical(rows))


def probe(name: str, body: bytes, steps: list[str], root: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "candidate": name,
        "transformations": steps,
        "bytes": len(body),
        "sha256": sha(body),
        "first_32_hex": body[:32].hex(),
        "last_32_hex": body[-32:].hex(),
        "valid_archive": False,
    }
    destination = root / name
    destination.mkdir(parents=True, exist_ok=True)
    try:
        archive_type, members = v15.extract_archive(body, destination)
        rows, digest = tree_digest(destination)
        record.update({
            "valid_archive": True,
            "archive_type": archive_type,
            "archive_member_count": len(members),
            "regular_file_count": len(rows),
            "source_tree_sha256": digest,
            "source_tree": rows,
            "extracted_root": str(destination),
        })
    except Exception as exc:
        record.update({"error_type": type(exc).__name__, "error": str(exc)})
    return record


def persist_inventory(extracted: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    persisted = []
    skipped = []
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
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        body = target.read_bytes()
        persisted.append({"path": relative.as_posix(), "bytes": len(body), "sha256": sha(body), "suffix": suffix})
        if suffix == ".py":
            python_count += 1
            found, imports = v15.definitions(target)
            definitions_by_file[relative.as_posix()] = sorted(found)
            imports_by_file[relative.as_posix()] = imports
            all_definitions.update(found)
    if python_count == 0:
        raise RuntimeError("selected archive contains no compilable Python source")
    missing = sorted(set(v15.REQUIRED_SYMBOLS) - all_definitions)
    found = sorted(set(v15.REQUIRED_SYMBOLS) & all_definitions)
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
        "required_symbols_found": found,
        "required_symbol_locations": {symbol: sorted(path for path, names in definitions_by_file.items() if symbol in names) for symbol in found},
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
    output = args.output_code.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    authority = validate_authority(args.authority)
    receipt: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_15_2_LARGE_BUNDLE_RUNTIME_QUORUM_RECEIPT",
        "started_at_utc": utc_now(),
        "source_commit": SOURCE_COMMIT,
        "predecessor_failed_receipt_id": PREDECESSOR_RECEIPT,
        "transport_repair_performed": False,
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
        values = []
        for path, expected_blob in CHUNKS.items():
            observed = v15.git(repo, "rev-parse", f"{SOURCE_COMMIT}:{path}").decode("ascii").strip()
            if observed != expected_blob:
                raise RuntimeError(f"Git blob mismatch for {path}: {observed} != {expected_blob}")
            body = v15.git(repo, "show", f"{SOURCE_COMMIT}:{path}")
            values.append(body)
            source_rows.append({"path": path, "git_blob_sha1": observed, "bytes": len(body), "sha256": sha(body)})
        raw = b"".join(values)
        temp = Path(tempfile.mkdtemp(prefix="kch-helical-v0152-", dir=output.parent))
        probes = [probe(name, body, steps, temp) for name, body, steps in candidate_streams(raw)]
        valid = [item for item in probes if item["valid_archive"]]
        distinct = {item["source_tree_sha256"] for item in valid}
        if not valid:
            receipt.update({"outcome": "FAIL_CLOSED_NO_VALID_TRANSPORT", "exit_code": 50, "source_blobs": source_rows, "candidate_probes": probes})
            exit_code = 50
        elif len(distinct) > 1:
            receipt.update({"outcome": "FAIL_CLOSED", "exit_code": 50, "error": "multiple valid candidates yield different source trees", "source_blobs": source_rows, "candidate_probes": probes})
            exit_code = 50
        else:
            selected = valid[0]
            inventory = persist_inventory(Path(selected["extracted_root"]), output)
            missing = inventory["required_symbols_missing"]
            outcome = "HISTORICAL_RUNTIME_SOURCE_QUORUM_PASS" if not missing else "HISTORICAL_RUNTIME_PARTIAL_SOURCE_ONLY"
            exit_code = 0 if not missing else 30
            clean = [{key: value for key, value in item.items() if key != "extracted_root"} for item in probes]
            receipt.update({
                "outcome": outcome,
                "exit_code": exit_code,
                "authority_id": authority["authority_id"],
                "source_blobs": source_rows,
                "raw_concatenation_bytes": len(raw),
                "raw_concatenation_sha256": sha(raw),
                "candidate_probes": clean,
                "selected_candidate": selected["candidate"],
                "selected_transformations": selected["transformations"],
                "selected_source_tree_sha256": selected["source_tree_sha256"],
                "historical_identity_claim": "EXACT_LARGE_V0_6_BUNDLE_TRANSPORT_ONLY_NOT_V0_8_4_IDENTITY",
                **inventory,
            })
    except Exception as exc:
        receipt.update({"outcome": "FAIL_CLOSED", "exit_code": 50, "error_type": type(exc).__name__, "error": str(exc)})
        exit_code = 50
        if output.exists():
            shutil.rmtree(output)
    finally:
        if temp is not None and temp.exists():
            shutil.rmtree(temp)
        receipt["completed_at_utc"] = utc_now()
        receipt["authority_consumed"] = True
        receipt["authority_terminal_status"] = "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED"
        receipt["receipt_id"] = content_id("h152runtimequorum", receipt)
        write_json(args.receipt.resolve(), receipt)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
