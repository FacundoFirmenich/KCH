from __future__ import annotations

import hashlib
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
REQUIRED_BASENAME = "focmec_ca_final.pickle"
PAGE_URL = f"https://data.mendeley.com/datasets/{DATASET_ID}/{VERSION}"
ORIGIN = "https://data.mendeley.com"
OUT = Path(os.environ["RUNNER_TEMP"]) / "helical-v08-public-file-discovery"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "Accept-Encoding": "identity",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "KCH-KwanBlocks-Helical-Lift-v0.8-discovery"
    ),
    "Referer": PAGE_URL,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str, accept: str) -> tuple[int, dict[str, str], bytes, str]:
    req = urllib.request.Request(url, headers={**HEADERS, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return (
                int(response.status),
                {str(k): str(v) for k, v in response.headers.items()},
                response.read(),
                response.geturl(),
            )
    except urllib.error.HTTPError as exc:
        return (
            int(exc.code),
            {str(k): str(v) for k, v in exc.headers.items()},
            exc.read(2 * 1024 * 1024),
            exc.geturl(),
        )


def extract_state(page: str) -> dict[str, Any]:
    marker = "window.INITIAL_STATE = "
    start = page.find(marker)
    if start < 0:
        return {}
    start += len(marker)
    end = page.find("window.initialTime", start)
    if end < 0:
        end = page.find("</script>", start)
    raw = page[start:end].strip()
    if raw.endswith(";"):
        raw = raw[:-1]
    return json.loads(raw)


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


def json_or_none(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def snippets(text: str, needles: tuple[str, ...], radius: int = 220) -> list[str]:
    found: list[str] = []
    for needle in needles:
        start = 0
        while True:
            idx = text.find(needle, start)
            if idx < 0:
                break
            candidate = text[max(0, idx - radius): idx + len(needle) + radius]
            if candidate not in found:
                found.append(candidate)
            start = idx + len(needle)
            if len(found) >= 250:
                return found
    return found


def main() -> int:
    started = utc_now()
    page_status, page_headers, page_bytes, page_effective = fetch(PAGE_URL, "text/html")
    if page_status != 200:
        raise RuntimeError(f"dataset page status {page_status}")
    page = page_bytes.decode("utf-8")
    (OUT / "dataset_page.html").write_bytes(page_bytes)
    state = extract_state(page)
    (OUT / "initial_state.json").write_text(
        json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    config = state.get("configClient", {}) if isinstance(state, dict) else {}
    api_base = str(config.get("apiBaseUrl") or "/api/datasets-v2")
    public_base = str(config.get("publicApiBaseUrl") or "/public-api")

    script_match = re.search(
        r'<script[^>]+src=["\']([^"\']*?/datasets/bundle\.js\?[^"\']+)["\']',
        page,
        re.I,
    )
    bundle_url = urllib.parse.urljoin(ORIGIN, script_match.group(1)) if script_match else None
    bundle_receipt: dict[str, Any] | None = None
    if bundle_url:
        status, headers, body, effective = fetch(bundle_url, "application/javascript")
        bundle_receipt = {
            "url": bundle_url,
            "effective_url": effective,
            "status": status,
            "headers": headers,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
        if status == 200:
            (OUT / "datasets_bundle.js").write_bytes(body)
            text = body.decode("utf-8", errors="replace")
            bundle_snips = snippets(
                text,
                (
                    "apiBaseUrl",
                    "publicApiBaseUrl",
                    "/files",
                    "files?",
                    "folder_id",
                    "file_downloaded",
                    "datasets-v2",
                    "public-api",
                ),
            )
            (OUT / "bundle_endpoint_snippets.txt").write_text(
                "\n\n--- SNIPPET ---\n\n".join(bundle_snips),
                encoding="utf-8",
            )

    api_base_url = urllib.parse.urljoin(ORIGIN, api_base.rstrip("/") + "/")
    public_base_url = urllib.parse.urljoin(ORIGIN, public_base.rstrip("/") + "/")
    candidate_paths = [
        f"{DATASET_ID}/files?version={VERSION}",
        f"datasets/{DATASET_ID}/files?version={VERSION}",
        f"datasets/publics/{DATASET_ID}/files?version={VERSION}",
        f"{DATASET_ID}/versions/{VERSION}/files",
        f"datasets/{DATASET_ID}/versions/{VERSION}/files",
        f"datasets/{DATASET_ID}/{VERSION}/files",
        f"{DATASET_ID}/{VERSION}/files",
    ]
    candidate_urls: list[str] = []
    for base in (api_base_url, public_base_url):
        for path in candidate_paths:
            candidate_urls.append(urllib.parse.urljoin(base, path))
    candidate_urls.extend(
        [
            f"{ORIGIN}/api/datasets-v2/{DATASET_ID}/files?version={VERSION}&$start=0&$limit=100",
            f"{ORIGIN}/public-api/datasets/{DATASET_ID}/files?version={VERSION}&$start=0&$limit=100",
            f"{ORIGIN}/api/datasets-v2/datasets/{DATASET_ID}/files?version={VERSION}&$start=0&$limit=100",
        ]
    )

    probes: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for url in candidate_urls:
        if url in seen:
            continue
        seen.add(url)
        status, headers, body, effective = fetch(url, "application/json")
        parsed = json_or_none(body)
        response_path = OUT / f"probe_{len(probes):02d}.body"
        response_path.write_bytes(body)
        rows = walk_files(parsed) if parsed is not None else []
        exact = [row for row in rows if Path(row["filename"]).name == REQUIRED_BASENAME]
        probe = {
            "url": url,
            "effective_url": effective,
            "status": status,
            "headers": headers,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "json": parsed is not None,
            "file_rows": len(rows),
            "exact_matches": [
                {"filename": row["filename"], "file_id": row["file_id"], "raw": row["raw"]}
                for row in exact
            ],
            "body_file": response_path.name,
        }
        probes.append(probe)
        matches.extend(probe["exact_matches"])

    result = {
        "format": "KCH_MENDELEY_PUBLIC_FILE_DISCOVERY_V0_8",
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "dataset_id": DATASET_ID,
        "version": VERSION,
        "required_basename": REQUIRED_BASENAME,
        "page": {
            "url": PAGE_URL,
            "effective_url": page_effective,
            "status": page_status,
            "headers": page_headers,
            "bytes": len(page_bytes),
            "sha256": hashlib.sha256(page_bytes).hexdigest(),
        },
        "config": config,
        "bundle": bundle_receipt,
        "probes": probes,
        "exact_matches": matches,
        "outcome": "PUBLIC_FILE_ID_DISCOVERED" if matches else "PUBLIC_FILE_ID_NOT_DISCOVERED",
        "authority_ceiling": "NONE",
        "deserialization_performed": False,
        "scientific_execution_performed": False,
    }
    result["receipt_id"] = "h8filediscovery:" + hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (OUT / "DISCOVERY_RECEIPT.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if matches else 3


if __name__ == "__main__":
    raise SystemExit(main())
