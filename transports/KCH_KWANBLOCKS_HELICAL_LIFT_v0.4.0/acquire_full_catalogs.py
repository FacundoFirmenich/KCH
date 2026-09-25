#!/usr/bin/env python3
"""Acquire exact provider bytes for the frozen KwanBlocks v0.4 seismic gate.

This program has zero execution authority outside its GitHub Actions workspace. It
uses a fixed source allow-list, preserves provider bytes, computes cryptographic
receipts, validates the four SCEDC HypoDD catalogs against the protocol frozen
before acquisition, and separately acquires DOI-backed external controls.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROTOCOL = ROOT / "spec" / "SEISMIC_HELICAL_PANEL_GATE_V0_4.json"
OUT = ROOT / "out"
RAW = OUT / "raw"
SUPPLEMENTAL = OUT / "supplemental_external_controls"
EXPECTED_PROTOCOL_SHA256 = "03e2bc4cf92ab2e74aff7de97f7588360ae441f0fbd35fe8a2d440026840ff89"
MAX_BYTES = 50_000_000
USER_AGENT = "KCH-KwanBlocks-Helical-Lift/0.4 acquisition-only (+https://github.com/FacundoFirmenich/KCH)"

SUPPLEMENTAL_SOURCES = [
    {
        "name": "TEWKSBURY_RELOCATED",
        "url": "https://zenodo.org/records/14058325/files/catalog_Tewksbury_aftershocks_relocated.csv?download=1",
        "filename": "catalog_Tewksbury_aftershocks_relocated.csv",
        "doi": "10.5281/zenodo.14058325",
        "expected_md5": "8370e345141206cfafc7a0bf43ad3029",
        "expected_lines": 1754,
        "role": "EXTERNAL_RELOCATED_CATALOG_CONTROL",
    },
    {
        "name": "RIO_GRANDE_RIFT_HYPODD",
        "url": "https://zenodo.org/records/7806689/files/hypodDD_RGR.csv?download=1",
        "filename": "hypodDD_RGR.csv",
        "doi": "10.5281/zenodo.7806689",
        "expected_md5": "bf36b2858d0e8460a07c6b2de913cc92",
        "expected_lines": 715,
        "role": "EXTERNAL_HYPODD_CONTROL",
    },
    {
        "name": "ECUADOR_SEAMOUNT_HYPODD",
        "url": "https://zenodo.org/records/16988559/files/hypoDD_seamount_reloc_GRL.csv?download=1",
        "filename": "hypoDD_seamount_reloc_GRL.csv",
        "doi": "10.5281/zenodo.16988559",
        "expected_md5": "6ae519fd31c34075ad152fd73b7767d4",
        "expected_lines": 1214,
        "role": "EXTERNAL_HYPODD_CONTROL",
    },
    {
        "name": "CENTRAL_ITALY_RELATIVE_LOCATIONS",
        "url": "https://zenodo.org/records/3712731/files/catalog_relative_locs.csv?download=1",
        "filename": "catalog_relative_locs.csv",
        "doi": "10.5281/zenodo.3712731",
        "expected_md5": "483fb9639f4c6d1fdd2b58fb29361293",
        "expected_lines": 33983,
        "role": "LARGE_EXTERNAL_HYPODD_CONTROL",
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def download_exact(url: str, retries: int = 4) -> tuple[bytes, dict[str, str], str]:
    context = ssl.create_default_context()
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/octet-stream,text/plain,text/csv;q=0.9,*/*;q=0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120, context=context) as response:
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise RuntimeError(f"download exceeds {MAX_BYTES} bytes")
                    chunks.append(chunk)
                data = b"".join(chunks)
                headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
                final_url = response.geturl()
                if not data:
                    raise RuntimeError("provider returned an empty body")
                return data, headers, final_url
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))
    assert last_error is not None
    raise last_error


def line_count(data: bytes) -> int:
    return len(data.splitlines())


def validate_scedc(data: bytes, expected_lines: int) -> dict[str, Any]:
    lines = data.splitlines()
    nonblank = [line for line in lines if line.strip()]
    field_counts: dict[str, int] = {}
    invalid_examples: list[dict[str, Any]] = []
    for index, raw_line in enumerate(nonblank, start=1):
        try:
            text = raw_line.decode("ascii")
        except UnicodeDecodeError:
            text = raw_line.decode("utf-8", errors="replace")
        count = len(text.split())
        field_counts[str(count)] = field_counts.get(str(count), 0) + 1
        if count != 24 and len(invalid_examples) < 5:
            invalid_examples.append({"line": index, "field_count": count, "text": text[:240]})
    return {
        "line_count": len(lines),
        "nonblank_line_count": len(nonblank),
        "expected_line_count": expected_lines,
        "line_count_matches": len(lines) == expected_lines,
        "field_count_histogram": field_counts,
        "all_nonblank_rows_have_24_fields": not invalid_examples and field_counts.get("24", 0) == len(nonblank),
        "invalid_examples": invalid_examples,
        "validation_pass": (
            len(lines) == expected_lines
            and len(nonblank) == expected_lines
            and not invalid_examples
            and field_counts.get("24", 0) == len(nonblank)
        ),
    }


def acquire_one(source: dict[str, Any], destination: Path, scedc: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "name": source["name"],
        "role": source["role"],
        "source_url": source["source_url"] if scedc else source["url"],
        "status": "ERROR",
    }
    url = record["source_url"]
    try:
        data, headers, final_url = download_exact(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        record.update(
            {
                "status": "DOWNLOADED",
                "local_path": destination.relative_to(OUT).as_posix(),
                "bytes": len(data),
                "lines": line_count(data),
                "sha256": sha256_bytes(data),
                "md5": md5_bytes(data),
                "final_url": final_url,
                "http_headers": {
                    key: headers[key]
                    for key in ("content-type", "content-length", "etag", "last-modified", "content-disposition")
                    if key in headers
                },
            }
        )
        if scedc:
            validation = validate_scedc(data, int(source["provider_expected_lines"]))
            record["validation"] = validation
            record["status"] = "PASS" if validation["validation_pass"] else "VALIDATION_FAILED"
        else:
            expected_md5 = str(source["expected_md5"])
            expected_lines = int(source["expected_lines"])
            record.update(
                {
                    "doi": source["doi"],
                    "expected_md5": expected_md5,
                    "expected_lines": expected_lines,
                    "md5_matches": record["md5"] == expected_md5,
                    "line_count_matches": record["lines"] == expected_lines,
                }
            )
            record["status"] = "PASS" if record["md5_matches"] and record["line_count_matches"] else "VALIDATION_FAILED"
    except Exception as exc:  # receipt must survive transport failure
        record.update({"status": "DOWNLOAD_FAILED", "error_type": type(exc).__name__, "error": str(exc)})
    return record


def deterministic_zip(source_dir: Path, destination: Path) -> None:
    fixed = (2026, 9, 25, 18, 5, 8)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in source_dir.rglob("*") if p.is_file() and p != destination):
            rel = path.relative_to(source_dir).as_posix()
            info = zipfile.ZipInfo(rel, fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    protocol_bytes = PROTOCOL.read_bytes()
    protocol_sha = sha256_bytes(protocol_bytes)
    if protocol_sha != EXPECTED_PROTOCOL_SHA256:
        raise SystemExit(f"frozen protocol hash mismatch: {protocol_sha}")
    protocol = json.loads(protocol_bytes)
    if protocol.get("plan_id") != "shp4:9d449846dc2397c412a7bf52e920321c76786b996396fe4854c388ae1644ee9f":
        raise SystemExit("frozen plan_id mismatch")

    if OUT.exists():
        shutil.rmtree(OUT)
    RAW.mkdir(parents=True)
    SUPPLEMENTAL.mkdir(parents=True)
    (OUT / "spec").mkdir(parents=True)
    shutil.copy2(PROTOCOL, OUT / "spec" / PROTOCOL.name)

    started = dt.datetime.now(dt.timezone.utc)
    scedc_records: list[dict[str, Any]] = []
    for source in protocol["datasets"]:
        scedc_records.append(acquire_one(source, RAW / Path(source["local_path"]).name, scedc=True))

    supplemental_records: list[dict[str, Any]] = []
    for source in SUPPLEMENTAL_SOURCES:
        supplemental_records.append(acquire_one(source, SUPPLEMENTAL / source["filename"], scedc=False))

    scedc_pass = all(item["status"] == "PASS" for item in scedc_records)
    supplemental_pass_count = sum(item["status"] == "PASS" for item in supplemental_records)
    completed = dt.datetime.now(dt.timezone.utc)

    receipt: dict[str, Any] = {
        "format": "KCH_KWANBLOCKS_HELICAL_ACQUISITION_RECEIPT_V1",
        "version": "0.4.0",
        "plan_id": protocol["plan_id"],
        "protocol_sha256": protocol_sha,
        "protocol_lock_time_utc": protocol["lock_time_utc"],
        "execution_started_utc": started.isoformat().replace("+00:00", "Z"),
        "execution_completed_utc": completed.isoformat().replace("+00:00", "Z"),
        "exact_provider_bytes_preserved": True,
        "scedc_gate_status": "PASS" if scedc_pass else "BLOCKED_OR_FAILED",
        "scedc_catalogs": scedc_records,
        "supplemental_controls_status": {
            "pass_count": supplemental_pass_count,
            "total": len(supplemental_records),
            "all_pass": supplemental_pass_count == len(supplemental_records),
        },
        "supplemental_controls": supplemental_records,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "github_repository": os.environ.get("GITHUB_REPOSITORY"),
            "github_sha": os.environ.get("GITHUB_SHA"),
            "github_ref": os.environ.get("GITHUB_REF"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "runner_name": os.environ.get("RUNNER_NAME"),
            "runner_os": os.environ.get("RUNNER_OS"),
        },
        "claim_ceiling": protocol["claim_ceiling"],
        "next_action": "EXECUTE_FROZEN_PANEL_ONLY_IF_SCEDC_GATE_STATUS_PASS",
    }
    (OUT / "ACQUISITION_RECEIPT.json").write_bytes(canonical_json(receipt))

    checksum_rows: list[str] = []
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt"):
        checksum_rows.append(f"{sha256_bytes(path.read_bytes())}  {path.relative_to(OUT).as_posix()}")
    (OUT / "SHA256SUMS.txt").write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")

    summary = [
        "# KwanBlocks Helical Lift v0.4 acquisition gate",
        "",
        f"- Frozen plan: `{protocol['plan_id']}`",
        f"- Frozen protocol SHA-256: `{protocol_sha}`",
        f"- SCEDC exact-byte acquisition: **{'PASS' if scedc_pass else 'BLOCKED_OR_FAILED'}**",
        f"- DOI-backed controls acquired and verified: **{supplemental_pass_count}/{len(supplemental_records)}**",
        "- Authority: `NONE`",
        "- Promotion: `BLOCKED`",
        "- Canonicalization: `BLOCKED`",
        "",
        "The acquisition receipt is evidence of transport and byte custody only; it is not evidence of helicoidal geometry or physical helicity.",
        "",
    ]
    (OUT / "ACQUISITION_GATE.md").write_text("\n".join(summary), encoding="utf-8")

    bundle = OUT / "KCH_KWANBLOCKS_HELICAL_LIFT_v0_4_0_ACQUISITION.zip"
    deterministic_zip(OUT, bundle)
    bundle_sha = sha256_bytes(bundle.read_bytes())
    (OUT / "BUNDLE_SHA256.txt").write_text(f"{bundle_sha}  {bundle.name}\n", encoding="utf-8")

    print(json.dumps({
        "scedc_gate_status": receipt["scedc_gate_status"],
        "supplemental_pass": supplemental_pass_count,
        "supplemental_total": len(supplemental_records),
        "bundle": str(bundle),
        "bundle_sha256": bundle_sha,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
