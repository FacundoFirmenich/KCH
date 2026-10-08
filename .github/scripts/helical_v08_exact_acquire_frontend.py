from __future__ import annotations

import hashlib
import http.cookiejar
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATASET_ID = "2np9vw5v7w"
VERSION = 2
DOI = "10.17632/2np9vw5v7w.2"
REQUIRED_BASENAME = "focmec_ca_final.pickle"
ORIGIN = "https://data.mendeley.com"
PAGE_URL = f"{ORIGIN}/datasets/{DATASET_ID}/{VERSION}"
FILES_URL = (
    f"{ORIGIN}/public-api/datasets/{DATASET_ID}/files"
    f"?folder_id=root&version={VERSION}&$start=0&$limit=1000"
)
PUBLIC_DATASET_ACCEPT = "application/vnd.mendeley-public-dataset.1+json"

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
OUT = Path(os.environ["RUNNER_TEMP"]) / "helical-v08-exact-source"
OUT.mkdir(parents=True, exist_ok=True)


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
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    size = path.stat().st_size
    h = hashlib.sha1()
    h.update(b"blob " + str(size).encode("ascii") + b"\0")
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK), b""):
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


class PublicSession:
    def __init__(self) -> None:
        self.redirects = RedirectRecorder()
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            self.redirects,
            urllib.request.HTTPCookieProcessor(self.cookies),
        )
        self.base_headers = {
            "Accept-Encoding": "identity",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "KCH-KwanBlocks-Helical-Lift-v0.8-exact"
            ),
            "Referer": PAGE_URL,
        }

    def fetch(self, url: str, accept: str) -> tuple[bytes, dict[str, Any]]:
        start = len(self.redirects.events)
        requested_at = utc_now()
        request = urllib.request.Request(
            url,
            headers={**self.base_headers, "Accept": accept},
        )
        try:
            with self.opener.open(request, timeout=300) as response:
                body = response.read()
                receipt = {
                    "requested_at_utc": requested_at,
                    "completed_at_utc": utc_now(),
                    "requested_url": url,
                    "effective_url": response.geturl(),
                    "status": int(response.status),
                    "headers": safe_headers(response.headers),
                    "redirect_chain": self.redirects.events[start:],
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
        except urllib.error.HTTPError as exc:
            body = exc.read(2 * 1024 * 1024)
            exc.kch_receipt = {
                "requested_at_utc": requested_at,
                "completed_at_utc": utc_now(),
                "requested_url": url,
                "effective_url": exc.geturl(),
                "status": int(exc.code),
                "headers": safe_headers(exc.headers),
                "redirect_chain": self.redirects.events[start:],
                "error_body_utf8": body.decode("utf-8", errors="replace"),
            }
            raise
        if receipt["status"] != 200:
            raise RuntimeError(f"unexpected status {receipt['status']} for {url}")
        return body, receipt

    def download(self, url: str, target: Path, accept: str) -> dict[str, Any]:
        start = len(self.redirects.events)
        requested_at = utc_now()
        request = urllib.request.Request(
            url,
            headers={**self.base_headers, "Accept": accept},
        )
        h = hashlib.sha256()
        size = 0
        try:
            with self.opener.open(request, timeout=1800) as response, target.open("wb") as sink:
                while True:
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    sink.write(chunk)
                    h.update(chunk)
                    size += len(chunk)
                receipt = {
                    "requested_at_utc": requested_at,
                    "completed_at_utc": utc_now(),
                    "requested_url": url,
                    "effective_url": response.geturl(),
                    "status": int(response.status),
                    "headers": safe_headers(response.headers),
                    "redirect_chain": self.redirects.events[start:],
                    "bytes": size,
                    "sha256": h.hexdigest(),
                }
        except urllib.error.HTTPError as exc:
            body = exc.read(2 * 1024 * 1024)
            target.unlink(missing_ok=True)
            exc.kch_receipt = {
                "requested_at_utc": requested_at,
                "completed_at_utc": utc_now(),
                "requested_url": url,
                "effective_url": exc.geturl(),
                "status": int(exc.code),
                "headers": safe_headers(exc.headers),
                "redirect_chain": self.redirects.events[start:],
                "error_body_utf8": body.decode("utf-8", errors="replace"),
            }
            raise
        if receipt["status"] != 200 or size == 0:
            target.unlink(missing_ok=True)
            raise RuntimeError(f"empty or invalid download for {url}: {receipt}")
        return receipt


def walk_files(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        name = value.get("filename") or value.get("file_name") or value.get("name")
        file_id = value.get("id") or value.get("file_id") or value.get("uuid")
        if name and file_id:
            rows.append({"filename": str(name), "file_id": str(file_id), "raw": value})
        for child in value.values():
            rows.extend(walk_files(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(walk_files(child))
    return rows


def frontend_download_url(metadata_url: str) -> str:
    parsed = urllib.parse.urlsplit(metadata_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError(f"inadmissible metadata download URL: {metadata_url}")
    # This is the exact browser transformation in the official dataset bundle:
    # replace the metadata URL hostname with window.location.hostname.
    return urllib.parse.urlunsplit(
        ("https", "data.mendeley.com", parsed.path, parsed.query, parsed.fragment)
    )


def require_sha256(value: Any, label: str) -> str:
    text = str(value or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise RuntimeError(f"missing or invalid {label}: {value!r}")
    return text


def main() -> int:
    session = PublicSession()
    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_8_EXACT_SOURCE_ACQUISITION_FRONTEND",
        "dataset_id": DATASET_ID,
        "dataset_version": VERSION,
        "dataset_doi": DOI,
        "required_basename": REQUIRED_BASENAME,
        "file_list_contract": FILES_URL,
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
        page_bytes, page_receipt = session.fetch(PAGE_URL, "text/html")
        page_text = page_bytes.decode("utf-8", errors="strict")
        missing = [
            marker
            for marker in (DOI, "Version 2", REQUIRED_BASENAME)
            if marker not in page_text
        ]
        if missing:
            raise RuntimeError(f"official dataset page missing markers: {missing}")
        (OUT / "mendeley_dataset_v2_record.html").write_bytes(page_bytes)

        list_bytes, list_receipt = session.fetch(FILES_URL, PUBLIC_DATASET_ACCEPT)
        (OUT / "mendeley_public_files_v2.json").write_bytes(list_bytes)
        file_payload = json.loads(list_bytes.decode("utf-8"))
        rows = walk_files(file_payload)
        exact = [row for row in rows if Path(row["filename"]).name == REQUIRED_BASENAME]
        unique = {(row["filename"], row["file_id"]): row for row in exact}
        exact = list(unique.values())
        if len(exact) != 1:
            raise RuntimeError(
                f"expected exactly one focal file from official frontend; observed {len(exact)}"
            )

        selected = exact[0]
        raw = selected["raw"]
        details = raw.get("content_details")
        if not isinstance(details, dict):
            raise RuntimeError("official focal metadata lacks content_details")
        declared_size = int(details.get("size") or raw.get("size") or 0)
        if declared_size < MIN_FOCAL_BYTES:
            raise RuntimeError(f"implausible focal metadata size: {declared_size}")
        declared_sha256 = require_sha256(details.get("sha256_hash"), "focal sha256")
        metadata_download_url = str(details.get("download_url") or "")
        if not metadata_download_url:
            raise RuntimeError("official focal metadata lacks download_url")
        download_url = frontend_download_url(metadata_download_url)

        mechanism_path = OUT / REQUIRED_BASENAME
        mechanism_receipt = session.download(
            download_url,
            mechanism_path,
            "application/octet-stream",
        )
        if mechanism_path.stat().st_size != declared_size:
            raise RuntimeError(
                f"focal byte-size mismatch: {mechanism_path.stat().st_size} != {declared_size}"
            )
        if mechanism_receipt["sha256"] != declared_sha256:
            raise RuntimeError(
                f"focal SHA-256 mismatch: {mechanism_receipt['sha256']} != {declared_sha256}"
            )

        fault_path = OUT / "gem_active_faults_harmonized.geojson"
        fault_receipt = session.download(
            FAULT_URL,
            fault_path,
            "application/geo+json,application/json",
        )
        if fault_path.stat().st_size != EXPECTED_FAULT_BYTES:
            raise RuntimeError(
                f"fault byte-size mismatch: {fault_path.stat().st_size} != {EXPECTED_FAULT_BYTES}"
            )
        observed_blob_sha1 = git_blob_sha1(fault_path)
        if observed_blob_sha1 != EXPECTED_FAULT_BLOB_SHA1:
            raise RuntimeError(
                f"fault Git blob mismatch: {observed_blob_sha1} != {EXPECTED_FAULT_BLOB_SHA1}"
            )
        json.loads(fault_path.read_text("utf-8"))

        body.update(
            outcome="EXACT_BYTE_ACQUISITION_PASS",
            all_or_none_pass=True,
            dataset_page_receipt=page_receipt,
            file_list_receipt=list_receipt,
            official_file_row_count=len(rows),
            selected_mendeley_file={
                "filename": selected["filename"],
                "file_id": selected["file_id"],
                "status": raw.get("status"),
                "declared_size": declared_size,
                "declared_sha256": declared_sha256,
                "metadata_download_url": metadata_download_url,
                "frontend_rewritten_download_url": download_url,
            },
            mechanism_receipt=mechanism_receipt,
            fault_receipt={
                **fault_receipt,
                "git_blob_sha1": observed_blob_sha1,
                "expected_git_blob_sha1": EXPECTED_FAULT_BLOB_SHA1,
            },
            completed_at_utc=utc_now(),
        )
        status = 0
    except Exception as exc:
        receipt = getattr(exc, "kch_receipt", None)
        body.update(
            outcome="BLOCKED_EXACT_BYTE_ACQUISITION",
            all_or_none_pass=False,
            error_type=type(exc).__name__,
            error=str(exc),
            transport_error_receipt=receipt,
            completed_at_utc=utc_now(),
        )
        status = 3

    content = dict(body)
    body["receipt_id"] = "h8acqfrontend:" + hashlib.sha256(canonical(content)).hexdigest()
    (OUT / "ACQUISITION_RECEIPT_V0_8_FRONTEND.json").write_text(
        json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    sums = [
        f"{sha256_path(path)}  {path.name}"
        for path in sorted(OUT.iterdir(), key=lambda item: item.name)
        if path.is_file()
    ]
    (OUT / "SOURCE_SHA256SUMS.txt").write_text(
        "\n".join(sums) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
