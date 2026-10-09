from __future__ import annotations

from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any
import urllib.parse
import urllib.request

import helical_remote_gate as gate

DATASET_PAGE_URL = f"https://data.mendeley.com/datasets/{gate.DATASET_ID}/{gate.DATASET_VERSION}"
PUBLIC_FILENAME_URL = (
    f"https://data.mendeley.com/public-files/datasets/{gate.DATASET_ID}/files/"
    f"{urllib.parse.quote(gate.MECHANISM_BASENAME)}/download"
)


class ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.buffer: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        values = {key.lower(): value for key, value in attrs}
        script_type = (values.get("type") or "").lower()
        self.capture = script_type in {"application/json", "application/ld+json"} or values.get("id") == "__NEXT_DATA__"
        self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self.capture:
            self.scripts.append("".join(self.buffer))
            self.capture = False
            self.buffer = []


def safe_url(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "path": parsed.path,
        "query_keys": sorted(urllib.parse.parse_qs(parsed.query, keep_blank_values=True)),
        "query_values_recorded": False,
    }


def fetch_public_page(timeout: int) -> tuple[str, dict[str, Any]]:
    request = urllib.request.Request(
        DATASET_PAGE_URL,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
            "User-Agent": "KCH-Helical-Lift/0.10 public-version-audit",
        },
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024:
            raise RuntimeError("dataset page exceeds 32 MiB")
        receipt = {
            "adapter": "PUBLIC_VERSION_PAGE",
            "requested": safe_url(DATASET_PAGE_URL),
            "effective": safe_url(response.geturl()),
            "status": int(response.status),
            "content_type": response.headers.get("Content-Type"),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "elapsed_seconds": time.monotonic() - started,
        }
    text = raw.decode("utf-8", errors="strict")
    required = [
        "Statewide California focal mechanism catalog and stress model (1981-2021)",
        gate.MECHANISM_BASENAME,
        gate.DOI,
    ]
    missing = [value for value in required if value not in text]
    version_patterns = [
        rf"Version\s*{gate.DATASET_VERSION}\b",
        rf'"version"\s*:\s*{gate.DATASET_VERSION}\b',
        rf"/{gate.DATASET_VERSION}(?:[\"'/?#<]|$)",
    ]
    if missing or not any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in version_patterns):
        raise RuntimeError(f"public version-page audit failed; missing={missing}")
    receipt["dataset_id"] = gate.DATASET_ID
    receipt["dataset_version"] = gate.DATASET_VERSION
    receipt["doi"] = gate.DOI
    receipt["required_file_observed"] = True
    return text, receipt


def recursive_urls(value: Any, target: str, inherited_name: str | None = None) -> list[str]:
    urls: list[str] = []
    if isinstance(value, dict):
        name = inherited_name
        for key in ("filename", "file_name", "name", "title"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                name = candidate
                break
        for key, child in value.items():
            if isinstance(child, str) and ("public-files/datasets/" in child or child.endswith("/file_downloaded")):
                if name is None or Path(urllib.parse.urlsplit(name).path).name == target or target in json.dumps(value, ensure_ascii=False):
                    urls.append(child)
            else:
                urls.extend(recursive_urls(child, target, name))
    elif isinstance(value, list):
        for child in value:
            urls.extend(recursive_urls(child, target, inherited_name))
    return urls


def resolve_public_download(page: str) -> tuple[str, dict[str, Any]]:
    normalized = (
        page.replace("\\u002F", "/")
        .replace("\\u002f", "/")
        .replace("\\/", "/")
        .replace("&amp;", "&")
    )
    candidates: list[str] = []
    collector = ScriptCollector()
    collector.feed(page)
    for script in collector.scripts:
        try:
            value = json.loads(script)
        except Exception:
            continue
        candidates.extend(recursive_urls(value, gate.MECHANISM_BASENAME))
    direct_pattern = re.compile(
        rf"https?://data\.mendeley\.com/public-files/datasets/{re.escape(gate.DATASET_ID)}/files/"
        r"(?:[0-9a-fA-F-]{36}|[^\"'<>\s/]+)/"
        r"(?:file_downloaded|download)(?:\?[^\"'<>\s]*)?"
    )
    for match in direct_pattern.findall(normalized):
        candidates.append(match)
    for filename_match in re.finditer(re.escape(gate.MECHANISM_BASENAME), normalized):
        start = max(0, filename_match.start() - 12000)
        end = min(len(normalized), filename_match.end() + 12000)
        candidates.extend(direct_pattern.findall(normalized[start:end]))
    cleaned: list[str] = []
    for url in candidates:
        url = url.replace("\\u0026", "&").replace("\\u003d", "=")
        if gate.DATASET_ID not in url:
            continue
        if url not in cleaned:
            cleaned.append(url)
    uuid_urls = [
        url for url in cleaned
        if re.search(r"/files/[0-9a-fA-F-]{36}/file_downloaded", url)
    ]
    if len(uuid_urls) == 1:
        selected = uuid_urls[0]
        method = "EMBEDDED_VERSION_PAGE_UUID"
    elif len(uuid_urls) > 1:
        near_target = [url for url in uuid_urls if gate.MECHANISM_BASENAME in url]
        if len(near_target) != 1:
            raise RuntimeError(f"ambiguous public UUID download URLs: {len(uuid_urls)}")
        selected = near_target[0]
        method = "EMBEDDED_VERSION_PAGE_UUID_TARGET_MATCH"
    else:
        selected = PUBLIC_FILENAME_URL
        method = "PUBLIC_FILENAME_ROUTE_VERSION_PAGE_AUDITED"
    return selected, {
        "resolution_method": method,
        "candidate_count": len(cleaned),
        "uuid_candidate_count": len(uuid_urls),
        "selected": safe_url(selected),
        "dataset_page": safe_url(DATASET_PAGE_URL),
        "dataset_version": gate.DATASET_VERSION,
        "doi": gate.DOI,
    }


_PAGE_TEXT: str | None = None
_PAGE_RECEIPT: dict[str, Any] | None = None
_PUBLIC_DOWNLOAD_URL: str | None = None
_RESOLUTION_RECEIPT: dict[str, Any] | None = None
_ORIGINAL_STREAM_DOWNLOAD = gate.stream_download


def public_request_json(url: str, timeout: int) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    global _PAGE_TEXT, _PAGE_RECEIPT, _PUBLIC_DOWNLOAD_URL, _RESOLUTION_RECEIPT
    if url != gate.SNAPSHOT_URL:
        raise RuntimeError(f"unexpected authenticated metadata endpoint request: {safe_url(url)}")
    _PAGE_TEXT, _PAGE_RECEIPT = fetch_public_page(timeout)
    _PUBLIC_DOWNLOAD_URL, _RESOLUTION_RECEIPT = resolve_public_download(_PAGE_TEXT)
    synthetic = {
        "id": gate.DATASET_ID,
        "version": gate.DATASET_VERSION,
        "doi": gate.DOI,
        "public_version_page_audited": True,
        "files": [{
            "filename": gate.MECHANISM_BASENAME,
            "id": "public-version-page-route",
            "content_details": {"size": None, "sha256_hash": None},
        }],
        "public_resolution": _RESOLUTION_RECEIPT,
    }
    raw = json.dumps(synthetic, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt = dict(_PAGE_RECEIPT)
    receipt["public_resolution"] = _RESOLUTION_RECEIPT
    receipt["synthetic_snapshot_sha256"] = hashlib.sha256(raw).hexdigest()
    receipt["authenticated_api_used"] = False
    return synthetic, receipt, raw


def public_stream_download(url: str, output: Path, timeout: int, expected_bytes: int | None = None) -> dict[str, Any]:
    if output.name != gate.MECHANISM_BASENAME:
        return _ORIGINAL_STREAM_DOWNLOAD(url, output, timeout, expected_bytes)
    if _PUBLIC_DOWNLOAD_URL is None or _RESOLUTION_RECEIPT is None:
        raise RuntimeError("public download URL was not resolved before mechanism acquisition")
    request = urllib.request.Request(
        _PUBLIC_DOWNLOAD_URL,
        headers={
            "Accept": "application/octet-stream,*/*",
            "Accept-Encoding": "identity",
            "Referer": DATASET_PAGE_URL,
            "User-Agent": "KCH-Helical-Lift/0.10 public-file-acquisition",
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
    if status not in {200, 206}:
        raise RuntimeError(f"public file route returned HTTP {status}")
    if total < 100 * 1024 * 1024:
        raise RuntimeError(f"mechanism payload unexpectedly small: {total} bytes")
    if content_type and "text/html" in content_type.lower():
        raise RuntimeError("public file route returned HTML rather than the pickle payload")
    with tmp.open("rb") as handle:
        first = handle.read(2)
    if len(first) < 2 or first[0] != 0x80:
        raise RuntimeError(f"mechanism payload lacks a binary pickle protocol header: {first!r}")
    os.replace(tmp, output)
    return {
        "adapter": "MENDELEY_PUBLIC_FILE_DISTRIBUTION",
        "requested": safe_url(_PUBLIC_DOWNLOAD_URL),
        "effective": safe_url(effective_url),
        "status": status,
        **headers,
        "bytes": total,
        "sha256": digest.hexdigest(),
        "elapsed_seconds": time.monotonic() - started,
        "dataset_page": safe_url(DATASET_PAGE_URL),
        "dataset_id": gate.DATASET_ID,
        "dataset_version": gate.DATASET_VERSION,
        "doi": gate.DOI,
        "required_file": gate.MECHANISM_BASENAME,
        "authenticated_api_used": False,
        "resolution": _RESOLUTION_RECEIPT,
    }


gate.request_json = public_request_json
gate.stream_download = public_stream_download

if __name__ == "__main__":
    raise SystemExit(gate.main())
