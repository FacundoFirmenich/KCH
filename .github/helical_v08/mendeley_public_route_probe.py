from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

DATASET = "2np9vw5v7w"
VERSION = 2
TARGET = "focmec_ca_final.pickle"

ENDPOINTS = [
    f"https://data.mendeley.com/datasets/{DATASET}/{VERSION}",
    f"https://data.mendeley.com/datasets/compare/{DATASET}",
    f"https://api.data.mendeley.com/datasets/{DATASET}?version={VERSION}",
    f"https://api.data.mendeley.com/datasets/publics/{DATASET}?version={VERSION}",
    f"https://api.data.mendeley.com/datasets/{DATASET}/files?version={VERSION}",
    f"https://api.data.mendeley.com/datasets/publics/{DATASET}/files?version={VERSION}",
    f"https://data.mendeley.com/api/datasets/{DATASET}/{VERSION}",
    f"https://data.mendeley.com/api/datasets/{DATASET}?version={VERSION}",
    f"https://data.mendeley.com/oai?verb=ListRecords&metadataPrefix=oai_dc&set={DATASET}",
]


class Assets(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for key in ("src", "href"):
            value = values.get(key)
            if value:
                self.urls.append(value)


def request(url: str, accept: str = "*/*") -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Accept-Encoding": "identity",
            "User-Agent": "KCH-KwanBlocks-Helical-Lift/0.8 public-route-discovery",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            body = response.read()
            return {
                "requested_url": url,
                "effective_url": response.geturl(),
                "status": int(response.status),
                "headers": dict(response.headers.items()),
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        return {
            "requested_url": url,
            "effective_url": exc.geturl(),
            "status": int(exc.code),
            "headers": dict(exc.headers.items()) if exc.headers else {},
            "body": exc.read(),
            "error": f"HTTPError: {exc}",
        }
    except Exception as exc:
        return {"requested_url": url, "status": 0, "headers": {}, "body": b"", "error": repr(exc)}


def excerpt(text: str, needle: str, radius: int = 500) -> list[str]:
    hits: list[str] = []
    low = text.lower()
    start = 0
    while len(hits) < 20:
        index = low.find(needle.lower(), start)
        if index < 0:
            break
        hits.append(text[max(0, index - radius) : min(len(text), index + len(needle) + radius)])
        start = index + len(needle)
    return hits


def sanitize(result: dict[str, Any]) -> dict[str, Any]:
    body = result.pop("body")
    text = body.decode("utf-8", errors="replace")
    result.update(
        bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest() if body else None,
        target_hits=excerpt(text, TARGET),
        uuid_hits=sorted(set(re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text)))[:100],
        download_fragments=(
            excerpt(text, "file_downloaded")
            + excerpt(text, "download_url")
            + excerpt(text, "public-files")
        )[:30],
        body_prefix=text[:2000],
    )
    return result


def main() -> int:
    output = Path(os.environ.get("PROBE_OUT", "/tmp/mendeley_public_probe"))
    output.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    page_assets: list[str] = []

    for index, url in enumerate(ENDPOINTS):
        raw = request(url)
        if raw.get("status") == 200 and "text/html" in str(raw.get("headers", {}).get("Content-Type", "")):
            parser = Assets()
            parser.feed(raw["body"].decode("utf-8", errors="replace"))
            page_assets.extend(urllib.parse.urljoin(raw.get("effective_url", url), item) for item in parser.urls)
        sanitized = sanitize(raw)
        results.append(sanitized)
        (output / f"endpoint_{index:02d}.json").write_text(json.dumps(sanitized, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    js_urls = []
    seen: set[str] = set()
    for url in page_assets:
        if url in seen:
            continue
        seen.add(url)
        if ".js" in urllib.parse.urlparse(url).path:
            js_urls.append(url)

    asset_results: list[dict[str, Any]] = []
    for index, url in enumerate(js_urls[:80]):
        raw = request(url, accept="application/javascript,text/javascript,*/*;q=0.1")
        body = raw.get("body", b"")
        text = body.decode("utf-8", errors="replace")
        interesting = TARGET.lower() in text.lower() or any(
            token in text for token in ("file_downloaded", "download_url", "public-files", "/datasets/publics/")
        )
        if interesting:
            sanitized = sanitize(raw)
            asset_results.append(sanitized)
            (output / f"asset_{index:02d}.json").write_text(json.dumps(sanitized, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = {
        "format": "KCH_HELICAL_V0_8_MENDELEY_PUBLIC_ROUTE_PROBE",
        "dataset_id": DATASET,
        "version": VERSION,
        "target_basename": TARGET,
        "probed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "endpoints": results,
        "html_asset_count": len(page_assets),
        "javascript_asset_count": len(js_urls),
        "interesting_asset_count": len(asset_results),
        "interesting_assets": asset_results,
        "directional_scientific_values_accessed": False,
        "authority_ceiling": "NONE",
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["probe_id"] = "h8route:" + hashlib.sha256(canonical).hexdigest()
    (output / "MENDELEY_PUBLIC_ROUTE_PROBE.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
