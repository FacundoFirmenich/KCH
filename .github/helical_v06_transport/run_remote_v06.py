from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path

B64_SHA256 = "27a5d77456219fade65254b3bd7f5518726c7c31a246d6469054b5c683e039b9"
ZIP_SHA256 = "f8de0cff7dd03431a815fbe88da88c57a942d58f6e2f3bfd789f31af810c3b40"
PROTOCOL_FILE_SHA256 = "d1dbd521c3b58a27723d25aef5482bc44cd7fde9bbce78d038cffac3f4a30d1d"
PROTOCOL_BODY_SHA256 = "144c4aef47e8b9a88b2c74a92fae66a251581b5dd67295caaa4da6cef6e0827c"
CORE_RUNTIME_SHA256 = "a7d261274c92a2d1f4a161773b55fb3c3ecd561fbb7e093a9a9f14cbbf471bd6"
POWER_RUNTIME_SHA256 = "c6c354ff1a3c979352390581dcf403060bcd13f658382196fa5a44d413d1e5d9"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def run(cmd: list[str], *, stdout_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    if stdout_path is None:
        return subprocess.run(cmd, check=True, text=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as out:
        return subprocess.run(cmd, check=True, text=True, stdout=out, stderr=subprocess.STDOUT)


def reconstruct_locked_bundle(repo_root: Path, work_root: Path) -> tuple[Path, dict[str, object]]:
    chunks_dir = repo_root / ".github" / "helical_v06_bundle"
    chunk_paths = [chunks_dir / f"chunk_{i:02d}" for i in range(5)]
    raw = b"".join(p.read_bytes() for p in chunk_paths)
    canonical = b"".join(raw.split())
    diagnostics = {
        "chunk_bytes": {p.name: p.stat().st_size for p in chunk_paths},
        "chunk_sha256": {p.name: sha256_file(p) for p in chunk_paths},
        "raw_base64_bytes": len(raw),
        "raw_base64_sha256": sha256_bytes(raw),
        "canonical_base64_bytes": len(canonical),
        "canonical_base64_sha256": sha256_bytes(canonical),
        "expected_base64_sha256": B64_SHA256,
    }
    if diagnostics["canonical_base64_sha256"] != B64_SHA256:
        raise RuntimeError(f"canonical base64 hash mismatch: {diagnostics}")

    import base64

    zip_bytes = base64.b64decode(canonical, validate=True)
    diagnostics.update(
        {
            "decoded_zip_bytes": len(zip_bytes),
            "decoded_zip_sha256": sha256_bytes(zip_bytes),
            "expected_zip_sha256": ZIP_SHA256,
        }
    )
    if diagnostics["decoded_zip_sha256"] != ZIP_SHA256:
        raise RuntimeError(f"decoded ZIP hash mismatch: {diagnostics}")

    zip_path = work_root / "KCH_HELICAL_V06_TRANSPORT_RUNTIME.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(zip_bytes)
    runtime_root = work_root / "locked_bundle"
    runtime_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC failure: {bad}")
        zf.extractall(runtime_root)

    protocol = runtime_root / "spec" / "HELICAL_LOCAL_PIECEWISE_GATE_V0_6_LOCKED.json"
    core = runtime_root / "runtime" / "helical_v06.py"
    power = runtime_root / "runtime" / "power_v06.py"
    checks = {
        "protocol_file_sha256": sha256_file(protocol),
        "core_runtime_sha256": sha256_file(core),
        "power_runtime_sha256": sha256_file(power),
    }
    expected = {
        "protocol_file_sha256": PROTOCOL_FILE_SHA256,
        "core_runtime_sha256": CORE_RUNTIME_SHA256,
        "power_runtime_sha256": POWER_RUNTIME_SHA256,
    }
    if checks != expected:
        raise RuntimeError(f"locked file hash mismatch: observed={checks}, expected={expected}")
    diagnostics["locked_file_hashes"] = checks
    return runtime_root, diagnostics


def verify_protocol(runtime_root: Path) -> dict[str, object]:
    path = runtime_root / "spec" / "HELICAL_LOCAL_PIECEWISE_GATE_V0_6_LOCKED.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    body = dict(obj)
    body.pop("protocol_id", None)
    body.pop("protocol_sha256", None)
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    observed = sha256_bytes(canonical)
    if observed != PROTOCOL_BODY_SHA256:
        raise RuntimeError(f"protocol body mismatch: {observed}")
    if obj["protocol_id"] != "h6p:" + PROTOCOL_BODY_SHA256:
        raise RuntimeError("protocol ID mismatch")
    if obj["status"] != "LOCKED_BEFORE_V0_6_SOURCE_BYTE_ACQUISITION":
        raise RuntimeError("protocol is not in locked pre-acquisition state")
    if obj["locked_at_utc"] != "2026-09-27T01:44:51.945745Z":
        raise RuntimeError("unexpected lock timestamp")
    return obj


def acquire(protocol: dict[str, object], data_root: Path) -> None:
    transport = data_root / "transport"
    (transport / "headers").mkdir(parents=True, exist_ok=True)
    (transport / "curl").mkdir(parents=True, exist_ok=True)
    for source in protocol["sources"]:  # type: ignore[index]
        catalog_id = source["catalog_id"]
        output = data_root / source["relative_path"]
        output.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "curl",
            "--proto", "=https",
            "--tlsv1.2",
            "--fail-with-body",
            "--location",
            "--retry", "5",
            "--retry-all-errors",
            "--retry-delay", "2",
            "--connect-timeout", "30",
            "--max-time", "1200",
            "--header", "Accept-Encoding: identity",
            "--header", "Accept: text/plain,application/gzip,application/octet-stream;q=0.9,*/*;q=0.1",
            "--user-agent", "KCH-KwanBlocks-Helical-Lift/0.6 locked-gate via GitHub Actions",
            "--dump-header", str(transport / "headers" / f"{catalog_id}.headers"),
            "--output", str(output),
            "--write-out", "%{json}\\n",
            source["url"],
        ]
        run(cmd, stdout_path=transport / "curl" / f"{catalog_id}.json")


def audit_acquisition(protocol: dict[str, object], data_root: Path) -> dict[str, object]:
    datasets: list[dict[str, object]] = []
    for source in protocol["sources"]:  # type: ignore[index]
        catalog_id = source["catalog_id"]
        path = data_root / source["relative_path"]
        payload = path.read_bytes()
        if not payload:
            raise RuntimeError(f"{catalog_id}: empty payload")
        prefix = payload[:4096].lstrip().lower()
        if prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<body" in prefix:
            raise RuntimeError(f"{catalog_id}: HTML payload rejected")

        curl_path = data_root / "transport" / "curl" / f"{catalog_id}.json"
        header_path = data_root / "transport" / "headers" / f"{catalog_id}.headers"
        curl_meta = json.loads(curl_path.read_text(encoding="utf-8"))
        response_code = int(curl_meta.get("response_code", 0))
        size_download = int(float(curl_meta.get("size_download", -1)))
        if response_code != 200:
            raise RuntimeError(f"{catalog_id}: HTTP {response_code}")
        if size_download != len(payload):
            raise RuntimeError(f"{catalog_id}: curl bytes {size_download} != file bytes {len(payload)}")

        audit: dict[str, object] = {
            "catalog_id": catalog_id,
            "parser": source["parser"],
            "relative_path": source["relative_path"],
            "url": source["url"],
            "bytes": len(payload),
            "sha256": sha256_file(path),
            "headers_sha256": sha256_file(header_path),
            "curl_metadata_sha256": sha256_file(curl_path),
            "response_code": response_code,
            "url_effective": curl_meta.get("url_effective"),
            "remote_ip": curl_meta.get("remote_ip"),
            "content_type": curl_meta.get("content_type"),
            "num_redirects": curl_meta.get("num_redirects"),
            "ssl_verify_result": curl_meta.get("ssl_verify_result"),
            "size_download": size_download,
            "accept_encoding": "identity",
            "content_decoding_requested": False,
            "exact_entity_body_preserved": True,
        }
        parser = source["parser"]
        if parser in {"GROWCLUST25", "HYPODD24"}:
            if b"\x00" in payload:
                raise RuntimeError(f"{catalog_id}: NUL byte in text payload")
            text = payload.decode("utf-8", errors="strict")
            rows = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
            expected_fields = 25 if parser == "GROWCLUST25" else 24
            valid = sum(len(line.split()) == expected_fields for line in rows)
            if valid == 0:
                raise RuntimeError(f"{catalog_id}: no valid {expected_fields}-field rows")
            audit.update(
                physical_lines=len(text.splitlines()),
                noncomment_rows=len(rows),
                valid_schema_rows=valid,
                expected_fields=expected_fields,
                strict_utf8=True,
            )
        else:
            members: list[dict[str, object]] = []
            with tarfile.open(path, mode="r:gz") as tf:
                for member in tf.getmembers():
                    if member.isfile():
                        members.append({"name": member.name, "bytes": member.size})
            if not members:
                raise RuntimeError(f"{catalog_id}: tar.gz has no regular members")
            audit.update(tar_gz_integrity="PASS", regular_members=members)
        datasets.append(audit)

    body: dict[str, object] = {
        "format": "KCH_HELICAL_V0_6_EXACT_BYTE_ACQUISITION_RECEIPT",
        "version": "0.6.0",
        "protocol_id": protocol["protocol_id"],
        "protocol_locked_at_utc": protocol["locked_at_utc"],
        "acquired_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "runner": {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "sha": os.environ.get("GITHUB_SHA"),
            "ref": os.environ.get("GITHUB_REF"),
            "runner_os": os.environ.get("RUNNER_OS"),
        },
        "transport_contract": protocol["acquisition_contract"],
        "datasets": datasets,
        "all_exact_bytes_validated": len(datasets) == len(protocol["sources"]),  # type: ignore[arg-type]
        "inference_authorized_by_acquisition_gate": len(datasets) == len(protocol["sources"]),  # type: ignore[arg-type]
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt = {"receipt_id": "h6a:" + sha256_bytes(canonical), **body}
    write_json(data_root / "ACQUISITION_RECEIPT_V0_6.json", receipt)
    return receipt


def copy_if_exists(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def seal_artifact(artifact_root: Path) -> None:
    files = sorted(p for p in artifact_root.rglob("*") if p.is_file() and p.name not in {"SHA256SUMS.txt", "FILE_SIZES.txt"})
    (artifact_root / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256_file(p)}  {p.relative_to(artifact_root).as_posix()}\n" for p in files),
        encoding="utf-8",
    )
    all_files = sorted(p for p in artifact_root.rglob("*") if p.is_file())
    (artifact_root / "FILE_SIZES.txt").write_text(
        "".join(f"{p.relative_to(artifact_root).as_posix()}\t{p.stat().st_size} bytes\n" for p in all_files),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    args = parser.parse_args()

    work_root = args.work_root
    artifact_root = args.artifact_root
    data_root = work_root / "data"
    results_root = work_root / "results"
    runtime_root = work_root / "locked_bundle"
    artifact_root.mkdir(parents=True, exist_ok=True)
    status = 1
    try:
        runtime_root, transport_diag = reconstruct_locked_bundle(args.repo_root, work_root)
        write_json(work_root / "TRANSPORT_DIAGNOSTICS.json", transport_diag)
        protocol = verify_protocol(runtime_root)
        write_json(
            work_root / "PRE_ACQUISITION_LOCK_VERIFICATION.json",
            {
                "protocol_id": protocol["protocol_id"],
                "locked_at_utc": protocol["locked_at_utc"],
                "identity_verified_before_acquisition": True,
                "verified_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )
        acquire(protocol, data_root)
        audit_acquisition(protocol, data_root)
        results_root.mkdir(parents=True, exist_ok=True)
        stdout_log = results_root / "EXECUTION_STDOUT.log"
        cmd = [
            sys.executable,
            str(runtime_root / "runtime" / "helical_v06.py"),
            "run-gate",
            "--protocol", str(runtime_root / "spec" / "HELICAL_LOCAL_PIECEWISE_GATE_V0_6_LOCKED.json"),
            "--data-root", str(data_root),
            "--output-dir", str(results_root),
        ]
        run(cmd, stdout_path=stdout_log)
        status = 0
    except Exception as exc:  # fail closed and preserve evidence
        write_json(
            work_root / "FAIL_CLOSED_RECEIPT.json",
            {
                "format": "KCH_HELICAL_V0_6_FAIL_CLOSED_RECEIPT",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "inference_claim_authorized": False,
                "authority_ceiling": "NONE",
                "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )
        print(traceback.format_exc(), file=sys.stderr)
    finally:
        copy_if_exists(runtime_root, artifact_root / "locked_bundle")
        copy_if_exists(data_root, artifact_root / "data")
        copy_if_exists(results_root, artifact_root / "results")
        for name in ["TRANSPORT_DIAGNOSTICS.json", "PRE_ACQUISITION_LOCK_VERIFICATION.json", "FAIL_CLOSED_RECEIPT.json"]:
            copy_if_exists(work_root / name, artifact_root / name)
        seal_artifact(artifact_root)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
