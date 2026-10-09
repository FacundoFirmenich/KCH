#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html as html_mod
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

DATASET_ID = "2np9vw5v7w"
VERSION = 2
FILENAME = "focmec_ca_final.pickle"
USER_AGENT = "KCH-Helical-Public-Route-Probe/0.1 (+https://github.com/FacundoFirmenich/KCH)"

CANDIDATES = [
    ("dataset_page", f"https://data.mendeley.com/datasets/{DATASET_ID}/{VERSION}"),
    ("legacy_snapshot", f"https://api.data.mendeley.com/datasets/{DATASET_ID}?version={VERSION}"),
    ("public_files_api", f"https://api.data.mendeley.com/datasets/publics/{DATASET_ID}/files?version={VERSION}&$limit=100"),
    ("files_api", f"https://api.data.mendeley.com/datasets/{DATASET_ID}/files?version={VERSION}&$limit=100"),
    ("public_filename_download", f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/files/{urllib.parse.quote(FILENAME)}/download"),
    ("public_filename_event", f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/files/{urllib.parse.quote(FILENAME)}/file_downloaded"),
    ("public_filename_download_v2", f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/files/{urllib.parse.quote(FILENAME)}/download?version={VERSION}"),
    ("oai_identify", "https://data.mendeley.com/oai?verb=Identify"),
    ("oai_formats", "https://data.mendeley.com/oai?verb=ListMetadataFormats"),
    ("oai_guess_dc", "https://data.mendeley.com/oai?verb=GetRecord&metadataPrefix=oai_dc&identifier=oai:data.mendeley.com:2np9vw5v7w/2"),
    ("oai_guess_datacite", "https://data.mendeley.com/oai?verb=GetRecord&metadataPrefix=oai_datacite&identifier=oai:data.mendeley.com:2np9vw5v7w/2"),
]

SAFE_HEADERS = {
    "content-type", "content-length", "location", "etag", "last-modified",
    "accept-ranges", "content-range", "cache-control", "x-request-id",
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_once(url: str, *, method: str, range_bytes: bool = False):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml, text/html;q=0.9, */*;q=0.8",
        "Accept-Encoding": "identity",
    }
    if range_bytes:
        headers["Range"] = "bytes=0-4095"
    req = urllib.request.Request(url, headers=headers, method=method)
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=60) as resp:
            body = resp.read(512 * 1024) if method == "GET" else b""
            return int(resp.status), resp.geturl(), dict(resp.headers.items()), body, None
    except urllib.error.HTTPError as exc:
        body = exc.read(512 * 1024) if method == "GET" else b""
        return int(exc.code), exc.geturl(), dict(exc.headers.items()), body, f"HTTPError: {exc}"
    except Exception as exc:
        return None, url, {}, b"", f"{type(exc).__name__}: {exc}"


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k.lower(): v for k, v in headers.items() if k.lower() in SAFE_HEADERS}


def extract_page_evidence(text: str) -> dict:
    decoded = html_mod.unescape(text)
    urls = sorted(set(re.findall(r"https?://[^\"'<>\\\s]+", decoded)))
    interesting_urls = [u for u in urls if any(tok in u.lower() for tok in (
        DATASET_ID, "focmec", "public-files", "file_downloaded", "download_url", "api.data.mendeley"
    ))]
    uuid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
    uuids = sorted(set(re.findall(uuid_pattern, decoded)))
    contexts = []
    for needle in (FILENAME, DATASET_ID, "public-files", "file_downloaded", "download_url", "__NEXT_DATA__"):
        start = 0
        while len(contexts) < 80:
            pos = decoded.lower().find(needle.lower(), start)
            if pos < 0:
                break
            contexts.append({"needle": needle, "context": decoded[max(0, pos-300):pos+700]})
            start = pos + len(needle)
    scripts = []
    for match in re.finditer(r"<script[^>]*?(?:type=[\"']([^\"']+)[\"'])?[^>]*>(.*?)</script>", text, flags=re.I | re.S):
        stype, payload = match.group(1), match.group(2)
        if (stype and "json" in stype.lower()) or FILENAME in payload or DATASET_ID in payload:
            scripts.append({
                "type": stype,
                "chars": len(payload),
                "sha256": hashlib.sha256(payload.encode("utf-8", "replace")).hexdigest(),
                "preview": payload[:20000],
            })
    return {
        "filename_present": FILENAME in decoded,
        "dataset_id_present": DATASET_ID in decoded,
        "interesting_urls": interesting_urls[:200],
        "uuid_candidates": uuids[:200],
        "contexts": contexts,
        "json_like_scripts": scripts[:50],
    }


def main() -> int:
    out = Path("probe-output")
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, url in CANDIDATES:
        candidate = {"name": name, "url": url, "attempts": []}
        for method, use_range in (("HEAD", False), ("GET", True)):
            status, final_url, headers, body, error = request_once(url, method=method, range_bytes=use_range)
            record = {
                "method": method,
                "status": status,
                "effective_url": final_url,
                "headers": sanitize_headers(headers),
                "body_bytes_captured": len(body),
                "body_sha256": hashlib.sha256(body).hexdigest() if body else None,
                "error": error,
            }
            if body:
                ctype = headers.get("Content-Type", headers.get("content-type", ""))
                suffix = "html" if "html" in ctype else "xml" if "xml" in ctype else "json" if "json" in ctype else "bin"
                body_path = out / f"{name}.{method.lower()}.{suffix}"
                body_path.write_bytes(body)
                record["captured_path"] = str(body_path)
                if "html" in ctype or body.lstrip().startswith(b"<"):
                    try:
                        record["page_evidence"] = extract_page_evidence(body.decode("utf-8", "replace"))
                    except Exception as exc:
                        record["page_evidence_error"] = f"{type(exc).__name__}: {exc}"
                elif "json" in ctype:
                    try:
                        parsed = json.loads(body)
                        record["json_type"] = type(parsed).__name__
                        record["json_preview"] = parsed
                    except Exception as exc:
                        record["json_parse_error"] = f"{type(exc).__name__}: {exc}"
            candidate["attempts"].append(record)
        rows.append(candidate)

    receipt = {
        "format": "KCH_MENDELEY_PUBLIC_ROUTE_PROBE_V0_1",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_id": DATASET_ID,
        "version": VERSION,
        "required_filename": FILENAME,
        "authentication_used": False,
        "secrets_used": False,
        "raw_scientific_file_downloaded": False,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "candidates": rows,
    }
    (out / "PROBE_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
