from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_PROTOCOL_ID = "h6p:144c4aef47e8b9a88b2c74a92fae66a251581b5dd67295caaa4da6cef6e0827c"
EXPECTED_LOCKED_AT = "2026-09-27T01:44:51.945745Z"
SOURCE_ARTIFACT_ID = 10922031783
SOURCE_ARTIFACT_DIGEST = "sha256:c6a2e3245afad2e25d98c19e28ce82dbcce3115404f65474b1ac784edce26198"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def extract_curl_json(raw_text: str) -> tuple[dict[str, Any], int, int]:
    decoder = json.JSONDecoder()
    matches: list[tuple[dict[str, Any], int, int]] = []
    for index, char in enumerate(raw_text):
        if char != "{":
            continue
        try:
            value, length = decoder.raw_decode(raw_text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            matches.append((value, index, index + length))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one curl JSON object, observed {len(matches)}")
    return matches[0]


def audit_text_catalog(path: Path, expected_fields: int) -> dict[str, Any]:
    payload = path.read_bytes()
    if b"\x00" in payload:
        raise RuntimeError(f"{path}: NUL byte rejected")
    text = payload.decode("utf-8", errors="strict")
    physical_lines = text.splitlines()
    rows = [line for line in physical_lines if line.strip() and not line.lstrip().startswith("#")]
    counts: dict[int, int] = {}
    for line in rows:
        count = len(line.split())
        counts[count] = counts.get(count, 0) + 1
    valid = counts.get(expected_fields, 0)
    if valid == 0:
        raise RuntimeError(f"{path}: no valid {expected_fields}-field rows; counts={counts}")
    return {
        "physical_lines": len(physical_lines),
        "noncomment_rows": len(rows),
        "valid_schema_rows": valid,
        "field_count_histogram": {str(k): v for k, v in sorted(counts.items())},
        "expected_fields": expected_fields,
        "strict_utf8": True,
    }


def audit_tar_catalog(path: Path) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    with tarfile.open(path, mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            row_count_25 = 0
            strict_utf8 = False
            extracted = archive.extractfile(member)
            if extracted is not None:
                payload = extracted.read()
                try:
                    text = payload.decode("utf-8", errors="strict")
                    strict_utf8 = True
                    row_count_25 = sum(
                        1
                        for line in text.splitlines()
                        if line.strip() and not line.lstrip().startswith("#") and len(line.split()) == 25
                    )
                except UnicodeDecodeError:
                    pass
            members.append(
                {
                    "name": member.name,
                    "bytes": member.size,
                    "strict_utf8": strict_utf8,
                    "valid_25_field_rows": row_count_25,
                }
            )
    if not members:
        raise RuntimeError(f"{path}: tar.gz has no regular members")
    selected = sorted(
        members,
        key=lambda row: (-int(row["valid_25_field_rows"]), str(row["name"])),
    )[0]
    if int(selected["valid_25_field_rows"]) == 0:
        raise RuntimeError(f"{path}: no tar member with valid 25-field rows")
    return {
        "tar_gz_integrity": "PASS",
        "regular_member_count": len(members),
        "members": members,
        "selected_member_under_locked_rule": selected,
    }


def seal_tree(root: Path) -> None:
    ignored = {"SHA256SUMS.txt", "FILE_SIZES.txt"}
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name not in ignored)
    (root / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}\n" for path in files),
        encoding="utf-8",
    )
    all_files = sorted(p for p in root.rglob("*") if p.is_file())
    (root / "FILE_SIZES.txt").write_text(
        "".join(f"{path.relative_to(root).as_posix()}\t{path.stat().st_size} bytes\n" for path in all_files),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    input_root = args.input_root
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        locked_bundle = input_root / "locked_bundle"
        data_root = input_root / "data"
        protocol_path = locked_bundle / "spec" / "HELICAL_LOCAL_PIECEWISE_GATE_V0_6_LOCKED.json"
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        if protocol.get("protocol_id") != EXPECTED_PROTOCOL_ID:
            raise RuntimeError("protocol ID mismatch")
        if protocol.get("locked_at_utc") != EXPECTED_LOCKED_AT:
            raise RuntimeError("protocol lock timestamp mismatch")

        audit_rows: list[dict[str, Any]] = []
        canonical_curl_dir = output_root / "transport" / "curl_canonical"
        raw_curl_dir = output_root / "transport" / "curl_raw"
        header_dir = output_root / "transport" / "headers"
        sources_dir = output_root / "sources"

        for source in protocol["sources"]:
            catalog_id = source["catalog_id"]
            source_path = data_root / source["relative_path"]
            if not source_path.is_file():
                raise RuntimeError(f"missing acquired source: {source_path}")
            payload = source_path.read_bytes()
            if not payload:
                raise RuntimeError(f"empty acquired source: {catalog_id}")
            prefix = payload[:4096].lstrip().lower()
            if prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<body" in prefix:
                raise RuntimeError(f"HTML received instead of source: {catalog_id}")

            raw_curl_path = data_root / "transport" / "curl" / f"{catalog_id}.json"
            raw_header_path = data_root / "transport" / "headers" / f"{catalog_id}.headers"
            raw_text = raw_curl_path.read_text(encoding="utf-8", errors="strict")
            curl_meta, json_start, json_end = extract_curl_json(raw_text)
            response_code = int(curl_meta.get("response_code", curl_meta.get("http_code", 0)))
            size_download = int(float(curl_meta.get("size_download", -1)))
            if response_code != 200:
                raise RuntimeError(f"{catalog_id}: HTTP response {response_code}")
            if size_download != len(payload):
                raise RuntimeError(
                    f"{catalog_id}: curl size_download={size_download} != payload bytes={len(payload)}"
                )
            if curl_meta.get("url_effective") != source["url"]:
                raise RuntimeError(
                    f"{catalog_id}: effective URL differs from locked official URL: {curl_meta.get('url_effective')}"
                )

            if source["parser"] == "GROWCLUST25":
                schema = audit_text_catalog(source_path, 25)
            elif source["parser"] == "HYPODD24":
                schema = audit_text_catalog(source_path, 24)
            elif source["parser"] == "GROWCLUST25_TAR_GZ":
                schema = audit_tar_catalog(source_path)
            else:
                raise RuntimeError(f"unsupported locked parser: {source['parser']}")

            destination = sources_dir / source["relative_path"].split("sources/", 1)[-1]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            raw_curl_dir.mkdir(parents=True, exist_ok=True)
            header_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(raw_curl_path, raw_curl_dir / raw_curl_path.name)
            shutil.copy2(raw_header_path, header_dir / raw_header_path.name)
            write_json(canonical_curl_dir / f"{catalog_id}.json", curl_meta)

            audit_rows.append(
                {
                    "catalog_id": catalog_id,
                    "official_url": source["url"],
                    "relative_path": source["relative_path"],
                    "parser": source["parser"],
                    "bytes": len(payload),
                    "sha256": sha256_bytes(payload),
                    "http_response_code": response_code,
                    "url_effective": curl_meta.get("url_effective"),
                    "remote_ip": curl_meta.get("remote_ip"),
                    "size_download": size_download,
                    "raw_curl_receipt_sha256": sha256_file(raw_curl_path),
                    "raw_curl_prefix_bytes": json_start,
                    "raw_curl_suffix_bytes": len(raw_text) - json_end,
                    "canonical_curl_receipt_sha256": sha256_file(canonical_curl_dir / f"{catalog_id}.json"),
                    "headers_sha256": sha256_file(raw_header_path),
                    "exact_source_bytes_preserved": True,
                    "source_bytes_modified": False,
                    "receipt_serialization_repaired_only": True,
                    "schema_audit": schema,
                }
            )

        acquisition_body: dict[str, Any] = {
            "format": "KCH_HELICAL_V0_6_SUCCESSOR_ACQUISITION_RECEIPT",
            "version": "0.6.1-resume",
            "protocol_id": protocol["protocol_id"],
            "protocol_locked_at_utc": protocol["locked_at_utc"],
            "source_artifact_id": SOURCE_ARTIFACT_ID,
            "source_artifact_digest": SOURCE_ARTIFACT_DIGEST,
            "audited_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "datasets": audit_rows,
            "all_exact_bytes_validated": len(audit_rows) == len(protocol["sources"]),
            "inference_authorized": len(audit_rows) == len(protocol["sources"]),
            "scientific_runtime_changed": False,
            "protocol_changed": False,
            "thresholds_changed": False,
            "authority_ceiling": "NONE",
            "promotion": "BLOCKED",
            "canonicalization": "BLOCKED",
        }
        canonical = json.dumps(
            acquisition_body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        acquisition_receipt = {
            "receipt_id": "h6ar:" + sha256_bytes(canonical),
            **acquisition_body,
        }
        write_json(output_root / "SUCCESSOR_ACQUISITION_RECEIPT_V0_6.json", acquisition_receipt)

        results_dir = output_root / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = results_dir / "EXECUTION_STDOUT.log"
        command = [
            sys.executable,
            str(locked_bundle / "runtime" / "helical_v06.py"),
            "run-gate",
            "--protocol",
            str(protocol_path),
            "--data-root",
            str(data_root),
            "--output-dir",
            str(results_dir),
        ]
        with stdout_path.open("w", encoding="utf-8") as stdout:
            completed = subprocess.run(command, text=True, stdout=stdout, stderr=subprocess.STDOUT)
        if completed.returncode != 0:
            raise RuntimeError(f"locked scientific runtime returned {completed.returncode}")

        gate_path = results_dir / "V0_6_GATE_RESULT.json"
        gate_result = json.loads(gate_path.read_text(encoding="utf-8"))
        execution_body = {
            "format": "KCH_HELICAL_V0_6_EXACT_BYTE_RESUME_EXECUTION_RECEIPT",
            "protocol_id": protocol["protocol_id"],
            "source_acquisition_receipt_id": acquisition_receipt["receipt_id"],
            "executed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "python": sys.version,
            "gate_result_id": gate_result.get("gate_result_id"),
            "outcome": gate_result.get("outcome"),
            "model_execution_performed": True,
            "scientific_runtime_sha256": sha256_file(locked_bundle / "runtime" / "helical_v06.py"),
            "protocol_file_sha256": sha256_file(protocol_path),
            "thresholds_changed": False,
            "model_grid_changed": False,
            "authority_ceiling": "NONE",
            "promotion": "BLOCKED",
            "canonicalization": "BLOCKED",
        }
        execution_canonical = json.dumps(
            execution_body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        execution_receipt = {
            "execution_receipt_id": "h6xr:" + sha256_bytes(execution_canonical),
            **execution_body,
        }
        write_json(output_root / "EXACT_BYTE_RESUME_EXECUTION_RECEIPT.json", execution_receipt)
        shutil.copytree(locked_bundle, output_root / "locked_bundle", dirs_exist_ok=True)
        seal_tree(output_root)
        print(json.dumps(execution_receipt, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        write_json(
            output_root / "FAIL_CLOSED_RESUME_RECEIPT.json",
            {
                "format": "KCH_HELICAL_V0_6_EXACT_BYTE_RESUME_FAIL_CLOSED_RECEIPT",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "scientific_result_authorized": False,
                "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "authority_ceiling": "NONE",
            },
        )
        seal_tree(output_root)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
