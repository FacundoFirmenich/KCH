from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SOURCES = [
    ("CAHUILLA_SWARM_2016_2019", "https://service.scedc.caltech.edu/ftp/cahuilla_swarm/out.growclust_cat", "cahuilla_swarm/out.growclust_cat"),
    ("RIDGECREST_QTM_2019", "https://service.scedc.caltech.edu/ftp/QTMcatalog-ridgecrest/ridgecrest_qtm.tar.gz", "QTMcatalog-ridgecrest/ridgecrest_qtm.tar.gz"),
    ("CALMEX_BORDER_2012_2020", "https://service.scedc.caltech.edu/ftp/calmex/out.hypoDD.reloc", "calmex/out.hypoDD.reloc"),
]


def fetch(name: str, route: str, url: str, root: Path) -> dict[str, object]:
    safe = f"{name}__{route}"
    body = root / f"{safe}.body"
    headers = root / f"{safe}.headers"
    meta = root / f"{safe}.meta.json"
    stderr = root / f"{safe}.stderr.txt"
    cmd = [
        "curl", "--location", "--connect-timeout", "8", "--max-time", "35",
        "--header", "Accept-Encoding: identity", "--dump-header", str(headers),
        "--output", str(body), "--write-out", "%{json}", url,
    ]
    with meta.open("w", encoding="utf-8") as out, stderr.open("w", encoding="utf-8") as err:
        proc = subprocess.run(cmd, stdout=out, stderr=err, text=True)
    try:
        m = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        m = {}
    payload = body.read_bytes() if body.exists() else b""
    prefix = payload[:4096].lstrip().lower()
    return {
        "catalog_id": name,
        "route": route,
        "url": url,
        "exit_code": proc.returncode,
        "response_code": int(m.get("response_code", 0) or 0),
        "url_effective": m.get("url_effective"),
        "remote_ip": m.get("remote_ip"),
        "content_type": m.get("content_type"),
        "body_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest() if payload else None,
        "html_like": prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<body" in prefix,
        "gzip_magic": payload[:2] == b"\x1f\x8b",
        "stderr_tail": stderr.read_text(encoding="utf-8", errors="replace")[-500:],
        "body_path": body.as_posix(),
    }


def main() -> int:
    root = Path(os.environ.get("PROBE_OUT", "/tmp/v06_fast_probe"))
    root.mkdir(parents=True, exist_ok=True)
    tasks: list[tuple[str, str, str]] = []
    for name, official, key in SOURCES:
        encoded = urllib.parse.quote(official, safe="")
        routes = {
            "official": official,
            "isomorphic": "https://cors.isomorphic-git.org/" + official,
            "allorigins": "https://api.allorigins.win/raw?url=" + encoded,
            "corsproxy": "https://corsproxy.io/?url=" + encoded,
            "codetabs": "https://api.codetabs.com/v1/proxy?quest=" + encoded,
            "cloudfront": "https://d2t2xxda3aznuq.cloudfront.net/ftp/" + key,
            "s3_ftp": "https://scedc-pds.s3.us-west-2.amazonaws.com/ftp/" + key,
            "s3_root": "https://scedc-pds.s3.us-west-2.amazonaws.com/" + key,
            "wayback_cdx": "https://web.archive.org/cdx/search/cdx?url=" + encoded + "&output=json&fl=timestamp,original,statuscode,mimetype,digest,length&filter=statuscode:200&collapse=digest",
        }
        tasks.extend((name, route, url) for route, url in routes.items())

    results: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=18) as pool:
        futures = [pool.submit(fetch, name, route, url, root) for name, route, url in tasks]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    grouped: dict[str, dict[str, object]] = {}
    for name, _, _ in SOURCES:
        rows = sorted((r for r in results if r["catalog_id"] == name), key=lambda r: str(r["route"]))
        digests: dict[str, list[str]] = {}
        for row in rows:
            if row["exit_code"] == 0 and row["response_code"] in {200, 206} and row["body_bytes"] and not row["html_like"]:
                digests.setdefault(str(row["sha256"]), []).append(str(row["route"]))
        grouped[name] = {"routes": rows, "digest_groups": digests}

    report = {
        "format": "KCH_HELICAL_V0_6_FAST_BYTE_ROUTE_PROBE_V1",
        "probed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "runner": {"run_id": os.environ.get("GITHUB_RUN_ID"), "sha": os.environ.get("GITHUB_SHA")},
        "sources": grouped,
    }
    (root / "FAST_PROBE_REPORT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
