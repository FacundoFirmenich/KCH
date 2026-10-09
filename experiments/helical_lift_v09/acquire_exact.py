from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

DATASET_ID = "2np9vw5v7w"
VERSION = 2
DOI = "10.17632/2np9vw5v7w.2"
REQUIRED_BASENAME = "focmec_ca_final.pickle"
SNAPSHOT_URL = f"https://api.data.mendeley.com/datasets/{DATASET_ID}?version={VERSION}"
FAULT_REPOSITORY = "GEMScienceTools/gem-global-active-faults"
FAULT_COMMIT = "56816508ad92fd6846dad1163b1c8c01376a2cd1"
FAULT_PATH = "geojson/gem_active_faults_harmonized.geojson"
FAULT_BLOB_SHA1 = "fb164770b529695544fa864abe2cc9dd8aa5793d"
FAULT_URL = f"https://raw.githubusercontent.com/{FAULT_REPOSITORY}/{FAULT_COMMIT}/{FAULT_PATH}"
USER_AGENT = "KCH-KwanBlocks-Helical-Lift/0.9 exact-byte blind acquisition"
CHUNK = 8 * 1024 * 1024
SAFE_RESPONSE_HEADERS = {
    "content-type", "content-length", "content-disposition", "etag",
    "last-modified", "accept-ranges", "date", "x-amz-version-id",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def safe_url_receipt(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    redacted = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return {
        "origin_and_path": redacted,
        "query_present": bool(parsed.query),
        "full_url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
    }


def safe_headers(headers: Any) -> dict[str, str]:
    output: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SAFE_RESPONSE_HEADERS:
            output[key.lower()] = str(value)
    return dict(sorted(output.items()))


def request_json(url: str) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "Accept-Encoding": "identity", "User-Agent": USER_AGENT})
    started = now_utc()
    with urllib.request.urlopen(req, timeout=300) as response:
        raw = response.read()
        receipt = {
            "requested": safe_url_receipt(url),
            "effective": safe_url_receipt(response.geturl()),
            "status": int(response.status),
            "headers": safe_headers(response.headers),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "started_at_utc": started,
            "finished_at_utc": now_utc(),
        }
    return json.loads(raw.decode("utf-8")), receipt, raw


def stream_download(url: str, destination: Path, *, accept: str) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    partial.unlink(missing_ok=True)
    req = urllib.request.Request(url, headers={"Accept": accept, "Accept-Encoding": "identity", "User-Agent": USER_AGENT})
    h = hashlib.sha256()
    size = 0
    started = now_utc()
    try:
        with urllib.request.urlopen(req, timeout=900) as response, partial.open("wb") as handle:
            while True:
                block = response.read(CHUNK)
                if not block:
                    break
                handle.write(block)
                h.update(block)
                size += len(block)
            handle.flush()
            os.fsync(handle.fileno())
            receipt = {
                "requested": safe_url_receipt(url),
                "effective": safe_url_receipt(response.geturl()),
                "status": int(response.status),
                "headers": safe_headers(response.headers),
                "bytes": size,
                "sha256": h.hexdigest(),
                "started_at_utc": started,
                "finished_at_utc": now_utc(),
            }
        partial.replace(destination)
        return receipt
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def walk_files(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        filename = value.get("filename") or value.get("file_name") or value.get("name")
        file_id = value.get("id") or value.get("uuid") or value.get("file_id")
        if filename and file_id:
            rows.append({"filename": str(filename), "file_id": str(file_id), "metadata": value})
        for child in value.values():
            rows.extend(walk_files(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(walk_files(child))
    return rows


def git_blob_sha1(path: Path) -> str:
    size = path.stat().st_size
    h = hashlib.sha1()
    h.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    data_dir = out / "data"
    receipts_dir = out / "receipts"
    out.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    receipts_dir.mkdir(parents=True, exist_ok=True)

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_9_EXACT_BYTE_ACQUISITION",
        "dataset_id": DATASET_ID,
        "dataset_version": VERSION,
        "doi": DOI,
        "required_basename": REQUIRED_BASENAME,
        "fault_repository": FAULT_REPOSITORY,
        "fault_commit": FAULT_COMMIT,
        "fault_path": FAULT_PATH,
        "expected_fault_git_blob_sha1": FAULT_BLOB_SHA1,
        "attempted_at_utc": now_utc(),
        "authority_ceiling": "NONE",
        "secrets_collected": False,
        "signed_redirect_urls_persisted": False,
    }
    try:
        snapshot, snapshot_receipt, snapshot_raw = request_json(SNAPSHOT_URL)
        files = walk_files(snapshot)
        raw_matches = [row for row in files if Path(row["filename"]).name == REQUIRED_BASENAME]
        matches_by_id = {row["file_id"]: row for row in raw_matches}
        matches = list(matches_by_id.values())
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one distinct {REQUIRED_BASENAME}; observed {len(matches)}")
        selected = matches[0]
        file_id = selected["file_id"]

        candidate_urls: list[str] = []
        metadata = selected["metadata"]
        for key in ("download_url", "file_download_url", "url"):
            candidate = metadata.get(key) if isinstance(metadata, dict) else None
            if isinstance(candidate, str):
                parsed = urllib.parse.urlsplit(candidate)
                if parsed.scheme == "https" and parsed.hostname in {"api.data.mendeley.com", "data.mendeley.com"}:
                    candidate_urls.append(candidate)
        candidate_urls.extend([
            f"https://api.data.mendeley.com/datasets/{DATASET_ID}/files/{file_id}/file_downloaded?version={VERSION}",
            f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/files/{file_id}/file_downloaded",
        ])
        candidate_urls = list(dict.fromkeys(candidate_urls))

        mechanism_path = data_dir / REQUIRED_BASENAME
        fault_path = data_dir / "gem_active_faults_harmonized.geojson"
        mechanism_errors: list[dict[str, str]] = []
        mechanism_receipt = None
        for candidate_url in candidate_urls:
            try:
                mechanism_receipt = stream_download(candidate_url, mechanism_path, accept="application/octet-stream")
                break
            except Exception as candidate_exc:
                mechanism_errors.append({
                    "url": safe_url_receipt(candidate_url)["origin_and_path"],
                    "error_type": type(candidate_exc).__name__,
                    "error": str(candidate_exc),
                })
        if mechanism_receipt is None:
            raise RuntimeError(f"all authoritative Mendeley file routes failed: {mechanism_errors}")
        mechanism_receipt["route_failures_before_success"] = mechanism_errors
        fault_receipt = stream_download(FAULT_URL, fault_path, accept="application/geo+json,application/json")

        if mechanism_path.stat().st_size == 0 or fault_path.stat().st_size == 0:
            raise RuntimeError("empty required entity body")
        json.loads(fault_path.read_text(encoding="utf-8"))
        observed_blob = git_blob_sha1(fault_path)
        if observed_blob != FAULT_BLOB_SHA1:
            raise RuntimeError(f"fault Git blob mismatch: {observed_blob}")
        prefix = mechanism_path.open("rb").read(64).lstrip().lower()
        if prefix.startswith(b"<html") or prefix.startswith(b"<!doctype"):
            raise RuntimeError("mechanism response is HTML, not the required entity body")

        snapshot_path = receipts_dir / "MENDELEY_SNAPSHOT_V2.json"
        snapshot_path.write_bytes(snapshot_raw)
        body.update({
            "outcome": "EXACT_BYTE_ACQUISITION_PASS",
            "all_or_none_pass": True,
            "snapshot_receipt": snapshot_receipt,
            "selected_file": {
                "basename": REQUIRED_BASENAME,
                "file_id": file_id,
                "metadata_sha256": hashlib.sha256(canonical(selected["metadata"])).hexdigest(),
                "declared_size": selected["metadata"].get("size") or selected["metadata"].get("file_size"),
            },
            "mechanism_receipt": mechanism_receipt,
            "fault_receipt": {**fault_receipt, "git_blob_sha1": observed_blob},
            "mechanism_relative_path": str(mechanism_path.relative_to(out)),
            "fault_relative_path": str(fault_path.relative_to(out)),
            "snapshot_relative_path": str(snapshot_path.relative_to(out)),
        })
        status = 0
    except Exception as exc:
        quarantine = out / "quarantine"
        quarantine.mkdir(exist_ok=True)
        for candidate in (data_dir / REQUIRED_BASENAME, data_dir / "gem_active_faults_harmonized.geojson"):
            if candidate.exists():
                shutil.move(str(candidate), str(quarantine / candidate.name))
        body.update({
            "outcome": "BLOCKED_EXACT_BYTE_ACQUISITION",
            "all_or_none_pass": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        status = 3
    body["receipt_id"] = "h9acq:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(receipts_dir / "ACQUISITION_RECEIPT_V0_9.json", body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
