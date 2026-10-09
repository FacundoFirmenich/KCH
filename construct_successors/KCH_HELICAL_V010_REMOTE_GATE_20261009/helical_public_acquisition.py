from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
import urllib.parse
import urllib.request

import helical_remote_gate as gate

PUBLIC_DATASET_URL = (
    f"https://data.mendeley.com/public-api/datasets/{gate.DATASET_ID}"
    f"?version={gate.DATASET_VERSION}"
)
PUBLIC_FILE_LIST_URL = (
    f"https://data.mendeley.com/public-api/datasets/{gate.DATASET_ID}/files"
    f"?folder_id=root&version={gate.DATASET_VERSION}&%24start=0&%24limit=1000"
)
EXPECTED_FILE_ID = "c5fd3e24-24ef-4186-8794-c681411cdcc3"
EXPECTED_CONTENT_ID = "a0e8bb96-722c-4f20-91c0-f30a148e5012"
EXPECTED_BYTES = 528_904_117
EXPECTED_SHA256 = "cc13d9e4335bb20579d224c52ea2936d3251719c381c830c23b2abfd0a1eedeb"
EXPECTED_DOWNLOAD_URL = (
    f"https://data.mendeley.com/public-files/datasets/{gate.DATASET_ID}/files/"
    f"{EXPECTED_FILE_ID}/file_downloaded"
)
_ORIGINAL_STREAM_DOWNLOAD = gate.stream_download
_PUBLIC_DOWNLOAD_URL: str | None = None
_PUBLIC_IDENTITY: dict[str, Any] | None = None


def safe_url(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "path": parsed.path,
        "query_keys": sorted(urllib.parse.parse_qs(parsed.query, keep_blank_values=True)),
        "query_values_recorded": False,
    }


def fetch_json(url: str, timeout: int, label: str) -> tuple[Any, dict[str, Any], bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "KCH-Helical-Lift/0.10 exact-public-identity; no credentials",
        },
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024:
            raise RuntimeError(f"{label} response exceeds 32 MiB")
        receipt = {
            "label": label,
            "requested": safe_url(url),
            "effective": safe_url(response.geturl()),
            "status": int(response.status),
            "content_type": response.headers.get("Content-Type"),
            "content_length_header": response.headers.get("Content-Length"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "elapsed_seconds": time.monotonic() - started,
            "authenticated_api_used": False,
        }
    return json.loads(raw.decode("utf-8")), receipt, raw


def validate_dataset_metadata(metadata: Any) -> None:
    if not isinstance(metadata, dict):
        raise RuntimeError("public dataset metadata is not an object")
    encoded = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    required = [
        gate.DATASET_ID,
        gate.MECHANISM_BASENAME,
        "Statewide California focal mechanism catalog and stress model (1981-2021)",
    ]
    missing = [value for value in required if value not in encoded]
    if missing:
        raise RuntimeError(f"public dataset metadata identity mismatch; missing={missing}")
    version_values: set[int] = set()
    for key in ("version", "version_number", "dataset_version"):
        value = metadata.get(key)
        try:
            version_values.add(int(value))
        except Exception:
            pass
    if version_values and gate.DATASET_VERSION not in version_values:
        raise RuntimeError(f"public dataset version mismatch: {sorted(version_values)}")


def exact_file_row(file_list: Any) -> dict[str, Any]:
    rows = file_list if isinstance(file_list, list) else []
    matches = [row for row in rows if isinstance(row, dict) and row.get("filename") == gate.MECHANISM_BASENAME]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one required file in public file list; observed={len(matches)}")
    row = matches[0]
    details = row.get("content_details")
    if not isinstance(details, dict):
        raise RuntimeError("required file lacks content_details")
    observed = {
        "file_id": str(row.get("id")),
        "content_id": str(details.get("id")),
        "bytes": int(row.get("size")),
        "content_bytes": int(details.get("size")),
        "sha256": str(details.get("sha256_hash", "")).lower(),
        "download_url": str(details.get("download_url")),
        "status": str(row.get("status")),
        "content_type": str(details.get("content_type")),
    }
    expected = {
        "file_id": EXPECTED_FILE_ID,
        "content_id": EXPECTED_CONTENT_ID,
        "bytes": EXPECTED_BYTES,
        "content_bytes": EXPECTED_BYTES,
        "sha256": EXPECTED_SHA256,
        "download_url": EXPECTED_DOWNLOAD_URL,
        "status": "COMPLETED",
        "content_type": "application/octet-stream",
    }
    if observed != expected:
        raise RuntimeError(f"public file identity drift: observed={observed!r}")
    return row


def public_request_json(url: str, timeout: int) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    global _PUBLIC_DOWNLOAD_URL, _PUBLIC_IDENTITY
    if url != gate.SNAPSHOT_URL:
        raise RuntimeError(f"unexpected authenticated metadata endpoint request: {safe_url(url)}")
    metadata, metadata_receipt, _ = fetch_json(PUBLIC_DATASET_URL, timeout, "PUBLIC_DATASET_METADATA")
    file_list, file_list_receipt, _ = fetch_json(PUBLIC_FILE_LIST_URL, timeout, "PUBLIC_ROOT_FILE_LIST")
    validate_dataset_metadata(metadata)
    row = exact_file_row(file_list)
    details = row["content_details"]
    _PUBLIC_DOWNLOAD_URL = details["download_url"]
    _PUBLIC_IDENTITY = {
        "file_id": row["id"],
        "content_id": details["id"],
        "filename": row["filename"],
        "bytes": int(row["size"]),
        "sha256": details["sha256_hash"].lower(),
        "download_url": safe_url(_PUBLIC_DOWNLOAD_URL),
        "status": row["status"],
    }
    snapshot = {
        "id": gate.DATASET_ID,
        "version": gate.DATASET_VERSION,
        "doi": gate.DOI,
        "title": "Statewide California focal mechanism catalog and stress model (1981-2021)",
        "public_dataset_metadata_receipt": metadata_receipt,
        "public_file_list_receipt": file_list_receipt,
        "files": [row],
        "exact_public_identity": _PUBLIC_IDENTITY,
        "authenticated_api_used": False,
    }
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    receipt = {
        "adapter": "MENDELEY_PUBLIC_API_EXACT_IDENTITY",
        "dataset_id": gate.DATASET_ID,
        "dataset_version": gate.DATASET_VERSION,
        "doi": gate.DOI,
        "required_file": gate.MECHANISM_BASENAME,
        "metadata": metadata_receipt,
        "file_list": file_list_receipt,
        "exact_public_identity": _PUBLIC_IDENTITY,
        "synthetic_snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "authenticated_api_used": False,
        "credentials_supplied": False,
    }
    return snapshot, receipt, raw


def public_stream_download(url: str, output: Path, timeout: int, expected_bytes: int | None = None) -> dict[str, Any]:
    if output.name != gate.MECHANISM_BASENAME:
        return _ORIGINAL_STREAM_DOWNLOAD(url, output, timeout, expected_bytes)
    if _PUBLIC_DOWNLOAD_URL is None or _PUBLIC_IDENTITY is None:
        raise RuntimeError("exact public file identity was not resolved before mechanism acquisition")
    if expected_bytes != EXPECTED_BYTES:
        raise RuntimeError(f"main runner propagated unexpected byte count: {expected_bytes!r}")
    request = urllib.request.Request(
        _PUBLIC_DOWNLOAD_URL,
        headers={
            "Accept": "application/octet-stream,*/*",
            "Accept-Encoding": "identity",
            "Referer": PUBLIC_DATASET_URL,
            "User-Agent": "KCH-Helical-Lift/0.10 exact-public-file; no credentials",
        },
    )
    started = time.monotonic()
    digest = hashlib.sha256()
    total = 0
    tmp = output.with_suffix(output.suffix + ".part")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response, tmp.open("wb") as handle:
        content_type = response.headers.get("Content-Type")
        while True:
            block = response.read(8 * 1024 * 1024)
            if not block:
                break
            handle.write(block)
            digest.update(block)
            total += len(block)
        handle.flush()
        os.fsync(handle.fileno())
        effective_url = response.geturl()
        status = int(response.status)
        headers = {
            "content_type": content_type,
            "content_length_header": response.headers.get("Content-Length"),
            "content_disposition": response.headers.get("Content-Disposition"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
        }
    observed_sha = digest.hexdigest()
    if status not in {200, 206}:
        raise RuntimeError(f"public file route returned HTTP {status}")
    if total != EXPECTED_BYTES:
        raise RuntimeError(f"mechanism byte count mismatch: {total} != {EXPECTED_BYTES}")
    if observed_sha != EXPECTED_SHA256:
        raise RuntimeError(f"mechanism SHA-256 mismatch: {observed_sha}")
    if content_type and "text/html" in content_type.lower():
        raise RuntimeError("public file route returned HTML rather than the pickle payload")
    with tmp.open("rb") as handle:
        first = handle.read(2)
    if len(first) < 2 or first[0] != 0x80:
        raise RuntimeError(f"mechanism payload lacks a binary pickle protocol header: {first!r}")
    os.replace(tmp, output)
    return {
        "adapter": "MENDELEY_PUBLIC_FILE_EXACT_IDENTITY",
        "requested": safe_url(_PUBLIC_DOWNLOAD_URL),
        "effective": safe_url(effective_url),
        "status": status,
        **headers,
        "bytes": total,
        "sha256": observed_sha,
        "elapsed_seconds": time.monotonic() - started,
        "dataset_id": gate.DATASET_ID,
        "dataset_version": gate.DATASET_VERSION,
        "doi": gate.DOI,
        "required_file": gate.MECHANISM_BASENAME,
        "file_id": EXPECTED_FILE_ID,
        "content_id": EXPECTED_CONTENT_ID,
        "provider_identity_match": True,
        "authenticated_api_used": False,
        "credentials_supplied": False,
    }


gate.request_json = public_request_json
gate.stream_download = public_stream_download

if __name__ == "__main__":
    raise SystemExit(gate.main())
