from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATASET_ID = "2np9vw5v7w"
VERSION = 2
DOI = "10.17632/2np9vw5v7w.2"
REQUIRED_BASENAME = "focmec_ca_final.pickle"
DATASET_PAGE_URL = f"https://data.mendeley.com/datasets/{DATASET_ID}/{VERSION}"
COMPARE_PAGE_URL = f"https://data.mendeley.com/datasets/compare/{DATASET_ID}"

# This UUID arrived from the predecessor acquisition work but is not trusted.
# It is admissible only if the public route returns the exact required basename
# and a catalog-sized body. Otherwise it is discarded and cannot authorize use.
UNTRUSTED_PREDECESSOR_FILE_UUIDS = (
    "51b869ad-2a13-4860-8d13-a259d0864fd9",
)

S3_BUCKET = "md-datasets-cache-zipfiles-prod"
S3_KEY = f"{DATASET_ID}-{VERSION}.zip"
S3_SEED_REGIONS = ("eu-west-1", "us-east-1", "eu-west-2", "us-west-2")

FAULT_REPOSITORY = "GEMScienceTools/gem-global-active-faults"
FAULT_COMMIT = "56816508ad92fd6846dad1163b1c8c01376a2cd1"
FAULT_PATH = "geojson/gem_active_faults_harmonized.geojson"
FAULT_URL = (
    "https://raw.githubusercontent.com/"
    f"{FAULT_REPOSITORY}/{FAULT_COMMIT}/{FAULT_PATH}"
)
EXPECTED_FAULT_BLOB_SHA1 = "fb164770b529695544fa864abe2cc9dd8aa5793d"
EXPECTED_FAULT_BYTES = 29_636_622

MIN_FOCAL_BYTES = 100_000_000
CHUNK = 8 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    size = path.stat().st_size
    h = hashlib.sha1()
    h.update(b"blob " + str(size).encode("ascii") + b"\0")
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_headers(headers: Any) -> dict[str, str]:
    return {str(k): str(v) for k, v in headers.items()}


class RedirectRecorder(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.events.append(
            {"from_url": req.full_url, "to_url": newurl, "status": int(code)}
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


REDIRECTS = RedirectRecorder()
OPENER = urllib.request.build_opener(REDIRECTS)
BASE_HEADERS = {
    "Accept-Encoding": "identity",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "KCH-KwanBlocks-Helical-Lift-v0.8"
    ),
}


def fetch_bytes(url: str, accept: str) -> tuple[bytes, dict[str, Any]]:
    start = len(REDIRECTS.events)
    req = urllib.request.Request(url, headers={**BASE_HEADERS, "Accept": accept})
    requested_at = utc_now()
    with OPENER.open(req, timeout=300) as response:
        data = response.read()
        receipt = {
            "requested_at_utc": requested_at,
            "completed_at_utc": utc_now(),
            "requested_url": url,
            "effective_url": response.geturl(),
            "status": int(response.status),
            "headers": safe_headers(response.headers),
            "redirect_chain": REDIRECTS.events[start:],
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    if receipt["status"] != 200:
        raise RuntimeError(f"unexpected HTTP status {receipt['status']} for {url}")
    return data, receipt


def download(
    url: str,
    path: Path,
    accept: str,
    *,
    timeout: int = 1200,
) -> dict[str, Any]:
    start = len(REDIRECTS.events)
    req = urllib.request.Request(url, headers={**BASE_HEADERS, "Accept": accept})
    requested_at = utc_now()
    h = hashlib.sha256()
    size = 0
    try:
        with OPENER.open(req, timeout=timeout) as response, path.open("wb") as target:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                target.write(chunk)
                h.update(chunk)
                size += len(chunk)
            receipt = {
                "requested_at_utc": requested_at,
                "completed_at_utc": utc_now(),
                "requested_url": url,
                "effective_url": response.geturl(),
                "status": int(response.status),
                "headers": safe_headers(response.headers),
                "redirect_chain": REDIRECTS.events[start:],
                "bytes": size,
                "sha256": h.hexdigest(),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(64 * 1024)
        path.unlink(missing_ok=True)
        exc.kch_receipt = {
            "requested_at_utc": requested_at,
            "completed_at_utc": utc_now(),
            "requested_url": url,
            "effective_url": exc.geturl(),
            "status": int(exc.code),
            "headers": safe_headers(exc.headers),
            "redirect_chain": REDIRECTS.events[start:],
            "error_body_utf8": body.decode("utf-8", errors="replace"),
        }
        raise
    if receipt["status"] != 200 or size == 0:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"failed nonempty download for {url}: {receipt}")
    return receipt


def extract_initial_state(page_text: str) -> dict[str, Any]:
    for marker in ("window.INITIAL_STATE = ", "window.__state = "):
        start = page_text.find(marker)
        if start < 0:
            continue
        start += len(marker)
        end = page_text.find("</script>", start)
        if end < 0:
            continue
        raw = page_text[start:end].strip()
        if "window.initialTime" in raw:
            raw = raw.split("window.initialTime", 1)[0].strip()
        if raw.endswith(";"):
            raw = raw[:-1]
        return json.loads(raw)
    return {}


def walk_files(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        filename = value.get("filename") or value.get("file_name") or value.get("name")
        file_id = value.get("id") or value.get("uuid") or value.get("file_id")
        if filename and file_id:
            rows.append(
                {"filename": str(filename), "file_id": str(file_id), "raw": value}
            )
        for child in value.values():
            rows.extend(walk_files(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(walk_files(child))
    return rows


def content_disposition_name(headers: dict[str, str]) -> str | None:
    value = next(
        (item for key, item in headers.items() if key.lower() == "content-disposition"),
        "",
    )
    if not value:
        return None
    match = re.search(r"filename\*=UTF-8''([^;]+)", value, re.I)
    if match:
        return urllib.parse.unquote(match.group(1)).strip('"')
    match = re.search(r"filename=\"?([^\";]+)", value, re.I)
    return match.group(1).strip() if match else None


def s3_urls_from_error(exc: urllib.error.HTTPError) -> list[str]:
    urls: list[str] = []
    headers = safe_headers(exc.headers)
    region = next(
        (v for k, v in headers.items() if k.lower() == "x-amz-bucket-region"),
        None,
    )
    if region:
        urls.append(f"https://{S3_BUCKET}.s3.{region}.amazonaws.com/{S3_KEY}")
    receipt = getattr(exc, "kch_receipt", {})
    body = receipt.get("error_body_utf8", "")
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        root = None
    if root is not None:
        endpoint = root.findtext("Endpoint")
        if endpoint:
            urls.append(f"https://{endpoint.strip('/')}/{S3_KEY}")
        region_text = root.findtext("Region")
        if region_text:
            urls.append(
                f"https://{S3_BUCKET}.s3.{region_text}.amazonaws.com/{S3_KEY}"
            )
    return urls


def acquire_from_direct_candidates(
    mechanism_path: Path,
    page_candidates: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None] | None:
    candidates: list[tuple[str, dict[str, Any] | None, str]] = []
    for row in page_candidates:
        candidates.append((row["file_id"], row, "OFFICIAL_PAGE_STATE_FILE_UUID"))
    for file_id in UNTRUSTED_PREDECESSOR_FILE_UUIDS:
        if file_id not in {item[0] for item in candidates}:
            candidates.append((file_id, None, "UNTRUSTED_PREDECESSOR_UUID_VALIDATED_EX_POST"))

    for file_id, metadata, mode in candidates:
        url = (
            f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/"
            f"files/{file_id}/file_downloaded"
        )
        try:
            receipt = download(url, mechanism_path, "application/octet-stream")
        except urllib.error.HTTPError as exc:
            attempts.append(
                {
                    "mode": mode,
                    "file_id": file_id,
                    "outcome": "HTTP_ERROR",
                    "receipt": getattr(exc, "kch_receipt", {"status": exc.code}),
                }
            )
            continue
        except Exception as exc:
            attempts.append(
                {
                    "mode": mode,
                    "file_id": file_id,
                    "outcome": "ERROR",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            mechanism_path.unlink(missing_ok=True)
            continue

        disposition = content_disposition_name(receipt["headers"])
        size = mechanism_path.stat().st_size
        name_ok = disposition is None or Path(disposition).name == REQUIRED_BASENAME
        size_ok = size >= MIN_FOCAL_BYTES
        attempts.append(
            {
                "mode": mode,
                "file_id": file_id,
                "outcome": "BODY_OBSERVED",
                "content_disposition_name": disposition,
                "name_ok": name_ok,
                "size_ok": size_ok,
                "bytes": size,
                "sha256": receipt["sha256"],
            }
        )
        if not (name_ok and size_ok):
            mechanism_path.unlink(missing_ok=True)
            continue

        if metadata is not None:
            details = metadata["raw"].get("content_details", {})
            declared_size = details.get("size") or metadata["raw"].get("size")
            if declared_size is not None and size != int(declared_size):
                mechanism_path.unlink(missing_ok=True)
                attempts[-1]["outcome"] = "DECLARED_SIZE_MISMATCH"
                continue
        return receipt, metadata
    return None


def acquire_from_official_zip(
    out: Path,
    mechanism_path: Path,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    archive_path = out / S3_KEY
    queue = [
        f"https://{S3_BUCKET}.s3.{region}.amazonaws.com/{S3_KEY}"
        for region in S3_SEED_REGIONS
    ]
    queue.append(f"https://{S3_BUCKET}.s3.amazonaws.com/{S3_KEY}")
    observed: set[str] = set()
    archive_receipt: dict[str, Any] | None = None
    chosen_url: str | None = None

    while queue:
        url = queue.pop(0)
        if url in observed:
            continue
        observed.add(url)
        try:
            archive_receipt = download(url, archive_path, "application/zip")
        except urllib.error.HTTPError as exc:
            receipt = getattr(exc, "kch_receipt", {"status": exc.code})
            attempts.append(
                {"mode": "OFFICIAL_MENDELEY_CACHE_ZIP", "url": url, "receipt": receipt}
            )
            queue.extend(candidate for candidate in s3_urls_from_error(exc) if candidate not in observed)
            continue
        except Exception as exc:
            attempts.append(
                {
                    "mode": "OFFICIAL_MENDELEY_CACHE_ZIP",
                    "url": url,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        chosen_url = url
        break

    if archive_receipt is None or chosen_url is None:
        raise RuntimeError("all official Mendeley cache endpoints failed")
    if not zipfile.is_zipfile(archive_path):
        raise RuntimeError("official Mendeley cache body is not a ZIP")

    with zipfile.ZipFile(archive_path) as zf:
        members = [
            info
            for info in zf.infolist()
            if not info.is_dir() and Path(info.filename).name == REQUIRED_BASENAME
        ]
        if len(members) != 1:
            raise RuntimeError(
                f"expected one exact focal member in official ZIP; observed {len(members)}"
            )
        member = members[0]
        if member.flag_bits & 0x1:
            raise RuntimeError("required ZIP member is encrypted")
        with zf.open(member, "r") as source, mechanism_path.open("wb") as target:
            shutil.copyfileobj(source, target, length=CHUNK)
        if mechanism_path.stat().st_size != member.file_size:
            raise RuntimeError("extracted focal member size mismatch")

    archive_sha256 = archive_receipt["sha256"]
    archive_bytes = archive_receipt["bytes"]
    archive_path.unlink()
    if mechanism_path.stat().st_size < MIN_FOCAL_BYTES:
        raise RuntimeError(
            f"focal catalog unexpectedly small: {mechanism_path.stat().st_size} bytes"
        )
    return {
        "source_archive_url": chosen_url,
        "archive_sha256": archive_sha256,
        "archive_bytes": archive_bytes,
        "member_name": member.filename,
        "member_crc32": f"{member.CRC:08x}",
        "bytes": mechanism_path.stat().st_size,
        "sha256": sha256_path(mechanism_path),
    }


def main() -> int:
    out = Path(os.environ["RUNNER_TEMP"]) / "helical-v08-exact-source"
    out.mkdir(parents=True, exist_ok=True)
    attempts: list[dict[str, Any]] = []
    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_8_EXACT_SOURCE_ACQUISITION",
        "dataset_id": DATASET_ID,
        "dataset_version": VERSION,
        "dataset_doi": DOI,
        "required_basename": REQUIRED_BASENAME,
        "fault_repository": FAULT_REPOSITORY,
        "fault_commit": FAULT_COMMIT,
        "fault_path": FAULT_PATH,
        "workflow_repository": os.environ.get("GITHUB_REPOSITORY"),
        "workflow_ref": os.environ.get("GITHUB_REF"),
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "started_at_utc": utc_now(),
        "network_plane": "GITHUB_ACTIONS_PUBLIC_EGRESS",
        "credentials_used": False,
        "deserialization_performed": False,
        "angle_fields_accessed": False,
        "scientific_execution_performed": False,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
    }

    try:
        page_bytes, page_receipt = fetch_bytes(DATASET_PAGE_URL, "text/html")
        page_text = page_bytes.decode("utf-8", errors="strict")
        required_markers = (DOI, "Version 2", REQUIRED_BASENAME)
        absent = [marker for marker in required_markers if marker not in page_text]
        if absent:
            raise RuntimeError(f"dataset page missing frozen markers: {absent}")
        (out / "mendeley_dataset_v2_record.html").write_bytes(page_bytes)

        state = extract_initial_state(page_text)
        (out / "mendeley_dataset_v2_state.json").write_text(
            json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
        page_candidates = [
            row
            for row in walk_files(state)
            if Path(row["filename"]).name == REQUIRED_BASENAME
        ]
        page_candidates = list(
            {(row["filename"], row["file_id"]): row for row in page_candidates}.values()
        )

        mechanism_path = out / REQUIRED_BASENAME
        direct = acquire_from_direct_candidates(mechanism_path, page_candidates, attempts)
        if direct is not None:
            mechanism_receipt, selected_file = direct
            acquisition_mode = (
                "OFFICIAL_DATASET_PAGE_FILE_UUID"
                if selected_file is not None
                else "PREDECESSOR_UUID_REVALIDATED_AGAINST_PUBLIC_BODY"
            )
        else:
            mechanism_receipt = acquire_from_official_zip(out, mechanism_path, attempts)
            selected_file = None
            acquisition_mode = "OFFICIAL_MENDELEY_CACHE_ZIP_EXACT_MEMBER"

        if mechanism_path.stat().st_size < MIN_FOCAL_BYTES:
            raise RuntimeError("materialized focal catalog failed minimum-size gate")

        fault_target = out / "gem_active_faults_harmonized.geojson"
        fault_receipt = download(
            FAULT_URL, fault_target, "application/geo+json,application/json"
        )
        if fault_target.stat().st_size != EXPECTED_FAULT_BYTES:
            raise RuntimeError(
                f"fault byte-size mismatch: {fault_target.stat().st_size} "
                f"!= {EXPECTED_FAULT_BYTES}"
            )
        observed_blob = git_blob_sha1(fault_target)
        if observed_blob != EXPECTED_FAULT_BLOB_SHA1:
            raise RuntimeError(
                f"fault Git blob mismatch: {observed_blob} != {EXPECTED_FAULT_BLOB_SHA1}"
            )
        json.loads(fault_target.read_text("utf-8"))

        body.update(
            outcome="EXACT_BYTE_ACQUISITION_PASS",
            all_or_none_pass=True,
            acquisition_mode=acquisition_mode,
            dataset_page_receipt=page_receipt,
            page_state_file_candidate_count=len(page_candidates),
            selected_mendeley_file=(
                {
                    "filename": selected_file["filename"],
                    "file_id": selected_file["file_id"],
                }
                if selected_file is not None
                else None
            ),
            acquisition_attempts=attempts,
            mechanism_receipt=mechanism_receipt,
            fault_receipt={
                **fault_receipt,
                "git_blob_sha1": observed_blob,
                "expected_git_blob_sha1": EXPECTED_FAULT_BLOB_SHA1,
            },
            completed_at_utc=utc_now(),
        )
        status = 0
    except Exception as exc:
        body.update(
            outcome="BLOCKED_EXACT_BYTE_ACQUISITION",
            all_or_none_pass=False,
            acquisition_attempts=attempts,
            error_type=type(exc).__name__,
            error=str(exc),
            completed_at_utc=utc_now(),
        )
        status = 3

    content = dict(body)
    body["receipt_id"] = "h8acqremote:" + hashlib.sha256(canonical(content)).hexdigest()
    (out / "ACQUISITION_RECEIPT_V0_8_REMOTE.json").write_text(
        json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )

    sums: list[str] = []
    for path in sorted(out.iterdir(), key=lambda p: p.name):
        if path.is_file():
            sums.append(f"{sha256_path(path)}  {path.name}")
    (out / "SOURCE_SHA256SUMS.txt").write_text(
        "\n".join(sums) + "\n", encoding="utf-8"
    )
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
