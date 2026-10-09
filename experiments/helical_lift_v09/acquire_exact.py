from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

DATASET_ID = "2np9vw5v7w"
VERSION = 2
DOI = "10.17632/2np9vw5v7w.2"
REQUIRED_BASENAME = "focmec_ca_final.pickle"
DATASET_PAGE_URL = f"https://data.mendeley.com/datasets/{DATASET_ID}/{VERSION}"
COMPARE_PAGE_URL = f"https://data.mendeley.com/datasets/compare/{DATASET_ID}"
AUTHENTICATED_SNAPSHOT_URL = f"https://api.data.mendeley.com/datasets/{DATASET_ID}?version={VERSION}"
FAULT_REPOSITORY = "GEMScienceTools/gem-global-active-faults"
FAULT_COMMIT = "56816508ad92fd6846dad1163b1c8c01376a2cd1"
FAULT_PATH = "geojson/gem_active_faults_harmonized.geojson"
FAULT_BLOB_SHA1 = "fb164770b529695544fa864abe2cc9dd8aa5793d"
FAULT_URL = f"https://raw.githubusercontent.com/{FAULT_REPOSITORY}/{FAULT_COMMIT}/{FAULT_PATH}"
USER_AGENT = "Mozilla/5.0 KCH-KwanBlocks-Helical-Lift/0.9 exact-byte blind acquisition"
CHUNK = 8 * 1024 * 1024
MIN_FOCMEC_BYTES = 400_000_000
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}")
SAFE_RESPONSE_HEADERS = {
    "content-type", "content-length", "content-disposition", "etag",
    "last-modified", "accept-ranges", "date", "x-amz-version-id",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


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


def request_bytes(url: str, *, accept: str, timeout: int = 300) -> tuple[bytes, dict[str, Any]]:
    req = urllib.request.Request(url, headers={"Accept": accept, "Accept-Encoding": "identity", "User-Agent": USER_AGENT})
    started = now_utc()
    with urllib.request.urlopen(req, timeout=timeout) as response:
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
    return raw, receipt


def stream_download(url: str, destination: Path, *, accept: str, timeout: int = 1800) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    partial.unlink(missing_ok=True)
    req = urllib.request.Request(url, headers={"Accept": accept, "Accept-Encoding": "identity", "User-Agent": USER_AGENT})
    h = hashlib.sha256()
    size = 0
    started = now_utc()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response, partial.open("wb") as handle:
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


def normalized_html(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    text = html.unescape(text)
    text = text.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
    return text


def discover_public_file_routes(page: str) -> tuple[list[str], dict[str, Any]]:
    routes: list[str] = []
    contexts: list[dict[str, Any]] = []
    direct_pattern = re.compile(
        rf"https://data\.mendeley\.com/public-files/datasets/{re.escape(DATASET_ID)}/files/({UUID_RE.pattern})/file_downloaded(?:\?[^\"'<>\\s]*)?",
        re.IGNORECASE,
    )
    for match in direct_pattern.finditer(page):
        routes.append(match.group(0))
    for occurrence in re.finditer(re.escape(REQUIRED_BASENAME), page, flags=re.IGNORECASE):
        start = max(0, occurrence.start() - 12000)
        end = min(len(page), occurrence.end() + 12000)
        window = page[start:end]
        ids = sorted(set(UUID_RE.findall(window)))
        contexts.append({
            "window_sha256": hashlib.sha256(window.encode("utf-8", errors="replace")).hexdigest(),
            "uuid_candidates": ids,
            "window_bytes": len(window.encode("utf-8", errors="replace")),
        })
        for file_id in ids:
            routes.append(f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/files/{file_id}/file_downloaded")
    fragment_pattern = re.compile(rf"/public-files/datasets/{re.escape(DATASET_ID)}/files/({UUID_RE.pattern})/file_downloaded", re.IGNORECASE)
    for match in fragment_pattern.finditer(page):
        routes.append(f"https://data.mendeley.com{match.group(0)}")
    routes = list(dict.fromkeys(routes))
    return routes, {
        "required_filename_occurrences": len(contexts),
        "candidate_route_count": len(routes),
        "contexts": contexts,
    }


def validate_mechanism_body(path: Path) -> None:
    if path.stat().st_size < MIN_FOCMEC_BYTES:
        raise RuntimeError(f"candidate body is too small for the published 504 MB focal catalog: {path.stat().st_size}")
    with path.open("rb") as handle:
        prefix = handle.read(64).lstrip().lower()
    if prefix.startswith(b"<html") or prefix.startswith(b"<!doctype"):
        raise RuntimeError("mechanism response is HTML, not the required entity body")
    if prefix.startswith(b"pk\x03\x04"):
        raise RuntimeError("mechanism candidate is a ZIP body, not the required pickle member")


def extract_required_zip_member(archive: Path, destination: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"official ZIP CRC failure at {bad}")
        matches = [info for info in zf.infolist() if PurePosixPath(info.filename).name == REQUIRED_BASENAME and not info.is_dir()]
        if len(matches) != 1:
            raise RuntimeError(f"official ZIP must contain exactly one {REQUIRED_BASENAME}; observed {len(matches)}")
        info = matches[0]
        if info.flag_bits & 0x1:
            raise RuntimeError("required ZIP member is encrypted")
        if info.file_size < MIN_FOCMEC_BYTES:
            raise RuntimeError(f"required ZIP member is too small: {info.file_size}")
        partial = destination.with_suffix(destination.suffix + ".partial")
        partial.unlink(missing_ok=True)
        h = hashlib.sha256()
        size = 0
        try:
            with zf.open(info, "r") as source, partial.open("wb") as target:
                while True:
                    block = source.read(CHUNK)
                    if not block:
                        break
                    target.write(block)
                    h.update(block)
                    size += len(block)
                target.flush()
                os.fsync(target.fileno())
            if size != info.file_size:
                raise RuntimeError(f"ZIP member length mismatch: {size} != {info.file_size}")
            partial.replace(destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        return {
            "member_name": info.filename,
            "member_bytes": size,
            "member_sha256": h.hexdigest(),
            "member_crc32": f"{info.CRC:08x}",
            "member_compressed_bytes": info.compress_size,
            "member_compression_type": info.compress_type,
        }


def acquire_mechanism(data_dir: Path, receipts_dir: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    mechanism_path = data_dir / REQUIRED_BASENAME
    discovery: dict[str, Any] = {"authenticated_api_required": True, "attempts": []}
    public_routes: list[str] = []

    for label, url in (("dataset_page_v2", DATASET_PAGE_URL), ("comparison_page", COMPARE_PAGE_URL)):
        try:
            raw, receipt = request_bytes(url, accept="text/html,application/xhtml+xml")
            page = normalized_html(raw)
            routes, parsed = discover_public_file_routes(page)
            public_routes.extend(routes)
            discovery[label] = {"receipt": receipt, "parsed": parsed}
            (receipts_dir / f"{label.upper()}.html").write_bytes(raw)
        except Exception as exc:
            discovery[label] = {"error_type": type(exc).__name__, "error": str(exc)}

    try:
        raw, receipt = request_bytes(AUTHENTICATED_SNAPSHOT_URL, accept="application/vnd.mendeley-public-dataset.1+json,application/json")
        discovery["authenticated_snapshot"] = {"receipt": receipt}
        (receipts_dir / "AUTHENTICATED_SNAPSHOT_RESPONSE.json").write_bytes(raw)
        snapshot = json.loads(raw.decode("utf-8"))
        for row in snapshot.get("files", []) if isinstance(snapshot, dict) else []:
            if Path(str(row.get("filename", ""))).name != REQUIRED_BASENAME:
                continue
            file_id = row.get("id")
            content = row.get("content_details") or {}
            for candidate in (content.get("download_url"), row.get("download_url")):
                if isinstance(candidate, str):
                    public_routes.append(candidate)
            if file_id:
                public_routes.append(f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/files/{file_id}/file_downloaded")
    except Exception as exc:
        discovery["authenticated_snapshot"] = {"error_type": type(exc).__name__, "error": str(exc)}

    public_routes = list(dict.fromkeys(public_routes))
    direct_errors: list[dict[str, Any]] = []
    for route in public_routes:
        parsed = urllib.parse.urlsplit(route)
        if parsed.scheme != "https" or parsed.hostname not in {"data.mendeley.com", "api.data.mendeley.com"}:
            direct_errors.append({"route": safe_url_receipt(route), "error": "route host not allow-listed"})
            continue
        try:
            receipt = stream_download(route, mechanism_path, accept="application/octet-stream")
            validate_mechanism_body(mechanism_path)
            receipt.update({"transport": "PUBLIC_FILE_ROUTE", "file_sha256": sha256_file(mechanism_path)})
            discovery["direct_route_failures_before_success"] = direct_errors
            discovery["selected_transport"] = "PUBLIC_FILE_ROUTE"
            return mechanism_path, receipt, discovery
        except Exception as exc:
            mechanism_path.unlink(missing_ok=True)
            direct_errors.append({"route": safe_url_receipt(route), "error_type": type(exc).__name__, "error": str(exc)})

    zip_routes = [
        f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/zip/file_downloaded?version={VERSION}",
        f"https://api.data.mendeley.com/datasets/{DATASET_ID}/zip/file_downloaded?version={VERSION}",
    ]
    zip_errors: list[dict[str, Any]] = []
    archive = data_dir / f"{DATASET_ID}_v{VERSION}.zip"
    for route in zip_routes:
        try:
            zip_receipt = stream_download(route, archive, accept="application/zip,application/octet-stream", timeout=3600)
            member_receipt = extract_required_zip_member(archive, mechanism_path)
            validate_mechanism_body(mechanism_path)
            receipt = {
                "transport": "OFFICIAL_DATASET_ZIP_MEMBER",
                "requested": zip_receipt["requested"],
                "effective": zip_receipt["effective"],
                "status": zip_receipt["status"],
                "headers": zip_receipt["headers"],
                "started_at_utc": zip_receipt["started_at_utc"],
                "finished_at_utc": now_utc(),
                "official_zip_bytes": zip_receipt["bytes"],
                "official_zip_sha256": zip_receipt["sha256"],
                "bytes": member_receipt["member_bytes"],
                "sha256": member_receipt["member_sha256"],
                "zip_member": member_receipt,
            }
            archive.unlink(missing_ok=True)
            discovery["direct_route_failures"] = direct_errors
            discovery["zip_route_failures_before_success"] = zip_errors
            discovery["selected_transport"] = "OFFICIAL_DATASET_ZIP_MEMBER"
            return mechanism_path, receipt, discovery
        except Exception as exc:
            archive.unlink(missing_ok=True)
            mechanism_path.unlink(missing_ok=True)
            zip_errors.append({"route": safe_url_receipt(route), "error_type": type(exc).__name__, "error": str(exc)})

    discovery["direct_route_failures"] = direct_errors
    discovery["zip_route_failures"] = zip_errors
    raise RuntimeError("no authoritative public Mendeley transport produced the required focal catalog")


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
        "authorization_headers_sent": False,
        "signed_redirect_urls_persisted": False,
    }
    try:
        mechanism_path, mechanism_receipt, discovery = acquire_mechanism(data_dir, receipts_dir)
        fault_path = data_dir / "gem_active_faults_harmonized.geojson"
        fault_receipt = stream_download(FAULT_URL, fault_path, accept="application/geo+json,application/json")
        if fault_path.stat().st_size == 0:
            raise RuntimeError("empty fault network body")
        json.loads(fault_path.read_text(encoding="utf-8"))
        observed_blob = git_blob_sha1(fault_path)
        if observed_blob != FAULT_BLOB_SHA1:
            raise RuntimeError(f"fault Git blob mismatch: {observed_blob}")
        if mechanism_receipt["sha256"] != sha256_file(mechanism_path):
            raise RuntimeError("mechanism hash changed after acquisition")
        body.update({
            "outcome": "EXACT_BYTE_ACQUISITION_PASS",
            "all_or_none_pass": True,
            "public_discovery": discovery,
            "selected_file": {
                "basename": REQUIRED_BASENAME,
                "minimum_expected_bytes": MIN_FOCMEC_BYTES,
                "observed_bytes": mechanism_path.stat().st_size,
            },
            "mechanism_receipt": mechanism_receipt,
            "fault_receipt": {**fault_receipt, "git_blob_sha1": observed_blob},
            "mechanism_relative_path": str(mechanism_path.relative_to(out)),
            "fault_relative_path": str(fault_path.relative_to(out)),
        })
        status = 0
    except Exception as exc:
        quarantine = out / "quarantine"
        quarantine.mkdir(exist_ok=True)
        for candidate in (
            data_dir / REQUIRED_BASENAME,
            data_dir / "gem_active_faults_harmonized.geojson",
            data_dir / f"{DATASET_ID}_v{VERSION}.zip",
        ):
            if candidate.exists():
                shutil.move(str(candidate), str(quarantine / candidate.name))
        body.update({
            "outcome": "BLOCKED_EXACT_BYTE_ACQUISITION",
            "all_or_none_pass": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        discovery_path = receipts_dir / "PUBLIC_DISCOVERY_RECEIPT_V0_9.json"
        if 'discovery' in locals():
            write_json(discovery_path, discovery)
        status = 3
    body["receipt_id"] = "h9acq:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(receipts_dir / "ACQUISITION_RECEIPT_V0_9.json", body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
