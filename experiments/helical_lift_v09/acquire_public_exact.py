from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

DATASET_ID = "2np9vw5v7w"
VERSION = 2
DOI = "10.17632/2np9vw5v7w.2"
REQUIRED = "focmec_ca_final.pickle"
PAGE = f"https://data.mendeley.com/datasets/{DATASET_ID}/{VERSION}"
FAULT_REPO = "GEMScienceTools/gem-global-active-faults"
FAULT_COMMIT = "56816508ad92fd6846dad1163b1c8c01376a2cd1"
FAULT_PATH = "geojson/gem_active_faults_harmonized.geojson"
FAULT_BLOB = "fb164770b529695544fa864abe2cc9dd8aa5793d"
FAULT_URL = f"https://raw.githubusercontent.com/{FAULT_REPO}/{FAULT_COMMIT}/{FAULT_PATH}"
UA = "Mozilla/5.0 KCH-KwanBlocks-Helical-Lift/0.9 public exact-byte acquisition"
CHUNK = 8 * 1024 * 1024
MIN_BYTES = 400_000_000
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}")
SAFE_HEADERS = {"content-type", "content-length", "content-disposition", "etag", "last-modified", "date", "x-amz-version-id"}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canon(x: Any) -> bytes:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write(path: Path, x: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def file_hash(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def safe_url(url: str) -> dict[str, Any]:
    p = urllib.parse.urlsplit(url)
    return {
        "origin_and_path": urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", "")),
        "query_present": bool(p.query),
        "url_sha256": hashlib.sha256(url.encode()).hexdigest(),
    }


def req(url: str, accept: str, timeout: int = 300) -> tuple[bytes, dict[str, Any]]:
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Encoding": "identity"})
    started = utc()
    with urllib.request.urlopen(r, timeout=timeout) as response:
        body = response.read()
        return body, {
            "requested": safe_url(url), "effective": safe_url(response.geturl()),
            "status": int(response.status), "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "headers": {k.lower(): str(v) for k, v in response.headers.items() if k.lower() in SAFE_HEADERS},
            "started_at_utc": started, "finished_at_utc": utc(),
        }


def download(url: str, path: Path, timeout: int = 3600) -> dict[str, Any]:
    partial = path.with_suffix(path.suffix + ".partial")
    partial.unlink(missing_ok=True)
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/octet-stream,application/zip", "Accept-Encoding": "identity"})
    h = hashlib.sha256(); size = 0; started = utc()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as response, partial.open("wb") as out:
            while True:
                block = response.read(CHUNK)
                if not block:
                    break
                out.write(block); h.update(block); size += len(block)
            out.flush(); os.fsync(out.fileno())
            receipt = {
                "requested": safe_url(url), "effective": safe_url(response.geturl()),
                "status": int(response.status), "bytes": size, "sha256": h.hexdigest(),
                "headers": {k.lower(): str(v) for k, v in response.headers.items() if k.lower() in SAFE_HEADERS},
                "started_at_utc": started, "finished_at_utc": utc(),
            }
        partial.replace(path)
        return receipt
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def normalize(text: str) -> str:
    return html.unescape(text).replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")


def file_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        name = value.get("filename") or value.get("file_name")
        if name:
            rows.append(value)
        for v in value.values():
            rows.extend(file_rows(v))
    elif isinstance(value, list):
        for v in value:
            rows.extend(file_rows(v))
    return rows


def routes_from_json(value: Any) -> tuple[list[str], list[dict[str, Any]]]:
    routes: list[str] = []; records: list[dict[str, Any]] = []
    for row in file_rows(value):
        if Path(str(row.get("filename") or row.get("file_name"))).name != REQUIRED:
            continue
        content = row.get("content_details") if isinstance(row.get("content_details"), dict) else {}
        fid = row.get("id") or row.get("uuid") or row.get("file_id")
        for url in (content.get("download_url"), row.get("download_url"), row.get("url")):
            if isinstance(url, str):
                routes.append(urllib.parse.urljoin("https://data.mendeley.com", url))
        if fid:
            routes.extend([
                f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/files/{fid}/file_downloaded",
                f"https://api.data.mendeley.com/datasets/{DATASET_ID}/files/{fid}/file_downloaded?version={VERSION}",
            ])
        records.append({
            "filename": REQUIRED, "file_id": str(fid) if fid else None,
            "size": row.get("size") or content.get("size"),
            "sha256": content.get("sha256_hash") or row.get("sha256_hash"),
            "record_sha256": hashlib.sha256(canon(row)).hexdigest(),
        })
    return list(dict.fromkeys(routes)), records


def routes_near_filename(text: str) -> tuple[list[str], list[dict[str, Any]]]:
    text = normalize(text)
    routes: list[str] = []; contexts: list[dict[str, Any]] = []
    direct = re.compile(rf"https://data\.mendeley\.com/public-files/datasets/{DATASET_ID}/files/({UUID.pattern})/file_downloaded[^\"'<>\s]*", re.I)
    routes.extend(m.group(0) for m in direct.finditer(text))
    for m in re.finditer(re.escape(REQUIRED), text, re.I):
        window = text[max(0, m.start()-30000):min(len(text), m.end()+30000)]
        ids = sorted(set(UUID.findall(window)))
        contexts.append({"window_sha256": hashlib.sha256(window.encode(errors="replace")).hexdigest(), "uuid_candidates": ids})
        routes.extend(f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/files/{fid}/file_downloaded" for fid in ids)
    return list(dict.fromkeys(routes)), contexts


def validate_pickle(path: Path) -> None:
    if path.stat().st_size < MIN_BYTES:
        raise RuntimeError(f"body too small for published focal catalog: {path.stat().st_size}")
    prefix = path.open("rb").read(64).lstrip().lower()
    if prefix.startswith((b"<html", b"<!doctype", b"pk\x03\x04")):
        raise RuntimeError("body is not the required pickle member")


def extract_zip(archive: Path, destination: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC failure: {bad}")
        matches = [i for i in z.infolist() if not i.is_dir() and PurePosixPath(i.filename).name == REQUIRED]
        if len(matches) != 1:
            raise RuntimeError(f"ZIP contains {len(matches)} required members")
        info = matches[0]
        if info.file_size < MIN_BYTES or info.flag_bits & 1:
            raise RuntimeError("ZIP member size/encryption gate failed")
        partial = destination.with_suffix(destination.suffix + ".partial")
        h = hashlib.sha256(); size = 0
        with z.open(info) as src, partial.open("wb") as out:
            while True:
                b = src.read(CHUNK)
                if not b: break
                out.write(b); h.update(b); size += len(b)
            out.flush(); os.fsync(out.fileno())
        if size != info.file_size:
            partial.unlink(missing_ok=True); raise RuntimeError("ZIP member length mismatch")
        partial.replace(destination)
        return {"member_name": info.filename, "bytes": size, "sha256": h.hexdigest(), "crc32": f"{info.CRC:08x}"}


def rendered_dom(receipts: Path) -> tuple[list[str], dict[str, Any]]:
    chrome = next((shutil.which(x) for x in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(x)), None)
    if not chrome:
        return [], {"status": "BROWSER_UNAVAILABLE"}
    command = [chrome, "--headless=new", "--disable-gpu", "--disable-dev-shm-usage", "--virtual-time-budget=45000", "--dump-dom", PAGE]
    run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, check=False)
    receipts.joinpath("HEADLESS_RENDERED_DATASET_PAGE.html").write_bytes(run.stdout)
    routes, contexts = routes_near_filename(run.stdout.decode("utf-8", errors="replace"))
    return routes, {
        "status": "PASS" if run.returncode == 0 else "FAILED", "returncode": run.returncode,
        "chrome": Path(chrome).name, "dom_bytes": len(run.stdout), "dom_sha256": hashlib.sha256(run.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(run.stderr).hexdigest(), "stderr_tail": run.stderr.decode(errors="replace")[-3000:],
        "contexts": contexts, "routes": len(routes),
    }


def acquire_mechanism(data: Path, receipts: Path, discovery: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    target = data / REQUIRED
    static, page_receipt = req(PAGE, "text/html,application/xhtml+xml")
    receipts.joinpath("DATASET_PAGE_V2.html").write_bytes(static)
    discovery["dataset_page"] = page_receipt
    routes, contexts = routes_near_filename(static.decode("utf-8", errors="replace"))
    discovery["static_contexts"] = contexts

    endpoints = [
        f"https://data.mendeley.com/public-api/datasets/{DATASET_ID}/files?version={VERSION}",
        f"https://data.mendeley.com/public-api/datasets/{DATASET_ID}/files?version={VERSION}&$start=0&$limit=100",
        f"https://data.mendeley.com/public-api/datasets/publics/{DATASET_ID}/files?version={VERSION}&$start=0&$limit=100",
        f"https://data.mendeley.com/api/datasets-v2/datasets/{DATASET_ID}/files?version={VERSION}",
        f"https://data.mendeley.com/api/datasets-v2/datasets/{DATASET_ID}/files?version={VERSION}&$start=0&$limit=100",
        f"https://data.mendeley.com/api/datasets-v2/datasets/publics/{DATASET_ID}/files?version={VERSION}&$start=0&$limit=100",
        f"https://api.data.mendeley.com/datasets/publics/{DATASET_ID}/files?version={VERSION}&$start=0&$limit=100",
    ]
    probes: list[dict[str, Any]] = []
    for i, endpoint in enumerate(endpoints):
        try:
            raw, receipt = req(endpoint, "application/json,application/vnd.mendeley-public-dataset.1+json")
            parsed = json.loads(raw.decode())
            new_routes, records = routes_from_json(parsed); routes.extend(new_routes)
            receipts.joinpath(f"PUBLIC_PROXY_RESPONSE_{i:02d}.json").write_bytes(raw)
            probes.append({"endpoint": safe_url(endpoint), "receipt": receipt, "matching_records": records, "routes": len(new_routes)})
        except Exception as exc:
            probes.append({"endpoint": safe_url(endpoint), "error_type": type(exc).__name__, "error": str(exc)})
    discovery["public_proxy_probes"] = probes

    browser_routes, browser = rendered_dom(receipts); routes.extend(browser_routes)
    discovery["headless_render"] = browser
    routes = list(dict.fromkeys(routes))
    discovery["candidate_route_count"] = len(routes)
    errors: list[dict[str, Any]] = []
    for route in routes:
        try:
            result = download(route, target)
            validate_pickle(target)
            result["transport"] = "PUBLIC_FILE_ROUTE"
            discovery["direct_failures_before_success"] = errors
            return target, result
        except Exception as exc:
            target.unlink(missing_ok=True)
            errors.append({"route": safe_url(route), "error_type": type(exc).__name__, "error": str(exc)})

    archive = data / f"{DATASET_ID}_v{VERSION}.zip"
    zip_routes = [
        f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/zip/file_downloaded?version={VERSION}",
        f"https://data.mendeley.com/public-api/datasets/{DATASET_ID}/zip/file_downloaded?version={VERSION}",
        f"https://data.mendeley.com/api/datasets-v2/datasets/{DATASET_ID}/zip/file_downloaded?version={VERSION}",
        f"https://api.data.mendeley.com/datasets/{DATASET_ID}/zip/file_downloaded?version={VERSION}",
    ]
    zip_errors: list[dict[str, Any]] = []
    for route in zip_routes:
        try:
            zr = download(route, archive)
            member = extract_zip(archive, target); validate_pickle(target); archive.unlink(missing_ok=True)
            discovery["direct_failures"] = errors; discovery["zip_failures_before_success"] = zip_errors
            return target, {"transport": "OFFICIAL_DATASET_ZIP_MEMBER", "official_zip_sha256": zr["sha256"], "official_zip_bytes": zr["bytes"], **member}
        except Exception as exc:
            archive.unlink(missing_ok=True); target.unlink(missing_ok=True)
            zip_errors.append({"route": safe_url(route), "error_type": type(exc).__name__, "error": str(exc)})
    discovery["direct_failures"] = errors; discovery["zip_failures"] = zip_errors
    raise RuntimeError("no public authoritative route yielded the required focal catalog")


def git_blob(path: Path) -> str:
    h = hashlib.sha1(); h.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""): h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--output-dir", type=Path, required=True); args = ap.parse_args()
    root = args.output_dir.resolve(); data = root / "data"; receipts = root / "receipts"
    data.mkdir(parents=True, exist_ok=True); receipts.mkdir(parents=True, exist_ok=True)
    discovery: dict[str, Any] = {}
    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_9_EXACT_BYTE_ACQUISITION", "dataset_id": DATASET_ID,
        "dataset_version": VERSION, "doi": DOI, "required_basename": REQUIRED,
        "fault_repository": FAULT_REPO, "fault_commit": FAULT_COMMIT, "fault_path": FAULT_PATH,
        "expected_fault_git_blob_sha1": FAULT_BLOB, "attempted_at_utc": utc(), "authority_ceiling": "NONE",
        "secrets_collected": False, "authorization_headers_sent": False, "signed_redirect_urls_persisted": False,
    }
    try:
        mechanism, mr = acquire_mechanism(data, receipts, discovery)
        fault = data / "gem_active_faults_harmonized.geojson"
        fr = download(FAULT_URL, fault)
        json.loads(fault.read_text())
        observed_blob = git_blob(fault)
        if observed_blob != FAULT_BLOB: raise RuntimeError(f"fault blob mismatch: {observed_blob}")
        if file_hash(mechanism) != mr["sha256"]: raise RuntimeError("mechanism post-acquisition hash mismatch")
        body.update({
            "outcome": "EXACT_BYTE_ACQUISITION_PASS", "all_or_none_pass": True, "public_discovery": discovery,
            "selected_file": {"basename": REQUIRED, "observed_bytes": mechanism.stat().st_size},
            "mechanism_receipt": mr, "fault_receipt": {**fr, "git_blob_sha1": observed_blob},
            "mechanism_relative_path": str(mechanism.relative_to(root)), "fault_relative_path": str(fault.relative_to(root)),
        }); status = 0
    except Exception as exc:
        discovery["terminal_error"] = {"type": type(exc).__name__, "error": str(exc)}
        body.update({"outcome": "BLOCKED_EXACT_BYTE_ACQUISITION", "all_or_none_pass": False, "error_type": type(exc).__name__, "error": str(exc)})
        for p in (data / REQUIRED, data / "gem_active_faults_harmonized.geojson", data / f"{DATASET_ID}_v{VERSION}.zip"):
            p.unlink(missing_ok=True)
        status = 3
    write(receipts / "PUBLIC_DISCOVERY_RECEIPT_V0_9.json", discovery)
    body["receipt_id"] = "h9acq:" + hashlib.sha256(canon(body)).hexdigest()
    write(receipts / "ACQUISITION_RECEIPT_V0_9.json", body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
