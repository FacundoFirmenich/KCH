from __future__ import annotations

import argparse
import ast
import base64
import binascii
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any
import zipfile

SOURCE_COMMIT = "24703e036401185e935b363f839f059c8d49d57e"
MAIN_CHUNKS = {
    ".github/helical_v06/runtime_b64/chunk_00": "3ba37c990f0c3d29e7bedc3bee6deae3a5a8e654",
    ".github/helical_v06/runtime_b64/chunk_01": "b58197cb6d5d23fb9f33db03df7fc04c1bc3fd33",
    ".github/helical_v06/runtime_b64/chunk_02": "a06efca521f8e07bcd34a037bf70be9c01467be0",
    ".github/helical_v06/runtime_b64/chunk_03": "bc2ce20415f02a8b3facad8309e4c35e51fad60b",
    ".github/helical_v06/runtime_b64/chunk_04": "8661307e4f5166f25ddd0b1d312ffc5804fe90b3",
    ".github/helical_v06/runtime_b64/chunk_05": "40cb4b432cdfb1a4158b85a9c60623693fdce3b5",
}
SUBCHUNKS = {
    f".github/helical_v06/runtime_b64/chunk_01_{index:02d}": sha
    for index, sha in enumerate(
        [
            "94e0b6a7b0388f75f2bc263bab4389d3297fa02d",
            "d325e5957e04bb687352afc53cb20cf72e3cea73",
            "dbe24ced84046eacb15a0a461e2eaf8c443278ba",
            "415abf5ff15d4778a4f8c4d70fd7e857e65b294e",
            "8903a4d4456a818f8f4d9823553d304c13149ed7",
            "cdf2ac0652b274818ff76e6babe310a95913b374",
            "732a74050e0242967cba8eda4e7c1965c2293681",
            "5382db4560cf3c25a43c7e09f0ae862fdcadbd47",
            "b9c8618ef16ee32ec33e33601cae452a5a6d84f8",
            "35efd88a31111393a9f55d09928b28e2ce23a4eb",
        ]
    )
}
REQUIRED_SYMBOLS = (
    "circular_distance_degrees",
    "compute_parent_state",
    "draw_static_fields",
    "eval_intensity",
    "head_to_normal",
    "make_rewired_null",
    "moving_block_resample",
    "permute_within_bins",
    "posterior_mark_expectations",
    "propagate_mechanism_uncertainty",
    "reflected_rake",
    "rewire_parent_graph",
    "score_null_metrics",
    "seeded_rng",
    "simulate_catalog",
    "simulate_nonhelical_fixed_parent_weights",
    "static_logodds",
    "write_json",
)
ALLOWED_SUFFIXES = {".py", ".json", ".md", ".txt", ".toml", ".cfg", ".ini", ".yml", ".yaml"}
MAX_PERSISTED_FILE_BYTES = 2_000_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_id(prefix: str, value: Any) -> str:
    return prefix + ":" + hashlib.sha256(canonical(value)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def safe_member(name: str) -> bool:
    if not name or "\\" in name:
        return False
    value = PurePosixPath(name)
    return not value.is_absolute() and ".." not in value.parts and all(part not in {"", "."} for part in value.parts)


def extract_archive(payload: bytes, destination: Path) -> tuple[str, list[dict[str, Any]]]:
    members: list[dict[str, Any]] = []
    buffer = io.BytesIO(payload)
    if zipfile.is_zipfile(buffer):
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as archive:
            for info in archive.infolist():
                if not safe_member(info.filename):
                    raise RuntimeError(f"unsafe ZIP member: {info.filename!r}")
                unix_mode = (info.external_attr >> 16) & 0o170000
                if unix_mode in {0o120000, 0o060000}:
                    raise RuntimeError(f"link/device member forbidden: {info.filename!r}")
                if info.file_size > MAX_PERSISTED_FILE_BYTES * 10:
                    raise RuntimeError(f"oversized archive member: {info.filename!r}")
                members.append({"path": info.filename, "bytes": info.file_size, "crc32": f"{info.CRC:08x}"})
            archive.extractall(destination)
        return "zip", members
    buffer.seek(0)
    try:
        with tarfile.open(fileobj=buffer, mode="r:*") as archive:
            for member in archive.getmembers():
                if not safe_member(member.name):
                    raise RuntimeError(f"unsafe TAR member: {member.name!r}")
                if member.issym() or member.islnk() or member.isdev():
                    raise RuntimeError(f"link/device member forbidden: {member.name!r}")
                if member.size > MAX_PERSISTED_FILE_BYTES * 10:
                    raise RuntimeError(f"oversized archive member: {member.name!r}")
                members.append({"path": member.name, "bytes": member.size, "type": member.type.decode("latin1") if isinstance(member.type, bytes) else str(member.type)})
            archive.extractall(destination, filter="data")
        return "tar", members
    except tarfile.ReadError as exc:
        raise RuntimeError("decoded transport is neither a safe ZIP nor TAR archive") from exc


def definitions(path: Path) -> tuple[set[str], list[str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    found: set[str] = set()
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    compile(source, str(path), "exec")
    return found, sorted(set(imports))


def validate_authority(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "status": "ACTIVE_UNTIL_SINGLE_SUCCESSOR_TERMINATES",
        "single_use": True,
        "scope": "HISTORICAL_CODE_ONLY_RUNTIME_SOURCE_QUORUM",
        "source_commit": SOURCE_COMMIT,
        "transport_repair_authorized": False,
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
    output_code = args.output_code.resolve()
    receipt_path = args.receipt.resolve()
    started = utc_now()
    receipt: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_15_HISTORICAL_RUNTIME_SOURCE_QUORUM_RECEIPT",
        "started_at_utc": started,
        "source_commit": SOURCE_COMMIT,
        "transport_repair_performed": False,
        "scientific_data_accessed": False,
        "scientific_model_execution_performed": False,
        "null_runtime_execution_performed": False,
        "sealed_test_accessed": False,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "HISTORICAL_CODE_ONLY_RUNTIME_SOURCE_QUORUM",
    }
    exit_code = 50
    temp: Path | None = None
    try:
        authority = validate_authority(args.authority)
        git(repo, "cat-file", "-e", f"{SOURCE_COMMIT}^{{commit}}")
        source_rows: list[dict[str, Any]] = []
        chunk_values: dict[str, bytes] = {}
        for path, expected_blob in {**MAIN_CHUNKS, **SUBCHUNKS}.items():
            observed_blob = git(repo, "rev-parse", f"{SOURCE_COMMIT}:{path}").decode("ascii").strip()
            if observed_blob != expected_blob:
                raise RuntimeError(f"Git blob mismatch for {path}: {observed_blob} != {expected_blob}")
            value = git(repo, "show", f"{SOURCE_COMMIT}:{path}")
            chunk_values[path] = value
            source_rows.append({"path": path, "git_blob_sha1": observed_blob, "bytes": len(value), "sha256": sha256_bytes(value)})
        main_one = b"".join(chunk_values[f".github/helical_v06/runtime_b64/chunk_01_{index:02d}"] for index in range(10))
        if main_one != chunk_values[".github/helical_v06/runtime_b64/chunk_01"]:
            raise RuntimeError("chunk_01 does not equal the exact concatenation of its ten audited subchunks")
        transported = b"".join(chunk_values[path] for path in MAIN_CHUNKS)
        normalized = b"".join(transported.split())
        try:
            decoded = base64.b64decode(normalized, validate=True)
        except binascii.Error as exc:
            raise RuntimeError(f"strict Base64 decode failed without repair authority: {exc}") from exc
        decompression = "none"
        archive_payload = decoded
        if decoded.startswith(b"\x1f\x8b"):
            try:
                archive_payload = gzip.decompress(decoded)
                decompression = "gzip"
            except (gzip.BadGzipFile, EOFError, OSError) as exc:
                raise RuntimeError(f"gzip transport failed exact CRC/EOF validation: {exc}") from exc
        temp = Path(tempfile.mkdtemp(prefix="kch-helical-v015-", dir=output_code.parent))
        extracted = temp / "extracted"
        extracted.mkdir(parents=True)
        archive_type, archive_members = extract_archive(archive_payload, extracted)

        if output_code.exists():
            shutil.rmtree(output_code)
        output_code.mkdir(parents=True)
        persisted: list[dict[str, Any]] = []
        python_files: list[Path] = []
        definitions_by_file: dict[str, list[str]] = {}
        imports_by_file: dict[str, list[str]] = {}
        all_definitions: set[str] = set()
        skipped: list[dict[str, Any]] = []
        for source_path in sorted(item for item in extracted.rglob("*") if item.is_file()):
            relative = source_path.relative_to(extracted)
            suffix = source_path.suffix.lower()
            size = source_path.stat().st_size
            if suffix not in ALLOWED_SUFFIXES or size > MAX_PERSISTED_FILE_BYTES:
                skipped.append({"path": relative.as_posix(), "bytes": size, "reason": "NON_CODE_OR_OVERSIZED"})
                continue
            target = output_code / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target)
            body = target.read_bytes()
            row = {"path": relative.as_posix(), "bytes": len(body), "sha256": sha256_bytes(body), "suffix": suffix}
            persisted.append(row)
            if suffix == ".py":
                python_files.append(target)
                found, imports = definitions(target)
                key = relative.as_posix()
                definitions_by_file[key] = sorted(found)
                imports_by_file[key] = imports
                all_definitions.update(found)
        missing = sorted(set(REQUIRED_SYMBOLS) - all_definitions)
        found_required = sorted(set(REQUIRED_SYMBOLS) & all_definitions)
        required_locations = {
            symbol: sorted(path for path, names in definitions_by_file.items() if symbol in names)
            for symbol in found_required
        }
        if not python_files:
            raise RuntimeError("archive reconstructed but contains no compilable Python source")
        outcome = "HISTORICAL_RUNTIME_SOURCE_QUORUM_PASS" if not missing else "HISTORICAL_RUNTIME_PARTIAL_SOURCE_ONLY"
        exit_code = 0 if not missing else 30
        receipt.update({
            "outcome": outcome,
            "exit_code": exit_code,
            "authority_id": authority["authority_id"],
            "source_blobs": source_rows,
            "chunk_01_subchunk_equivalence": True,
            "transported_base64_bytes": len(transported),
            "normalized_base64_bytes": len(normalized),
            "transported_base64_sha256": sha256_bytes(transported),
            "normalized_base64_sha256": sha256_bytes(normalized),
            "decoded_bytes": len(decoded),
            "decoded_sha256": sha256_bytes(decoded),
            "decompression": decompression,
            "archive_payload_bytes": len(archive_payload),
            "archive_payload_sha256": sha256_bytes(archive_payload),
            "archive_type": archive_type,
            "archive_member_count": len(archive_members),
            "archive_members": archive_members,
            "persisted_code_file_count": len(persisted),
            "persisted_code_files": persisted,
            "skipped_member_count": len(skipped),
            "skipped_members": skipped,
            "python_file_count": len(python_files),
            "python_compile_pass": True,
            "definitions_by_file": definitions_by_file,
            "imports_by_file": imports_by_file,
            "required_symbol_count": len(REQUIRED_SYMBOLS),
            "required_symbols_found": found_required,
            "required_symbol_locations": required_locations,
            "required_symbols_missing": missing,
            "historical_identity_claim": "EXACT_V0_6_TRANSPORT_ONLY_NOT_V0_8_4_IDENTITY",
        })
    except Exception as exc:
        message = str(exc)
        outcome = "FAIL_CLOSED_TRANSPORT_CORRUPT" if any(token in message.lower() for token in ("base64", "gzip", "archive", "chunk")) else "FAIL_CLOSED"
        receipt.update({"outcome": outcome, "exit_code": 50, "error_type": type(exc).__name__, "error": message})
        exit_code = 50
        if output_code.exists():
            shutil.rmtree(output_code)
    finally:
        if temp is not None and temp.exists():
            shutil.rmtree(temp)
        receipt["completed_at_utc"] = utc_now()
        receipt["authority_consumed"] = True
        receipt["authority_terminal_status"] = "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED"
        receipt["receipt_id"] = content_id("h15runtimequorum", receipt)
        write_json(receipt_path, receipt)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
