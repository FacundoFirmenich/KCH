from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import time
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request

from common_v09 import (
    assert_no_known_secret_names,
    canonical_json_bytes,
    content_id,
    fsync_directory,
    git_blob_sha1,
    safe_url_descriptor,
    sanitize_text,
    sha256_file,
    strip_known_secret_environment,
    utc_now,
    write_json_atomic,
)

FORMAT = "KCH_HELICAL_V0_9_TRANSACTIONAL_EXACT_BYTE_ACQUISITION"
DATASET_ID = "2np9vw5v7w"
VERSION = 2
DOI = "10.17632/2np9vw5v7w.2"
REQUIRED_BASENAME = "focmec_ca_final.pickle"
SNAPSHOT_URL = f"https://data.mendeley.com/public-api/datasets/{DATASET_ID}/files?folder_id=root&version={VERSION}"
FAULT_REPOSITORY = "GEMScienceTools/gem-global-active-faults"
FAULT_COMMIT = "56816508ad92fd6846dad1163b1c8c01376a2cd1"
FAULT_PATH = "geojson/gem_active_faults_harmonized.geojson"
FAULT_BASENAME = "gem_active_faults_harmonized.geojson"
FAULT_URL = f"https://raw.githubusercontent.com/{FAULT_REPOSITORY}/{FAULT_COMMIT}/{FAULT_PATH}"
FAULT_GIT_BLOB_SHA1 = "fb164770b529695544fa864abe2cc9dd8aa5793d"
FAULT_BYTES = 10_622_730
MAX_METADATA_BYTES = 64 * 1024 * 1024
HEADER_ALLOWLIST = {
    "content-type", "content-length", "content-range", "accept-ranges", "etag",
    "last-modified", "digest", "content-md5", "x-amz-version-id", "x-amz-request-id",
    "x-ms-version", "x-ms-blob-type", "cache-control",
}


class TrackingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, redirects: list[dict[str, Any]]) -> None:
        super().__init__()
        self.redirects = redirects

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> urllib.request.Request | None:
        if urllib.parse.urlsplit(newurl).scheme.lower() != "https":
            raise RuntimeError("redirect to a non-HTTPS endpoint is forbidden")
        self.redirects.append(
            {
                "status": int(code),
                "from": safe_url_descriptor(req.full_url),
                "to": safe_url_descriptor(newurl),
            }
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def public_https_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("only absolute HTTPS URLs are admissible")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("local endpoints are forbidden")
    try:
        packed = socket.inet_pton(socket.AF_INET, host)
        first, second = packed[0], packed[1]
        private = (
            first == 10 or first == 127 or first == 0 or
            (first == 169 and second == 254) or
            (first == 172 and 16 <= second <= 31) or
            (first == 192 and second == 168)
        )
        if private:
            raise ValueError("private IPv4 endpoints are forbidden")
    except OSError:
        pass


def filtered_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        str(name).lower(): str(value)
        for name, value in headers.items()
        if str(name).lower() in HEADER_ALLOWLIST
    }


def request_bytes(url: str, *, accept: str, timeout_seconds: int) -> tuple[bytes, dict[str, Any]]:
    public_https_url(url)
    redirects: list[dict[str, Any]] = []
    opener = urllib.request.build_opener(TrackingRedirectHandler(redirects))
    req = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Accept-Encoding": "identity",
            "User-Agent": "KCH-KwanBlocks-Helical-Lift/0.9 exact-byte transport",
        },
    )
    started = time.monotonic()
    with opener.open(req, timeout=timeout_seconds) as response:
        status = int(response.getcode())
        if status != 200:
            raise RuntimeError(f"unexpected HTTP status for metadata: {status}")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_METADATA_BYTES:
                raise RuntimeError("metadata response exceeds hard byte limit")
            chunks.append(block)
        data = b"".join(chunks)
        receipt = {
            "requested": safe_url_descriptor(url),
            "effective": safe_url_descriptor(response.geturl()),
            "redirects": redirects,
            "status": status,
            "headers": filtered_headers(response.headers),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "elapsed_seconds": time.monotonic() - started,
        }
    return data, receipt


def hash_existing_prefix(path: Path, chunk_bytes: int) -> hashlib._Hash:
    h = hashlib.sha256()
    if path.exists():
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(chunk_bytes), b""):
                h.update(block)
    return h


def stream_download(
    url: str,
    final_path: Path,
    *,
    accept: str,
    timeout_seconds: int,
    chunk_bytes: int,
    expected_bytes: int | None = None,
) -> dict[str, Any]:
    public_https_url(url)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    part = final_path.with_name(final_path.name + ".part")
    if final_path.exists():
        observed_bytes = final_path.stat().st_size
        if expected_bytes is not None and observed_bytes != expected_bytes:
            raise RuntimeError(f"existing cache final has wrong size: {observed_bytes}")
        return {
            "cache_reused": True,
            "requested": safe_url_descriptor(url),
            "effective": None,
            "redirects": [],
            "status": None,
            "headers": {},
            "resumed_from_bytes": observed_bytes,
            "bytes": observed_bytes,
            "sha256": sha256_file(final_path),
            "elapsed_seconds": 0.0,
        }

    resumed_from = part.stat().st_size if part.exists() else 0
    redirects: list[dict[str, Any]] = []
    opener = urllib.request.build_opener(TrackingRedirectHandler(redirects))
    headers = {
        "Accept": accept,
        "Accept-Encoding": "identity",
        "User-Agent": "KCH-KwanBlocks-Helical-Lift/0.9 resumable exact-byte transport",
    }
    if resumed_from:
        headers["Range"] = f"bytes={resumed_from}-"
    req = urllib.request.Request(url, headers=headers)
    started = time.monotonic()
    with opener.open(req, timeout=timeout_seconds) as response:
        status = int(response.getcode())
        if status not in {200, 206}:
            raise RuntimeError(f"unexpected HTTP status: {status}")
        if resumed_from and status == 200:
            # Server ignored Range; restart without concatenating two representations.
            resumed_from = 0
            part.unlink(missing_ok=True)
        if status == 206:
            content_range = response.headers.get("Content-Range", "")
            if not content_range.startswith(f"bytes {resumed_from}-"):
                raise RuntimeError(f"Content-Range does not match local prefix: {content_range!r}")
        mode = "ab" if resumed_from else "wb"
        h = hash_existing_prefix(part, chunk_bytes) if resumed_from else hashlib.sha256()
        total = resumed_from
        with part.open(mode) as handle:
            while True:
                block = response.read(chunk_bytes)
                if not block:
                    break
                handle.write(block)
                h.update(block)
                total += len(block)
            handle.flush()
            os.fsync(handle.fileno())
        if expected_bytes is not None and total != expected_bytes:
            raise RuntimeError(f"downloaded byte count {total} differs from required {expected_bytes}")
        os.replace(part, final_path)
        fsync_directory(final_path.parent)
        receipt = {
            "cache_reused": False,
            "requested": safe_url_descriptor(url),
            "effective": safe_url_descriptor(response.geturl()),
            "redirects": redirects,
            "status": status,
            "headers": filtered_headers(response.headers),
            "resumed_from_bytes": resumed_from,
            "bytes": total,
            "sha256": h.hexdigest(),
            "elapsed_seconds": time.monotonic() - started,
        }
    return receipt


def walk_files(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        filename = value.get("filename") or value.get("file_name") or value.get("name")
        file_id = value.get("id") or value.get("uuid") or value.get("file_id")
        if filename and file_id:
            rows.append({"filename": str(filename), "file_id": str(file_id), "raw": value})
        for child in value.values():
            rows.extend(walk_files(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(walk_files(child))
    return rows


def first_positive_integer(value: Any, keys: set[str]) -> int | None:
    values: list[int] = []
    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if str(key).lower() in keys:
                    try:
                        candidate = int(child)
                    except (TypeError, ValueError):
                        candidate = 0
                    if candidate > 0:
                        values.append(candidate)
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(value)
    unique = sorted(set(values))
    return unique[0] if len(unique) == 1 else None


def expected_digest(value: Any) -> str | None:
    candidates: list[str] = []
    def visit(node: Any, parent_key: str = "") -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                k = str(key).lower()
                if k in {"sha256", "sha_256", "checksum_sha256"} and isinstance(child, str):
                    normalized = child.lower().removeprefix("sha256:")
                    if len(normalized) == 64 and all(ch in "0123456789abcdef" for ch in normalized):
                        candidates.append(normalized)
                visit(child, k)
        elif isinstance(node, list):
            for child in node:
                visit(child, parent_key)
    visit(value)
    unique = sorted(set(candidates))
    return unique[0] if len(unique) == 1 else None


def hardlink_or_copy(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except OSError:
        shutil.copyfile(source, destination)
        with destination.open("rb") as handle:
            os.fsync(handle.fileno())


def validate_committed(directory: Path) -> dict[str, Any] | None:
    receipt_path = directory / "ACQUISITION_RECEIPT_V0_9.json"
    mechanism = directory / REQUIRED_BASENAME
    fault = directory / FAULT_BASENAME
    snapshot = directory / "mendeley_dataset_snapshot_v2.json"
    if not all(path.is_file() for path in (receipt_path, mechanism, fault, snapshot)):
        return None
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("outcome") != "EXACT_BYTE_ACQUISITION_PASS" or receipt.get("all_or_none_pass") is not True:
        return None
    source_receipts = receipt.get("source_receipts", {})
    if sha256_file(mechanism) != source_receipts.get("mechanism", {}).get("sha256"):
        return None
    if sha256_file(fault) != source_receipts.get("fault", {}).get("sha256"):
        return None
    if fault.stat().st_size != FAULT_BYTES or git_blob_sha1(fault) != FAULT_GIT_BLOB_SHA1:
        return None
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Transactional, resumable, exact-byte acquisition for the locked v0.8 scientific protocol")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--execute-network", action="store_true", help="Required explicit flag; otherwise the command is effect-free")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--chunk-mib", type=int, default=8)
    args = parser.parse_args()

    removed_secret_names = strip_known_secret_environment()
    workspace = args.workspace.resolve()
    cache = workspace / "cache"
    receipts_dir = workspace / "receipts"
    committed = workspace / "exact_sources"
    workspace.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    receipts_dir.mkdir(parents=True, exist_ok=True)
    attempt_started = utc_now()
    body: dict[str, Any] = {
        "transport_adapter": "0.9.1-public-versioned-files",
        "format": FORMAT,
        "attempted_at_utc": attempt_started,
        "dataset_id": DATASET_ID,
        "version": VERSION,
        "doi": DOI,
        "required_basename": REQUIRED_BASENAME,
        "fault_network": {
            "repository": FAULT_REPOSITORY,
            "commit": FAULT_COMMIT,
            "path": FAULT_PATH,
            "expected_git_blob_sha1": FAULT_GIT_BLOB_SHA1,
            "expected_bytes": FAULT_BYTES,
        },
        "dry_run_default": True,
        "execute_network_explicit": bool(args.execute_network),
        "all_or_none_pass": False,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "secret_values_accepted": False,
        "known_secret_environment_names_removed": removed_secret_names,
        "known_secret_named_environment_present_after_scrub": assert_no_known_secret_names(),
    }

    existing = validate_committed(committed) if committed.exists() else None
    if existing is not None:
        body.update(
            outcome="EXACT_BYTE_ACQUISITION_PASS",
            all_or_none_pass=True,
            idempotent_reuse=True,
            committed_receipt_id=existing.get("receipt_id"),
            completed_at_utc=utc_now(),
        )
        body["receipt_id"] = content_id("h9acqattempt", body)
        write_json_atomic(receipts_dir / "ACQUISITION_ATTEMPT_V0_9.json", body)
        print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
        return 0

    if not args.execute_network:
        body.update(
            outcome="DRY_RUN_NO_EFFECT",
            idempotent_reuse=False,
            completed_at_utc=utc_now(),
        )
        body["receipt_id"] = content_id("h9acqattempt", body)
        write_json_atomic(receipts_dir / "ACQUISITION_ATTEMPT_V0_9.json", body)
        print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
        return 4

    staging: Path | None = None
    try:
        metadata_bytes, metadata_receipt = request_bytes(
            SNAPSHOT_URL,
            accept="application/vnd.mendeley-public-dataset.1+json,application/json",
            timeout_seconds=args.timeout_seconds,
        )
        snapshot = json.loads(metadata_bytes.decode("utf-8"))
        files = walk_files(snapshot)
        matches = [row for row in files if Path(row["filename"]).name == REQUIRED_BASENAME]
        if len(matches) != 1:
            raise RuntimeError(f"expected one exact required basename in the public versioned snapshot; observed {len(matches)}")
        match = matches[0]
        file_id = match["file_id"]
        details = match["raw"].get("content_details")
        if not isinstance(details, dict):
            raise RuntimeError("official file metadata lacks content_details")
        file_url = details.get("download_url")
        if not isinstance(file_url, str) or not file_url:
            raise RuntimeError("official file metadata lacks download_url")
        public_https_url(file_url)
        if urllib.parse.urlsplit(file_url).hostname not in {"data.mendeley.com", "api.data.mendeley.com"}:
            raise RuntimeError("provider download redirect must originate on Mendeley")
        expected_mechanism_bytes = first_positive_integer(match["raw"], {"size", "file_size", "content_length", "bytes"})
        expected_mechanism_sha256 = expected_digest(match["raw"])

        mechanism_cache = cache / REQUIRED_BASENAME
        mechanism_receipt = stream_download(
            file_url,
            mechanism_cache,
            accept="application/octet-stream",
            timeout_seconds=args.timeout_seconds,
            chunk_bytes=args.chunk_mib * 1024 * 1024,
            expected_bytes=expected_mechanism_bytes,
        )
        if expected_mechanism_sha256 and mechanism_receipt["sha256"] != expected_mechanism_sha256:
            raise RuntimeError("mechanism entity SHA-256 differs from the unique provider-declared SHA-256")

        fault_cache = cache / FAULT_BASENAME
        fault_receipt = stream_download(
            FAULT_URL,
            fault_cache,
            accept="application/geo+json,application/json",
            timeout_seconds=args.timeout_seconds,
            chunk_bytes=args.chunk_mib * 1024 * 1024,
            expected_bytes=FAULT_BYTES,
        )
        observed_blob = git_blob_sha1(fault_cache)
        if observed_blob != FAULT_GIT_BLOB_SHA1:
            raise RuntimeError(f"fault-network Git blob mismatch: {observed_blob}")
        with fault_cache.open("r", encoding="utf-8") as handle:
            parsed_fault = json.load(handle)
        if parsed_fault.get("type") != "FeatureCollection" or not isinstance(parsed_fault.get("features"), list):
            raise RuntimeError("fault-network entity is not the required GeoJSON FeatureCollection")

        staging = Path(tempfile.mkdtemp(prefix=".exact_sources_v09.", dir=workspace))
        mechanism_stage = staging / REQUIRED_BASENAME
        fault_stage = staging / FAULT_BASENAME
        snapshot_stage = staging / "mendeley_dataset_snapshot_v2.json"
        hardlink_or_copy(mechanism_cache, mechanism_stage)
        hardlink_or_copy(fault_cache, fault_stage)
        with snapshot_stage.open("wb") as handle:
            handle.write(metadata_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        acquisition = {
            "format": FORMAT,
            "outcome": "EXACT_BYTE_ACQUISITION_PASS",
            "all_or_none_pass": True,
            "transaction_committed": True,
            "attempted_at_utc": attempt_started,
            "completed_at_utc": utc_now(),
            "scientific_protocol_id": "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f",
            "source_identities": {
                "mechanism": {
                    "provider": "Mendeley Data / Digital Commons Data",
                    "dataset_id": DATASET_ID,
                    "version": VERSION,
                    "doi": DOI,
                    "file_id": file_id,
                    "basename": REQUIRED_BASENAME,
                    "provider_expected_bytes": expected_mechanism_bytes,
                    "provider_expected_sha256": expected_mechanism_sha256,
                },
                "fault": {
                    "repository": FAULT_REPOSITORY,
                    "commit": FAULT_COMMIT,
                    "path": FAULT_PATH,
                    "git_blob_sha1": observed_blob,
                },
            },
            "source_receipts": {
                "metadata_snapshot": metadata_receipt,
                "mechanism": mechanism_receipt,
                "fault": {**fault_receipt, "git_blob_sha1": observed_blob},
            },
            "committed_files": {
                REQUIRED_BASENAME: {
                    "bytes": mechanism_stage.stat().st_size,
                    "sha256": sha256_file(mechanism_stage),
                },
                FAULT_BASENAME: {
                    "bytes": fault_stage.stat().st_size,
                    "sha256": sha256_file(fault_stage),
                    "git_blob_sha1": observed_blob,
                },
                snapshot_stage.name: {
                    "bytes": snapshot_stage.stat().st_size,
                    "sha256": sha256_file(snapshot_stage),
                },
            },
            "resume_cache_used": bool(mechanism_receipt.get("resumed_from_bytes") or fault_receipt.get("resumed_from_bytes")),
            "response_query_values_recorded": False,
            "secret_values_accepted": False,
            "directional_fields_accessed": False,
            "pickle_opened": False,
            "scientific_execution_performed": False,
            "authority_ceiling": "NONE",
            "promotion": "BLOCKED",
            "canonicalization": "BLOCKED",
        }
        acquisition["receipt_id"] = content_id("h9acq", acquisition)
        write_json_atomic(staging / "ACQUISITION_RECEIPT_V0_9.json", acquisition)
        fsync_directory(staging)
        if committed.exists():
            raise RuntimeError("exact_sources appeared concurrently; refusing non-atomic merge")
        os.replace(staging, committed)
        staging = None
        fsync_directory(workspace)
        body.update(
            outcome="EXACT_BYTE_ACQUISITION_PASS",
            all_or_none_pass=True,
            idempotent_reuse=False,
            committed_receipt_id=acquisition["receipt_id"],
            mechanism_sha256=mechanism_receipt["sha256"],
            fault_sha256=fault_receipt["sha256"],
            fault_git_blob_sha1=observed_blob,
            completed_at_utc=utc_now(),
        )
        status = 0
    except Exception as exc:
        body.update(
            outcome="BLOCKED_EXACT_BYTE_ACQUISITION",
            error_type=type(exc).__name__,
            error=sanitize_text(str(exc)),
            all_or_none_pass=False,
            transaction_committed=False,
            completed_at_utc=utc_now(),
        )
        status = 10
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    body["receipt_id"] = content_id("h9acqattempt", body)
    write_json_atomic(receipts_dir / "ACQUISITION_ATTEMPT_V0_9.json", body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
