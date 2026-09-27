from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SOURCES = [
    {
        "catalog_id": "CAHUILLA_SWARM_2016_2019",
        "url": "https://service.scedc.caltech.edu/ftp/cahuilla_swarm/out.growclust_cat",
        "relative_key": "cahuilla_swarm/out.growclust_cat",
        "kind": "text",
    },
    {
        "catalog_id": "RIDGECREST_QTM_2019",
        "url": "https://service.scedc.caltech.edu/ftp/QTMcatalog-ridgecrest/ridgecrest_qtm.tar.gz",
        "relative_key": "QTMcatalog-ridgecrest/ridgecrest_qtm.tar.gz",
        "kind": "gzip",
    },
    {
        "catalog_id": "CALMEX_BORDER_2012_2020",
        "url": "https://service.scedc.caltech.edu/ftp/calmex/out.hypoDD.reloc",
        "relative_key": "calmex/out.hypoDD.reloc",
        "kind": "text",
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def curl_fetch(url: str, stem: Path, timeout: int = 180) -> dict[str, object]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    body = stem.with_suffix(".body")
    headers = stem.with_suffix(".headers")
    meta = stem.with_suffix(".meta.json")
    stderr = stem.with_suffix(".stderr.txt")
    command = [
        "curl",
        "--location",
        "--retry", "2",
        "--retry-all-errors",
        "--retry-delay", "1",
        "--connect-timeout", "20",
        "--max-time", str(timeout),
        "--header", "Accept-Encoding: identity",
        "--dump-header", str(headers),
        "--output", str(body),
        "--write-out", "%{json}",
        url,
    ]
    with meta.open("w", encoding="utf-8") as mout, stderr.open("w", encoding="utf-8") as err:
        proc = subprocess.run(command, stdout=mout, stderr=err, text=True)
    try:
        curl_meta = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        curl_meta = {}
    payload = body.read_bytes() if body.exists() else b""
    prefix = payload[:4096].lstrip().lower()
    return {
        "url": url,
        "curl_exit_code": proc.returncode,
        "response_code": int(curl_meta.get("response_code", 0) or 0),
        "url_effective": curl_meta.get("url_effective"),
        "remote_ip": curl_meta.get("remote_ip"),
        "content_type": curl_meta.get("content_type"),
        "num_redirects": curl_meta.get("num_redirects"),
        "size_download": int(float(curl_meta.get("size_download", 0) or 0)),
        "body_bytes": len(payload),
        "body_sha256": hashlib.sha256(payload).hexdigest() if payload else None,
        "html_like": bool(prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<body" in prefix),
        "gzip_magic": payload[:2] == b"\x1f\x8b",
        "stderr_tail": stderr.read_text(encoding="utf-8", errors="replace")[-1000:],
        "body_path": body.as_posix(),
    }


def main() -> int:
    out = Path(os.environ.get("PROBE_OUT", "/tmp/helical_v06_byte_quorum_probe"))
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "format": "KCH_HELICAL_V0_6_BYTE_ROUTE_PROBE_V1",
        "probed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "runner": {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "sha": os.environ.get("GITHUB_SHA"),
            "ref": os.environ.get("GITHUB_REF"),
        },
        "sources": [],
    }

    for source in SOURCES:
        official = source["url"]
        encoded = urllib.parse.quote(official, safe="")
        key = source["relative_key"]
        routes: list[tuple[str, str]] = [
            ("official_direct", official),
            ("isomorphic_git_cors", "https://cors.isomorphic-git.org/" + official),
            ("allorigins_raw", "https://api.allorigins.win/raw?url=" + encoded),
            ("corsproxy_io", "https://corsproxy.io/?url=" + encoded),
            ("codetabs_proxy", "https://api.codetabs.com/v1/proxy?quest=" + encoded),
            ("cloudfront_guess", "https://d2t2xxda3aznuq.cloudfront.net/ftp/" + key),
            ("s3_virtual_ftp", "https://scedc-pds.s3.us-west-2.amazonaws.com/ftp/" + key),
            ("s3_virtual_root", "https://scedc-pds.s3.us-west-2.amazonaws.com/" + key),
            ("s3_path_ftp", "https://s3.us-west-2.amazonaws.com/scedc-pds/ftp/" + key),
            ("s3_path_root", "https://s3.us-west-2.amazonaws.com/scedc-pds/" + key),
        ]
        source_dir = out / source["catalog_id"]
        results: list[dict[str, object]] = []
        for route_name, route_url in routes:
            result = curl_fetch(route_url, source_dir / route_name)
            result["route"] = route_name
            results.append(result)

        cdx_url = (
            "https://web.archive.org/cdx/search/cdx?url="
            + urllib.parse.quote(official, safe="")
            + "&output=json&fl=timestamp,original,statuscode,mimetype,digest,length&filter=statuscode:200&collapse=digest"
        )
        cdx_result = curl_fetch(cdx_url, source_dir / "wayback_cdx", timeout=120)
        cdx_result["route"] = "wayback_cdx"
        results.append(cdx_result)
        captures: list[dict[str, object]] = []
        cdx_body_path = Path(str(cdx_result["body_path"]))
        if cdx_result["curl_exit_code"] == 0 and cdx_result["response_code"] == 200 and cdx_body_path.exists():
            try:
                rows = json.loads(cdx_body_path.read_text(encoding="utf-8"))
                if isinstance(rows, list) and len(rows) > 1:
                    header = rows[0]
                    for row in rows[1:][-3:]:
                        rec = dict(zip(header, row))
                        timestamp = rec.get("timestamp")
                        original = rec.get("original")
                        if timestamp and original:
                            snap_url = f"https://web.archive.org/web/{timestamp}id_/{original}"
                            snap = curl_fetch(snap_url, source_dir / f"wayback_{timestamp}", timeout=300)
                            snap.update({"route": "wayback_snapshot", "timestamp": timestamp, "cdx": rec})
                            captures.append(snap)
            except Exception as exc:
                captures.append({"route": "wayback_parse_error", "error": repr(exc)})

        valid_bodies = [
            r for r in results + captures
            if r.get("curl_exit_code") == 0
            and int(r.get("response_code", 0)) in {200, 206}
            and int(r.get("body_bytes", 0)) > 0
            and not bool(r.get("html_like"))
        ]
        digest_groups: dict[str, list[str]] = {}
        for record in valid_bodies:
            digest = str(record.get("body_sha256"))
            digest_groups.setdefault(digest, []).append(str(record.get("route")))

        report["sources"].append(
            {
                **source,
                "routes": results,
                "wayback_captures": captures,
                "valid_digest_groups": digest_groups,
            }
        )

    report_path = out / "BYTE_ROUTE_PROBE_REPORT.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    all_files = sorted(p for p in out.rglob("*") if p.is_file())
    (out / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(p)}  {p.relative_to(out).as_posix()}\n" for p in all_files),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
