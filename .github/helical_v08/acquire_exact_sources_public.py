from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATASET_ID = "2np9vw5v7w"
VERSION = 2
REQUIRED_BASENAME = "focmec_ca_final.pickle"
PUBLIC_FILES_URL = (
    f"https://data.mendeley.com/public-api/datasets/{DATASET_ID}/files"
    f"?folder_id=root&version={VERSION}&$start=0&$limit=1000"
)
FAULT_URL = (
    "https://raw.githubusercontent.com/GEMScienceTools/gem-global-active-faults/"
    "56816508ad92fd6846dad1163b1c8c01376a2cd1/"
    "geojson/gem_active_faults_harmonized.geojson"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def request(url: str, *, accept: str) -> tuple[bytes, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Accept-Encoding": "identity",
            "User-Agent": "KCH-KwanBlocks-Helical-Lift/0.8 exact-byte public-web acquisition",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        data = response.read()
        receipt = {
            "requested_url": url,
            "effective_url": response.geturl(),
            "status": int(response.status),
            "headers": dict(response.headers.items()),
            "bytes": len(data),
            "sha256": sha256_bytes(data),
        }
    return data, receipt


def walk_files(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        filename = value.get("filename") or value.get("file_name") or value.get("name")
        file_id = value.get("id") or value.get("uuid") or value.get("file_id")
        details = value.get("content_details") if isinstance(value.get("content_details"), dict) else {}
        download_url = details.get("download_url") or value.get("download_url")
        if filename and file_id:
            rows.append(
                {
                    "filename": str(filename),
                    "file_id": str(file_id),
                    "download_url": str(download_url) if download_url else None,
                    "raw": value,
                }
            )
        for child in value.values():
            rows.extend(walk_files(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(walk_files(child))
    return rows


def public_download_candidates(download_url: str) -> list[str]:
    parsed = urllib.parse.urlsplit(download_url)
    candidates = [download_url]
    if parsed.scheme and parsed.netloc:
        public_host = urllib.parse.urlunsplit((parsed.scheme, "data.mendeley.com", parsed.path, parsed.query, parsed.fragment))
        if public_host not in candidates:
            candidates.append(public_host)
    else:
        candidates.append(urllib.parse.urljoin("https://data.mendeley.com", download_url))
    return candidates


def download_public_file(download_url: str) -> tuple[bytes, dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    for candidate in public_download_candidates(download_url):
        try:
            data, receipt = request(candidate, accept="application/octet-stream")
            receipt["route_role"] = "Mendeley_web_client_public_download_url"
            return data, receipt, failures
        except Exception as exc:
            failures.append({"url": candidate, "error_type": type(exc).__name__, "error": str(exc)})
    raise RuntimeError(f"all public download URL candidates failed: {failures}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_8_ACQUISITION_ATTEMPT",
        "transport_revision": "PUBLIC_WEB_API_SUCCESSOR_TO_OIDC_401",
        "dataset_id": DATASET_ID,
        "version": VERSION,
        "required_basename": REQUIRED_BASENAME,
        "attempted_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "authority_ceiling": "NONE",
    }
    try:
        files_bytes, files_receipt = request(PUBLIC_FILES_URL, accept="application/json")
        files_payload = json.loads(files_bytes.decode("utf-8"))
        files = walk_files(files_payload)
        matches = [row for row in files if Path(row["filename"]).name == REQUIRED_BASENAME]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one required file in public file listing; observed {len(matches)}; "
                f"available={[row['filename'] for row in files]}"
            )
        selected = matches[0]
        download_url = selected.get("download_url")
        if not download_url:
            raise RuntimeError("required public file metadata lacks content_details.download_url")
        mechanism, mechanism_receipt, route_failures = download_public_file(str(download_url))
        fault, fault_receipt = request(FAULT_URL, accept="application/geo+json,application/json")
        if not mechanism or not fault:
            raise RuntimeError("empty required entity body")
        if mechanism[:32].lstrip().lower().startswith((b"<!doctype html", b"<html")):
            raise RuntimeError("Mendeley download returned HTML instead of pickle entity body")
        mechanism_path = out / REQUIRED_BASENAME
        fault_path = out / "gem_active_faults_harmonized.geojson"
        mechanism_path.write_bytes(mechanism)
        fault_path.write_bytes(fault)
        json.loads(fault.decode("utf-8"))
        body.update(
            outcome="EXACT_BYTE_ACQUISITION_PASS",
            files_listing_receipt=files_receipt,
            selected_public_file={
                "filename": selected["filename"],
                "file_id": selected["file_id"],
                "metadata_download_url": download_url,
            },
            public_route_failures_before_success=route_failures,
            mechanism_receipt=mechanism_receipt,
            fault_receipt=fault_receipt,
            mechanism_path=mechanism_path.name,
            fault_path=fault_path.name,
            all_or_none_pass=True,
            source_substitution=False,
            text_normalization=False,
        )
        status = 0
    except Exception as exc:
        body.update(
            outcome="BLOCKED_EXACT_BYTE_ACQUISITION",
            error_type=type(exc).__name__,
            error=str(exc),
            all_or_none_pass=False,
            source_substitution=False,
        )
        status = 3
    body["receipt_id"] = "h8acq:" + sha256_bytes(canonical(body))
    write_json(out / "ACQUISITION_RECEIPT_V0_8.json", body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
