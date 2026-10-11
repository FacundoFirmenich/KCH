from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import hashlib
import io
import json
import os
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

BASE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/detail/{event_id}.geojson"
CONCURRENCY = 24
RETRIES = 5


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def product_sort_key(product: dict[str, Any]) -> tuple[int, int, str, str]:
    return (
        int(product.get("preferredWeight") or 0),
        int(product.get("updateTime") or 0),
        str(product.get("source") or ""),
        str(product.get("id") or ""),
    )


def float_property(properties: dict[str, Any], key: str) -> float | None:
    value = properties.get(key)
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def select_product(root: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    products = root.get("properties", {}).get("products", {}) or {}
    for product_type in ["focal-mechanism", "moment-tensor"]:
        candidates = [
            item
            for item in products.get(product_type, []) or []
            if str(item.get("status") or "").upper() != "DELETE"
        ]
        valid: list[dict[str, Any]] = []
        for item in candidates:
            props = item.get("properties", {}) or {}
            required = [
                "nodal-plane-1-strike",
                "nodal-plane-1-dip",
                "nodal-plane-1-rake",
                "nodal-plane-2-strike",
                "nodal-plane-2-dip",
                "nodal-plane-2-rake",
            ]
            if all(float_property(props, key) is not None for key in required):
                valid.append(item)
        if valid:
            return product_type, sorted(valid, key=product_sort_key, reverse=True)[0]
    return None, None


async def fetch_one(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, event_id: str, raw_root: Path) -> dict[str, Any]:
    url = BASE.format(event_id=event_id)
    error = None
    async with semaphore:
        for attempt in range(1, RETRIES + 1):
            try:
                async with session.get(url, allow_redirects=True) as response:
                    body = await response.read()
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}: {body[:200]!r}")
                    root = json.loads(body.decode("utf-8"))
                    if str(root.get("id")) != event_id:
                        raise RuntimeError(f"event ID mismatch {root.get('id')!r}")
                    product_type, product = select_product(root)
                    raw_path = raw_root / event_id[:2] / f"{event_id}.geojson"
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_path.write_bytes(body)
                    receipt: dict[str, Any] = {
                        "event_id": event_id,
                        "url": url,
                        "effective_url": str(response.url),
                        "http_status": response.status,
                        "content_type": response.headers.get("Content-Type"),
                        "etag": response.headers.get("ETag"),
                        "last_modified": response.headers.get("Last-Modified"),
                        "bytes": len(body),
                        "sha256": sha256_bytes(body),
                        "product_type": product_type,
                        "parse_status": "PASS" if product is not None else "NO_VALID_DIRECTIONAL_PRODUCT",
                    }
                    if product is not None:
                        props = product.get("properties", {}) or {}
                        receipt.update(
                            {
                                "product_id": product.get("id"),
                                "product_source": product.get("source"),
                                "product_status": product.get("status"),
                                "product_update_time": product.get("updateTime"),
                                "product_preferred_weight": product.get("preferredWeight"),
                                "np1_strike": float_property(props, "nodal-plane-1-strike"),
                                "np1_dip": float_property(props, "nodal-plane-1-dip"),
                                "np1_rake": float_property(props, "nodal-plane-1-rake"),
                                "np2_strike": float_property(props, "nodal-plane-2-strike"),
                                "np2_dip": float_property(props, "nodal-plane-2-dip"),
                                "np2_rake": float_property(props, "nodal-plane-2-rake"),
                                "station_count": float_property(props, "station-count"),
                                "azimuthal_gap": float_property(props, "azimuthal-gap"),
                                "misfit": float_property(props, "misfit"),
                                "review_status": props.get("review-status"),
                            }
                        )
                    return receipt
            except Exception as exc:
                error = repr(exc)
                if attempt < RETRIES:
                    await asyncio.sleep(min(30.0, 1.5 ** attempt))
        return {
            "event_id": event_id,
            "url": url,
            "parse_status": "FETCH_FAILED",
            "error": error,
        }


async def acquire(event_ids: list[str], raw_root: Path) -> list[dict[str, Any]]:
    timeout = aiohttp.ClientTimeout(total=180, connect=30, sock_read=120)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY, ttl_dns_cache=300)
    headers = {"User-Agent": "KCH-Helical-v1.1-terminal-seismic-gate/2026-10-11"}
    semaphore = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers) as session:
        tasks = [fetch_one(session, semaphore, event_id, raw_root) for event_id in event_ids]
        output: list[dict[str, Any]] = []
        for index, future in enumerate(asyncio.as_completed(tasks), start=1):
            output.append(await future)
            if index % 250 == 0:
                print(f"acquired {index}/{len(tasks)}", flush=True)
        return output


def deterministic_tar_gz(raw_root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw_handle:
        with gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0, compresslevel=6) as gzip_handle:
            with tarfile.open(fileobj=gzip_handle, mode="w") as archive:
                for path in sorted(raw_root.rglob("*.geojson")):
                    relative = path.relative_to(raw_root).as_posix()
                    payload = path.read_bytes()
                    info = tarfile.TarInfo(relative)
                    info.size = len(payload)
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mode = 0o644
                    archive.addfile(info, io.BytesIO(payload))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    lock_path = args.network_root / "SEISMIC_FULL_NETWORK_LOCK_V1_1.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("status") != "LOCKED_BEFORE_DIRECTIONAL_PRODUCT_ACCESS":
        raise RuntimeError("network is not in the required pre-directional locked state")
    if lock.get("directional_products_accessed") is not False or lock.get("directional_opening_authorized") is not True:
        raise RuntimeError("directional opening is not authorized")
    selected_path = args.network_root / "SELECTED_EVENT_IDS_AND_SPLITS.csv"
    selected = pd.read_csv(selected_path, low_memory=False)
    selected = selected[selected["region"].isin(lock["selected_cohorts"])].copy()
    selected["event_id"] = selected["event_id"].astype(str)
    if selected["event_id"].duplicated().any():
        duplicates = selected.loc[selected["event_id"].duplicated(), "event_id"].tolist()[:20]
        raise RuntimeError(f"duplicate selected event IDs: {duplicates}")
    event_ids = sorted(selected["event_id"].tolist())
    raw_root = args.out / "raw_details"
    receipts = asyncio.run(acquire(event_ids, raw_root))
    receipt_frame = pd.DataFrame(receipts).sort_values("event_id", kind="stable")
    joined = selected.merge(receipt_frame, on="event_id", how="left", validate="one_to_one")
    receipt_path = args.out / "COMCAT_DETAIL_RECEIPTS.csv.gz"
    receipt_frame.to_csv(receipt_path, index=False, compression="gzip")
    mechanisms_path = args.out / "SELECTED_DIRECTIONAL_MECHANISMS.csv.gz"
    joined.to_csv(mechanisms_path, index=False, compression="gzip")
    tar_path = args.out / "COMCAT_DETAIL_BODIES.tar.gz"
    deterministic_tar_gz(raw_root, tar_path)
    success = joined["parse_status"].eq("PASS")
    by_region = []
    for region, group in joined.groupby("region", sort=True):
        test = group[group["split"] == "TEST"]
        by_region.append(
            {
                "region": region,
                "selected_events": int(len(group)),
                "parsed_directional_events": int(group["parse_status"].eq("PASS").sum()),
                "directional_coverage": float(group["parse_status"].eq("PASS").mean()),
                "sealed_test_events": int(len(test)),
                "sealed_test_parsed_directional_events": int(test["parse_status"].eq("PASS").sum()),
                "sealed_test_directional_coverage": float(test["parse_status"].eq("PASS").mean()) if len(test) else 0.0,
            }
        )
    all_fetch_complete = bool(joined["parse_status"].ne("FETCH_FAILED").all())
    coverage_gate = all(row["directional_coverage"] >= 0.75 and row["sealed_test_parsed_directional_events"] >= 200 for row in by_region)
    body = {
        "format": "KCH_SEISMIC_DIRECTIONAL_ACQUISITION_V1_1",
        "network_lock_id": lock["network_lock_id"],
        "network_lock_sha256": sha256_file(lock_path),
        "selected_event_file_sha256": sha256_file(selected_path),
        "acquired_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "selected_event_count": len(event_ids),
        "successful_directional_parse_count": int(success.sum()),
        "fetch_failures": int(joined["parse_status"].eq("FETCH_FAILED").sum()),
        "no_valid_product": int(joined["parse_status"].eq("NO_VALID_DIRECTIONAL_PRODUCT").sum()),
        "cohorts": by_region,
        "all_http_acquisitions_complete": all_fetch_complete,
        "directional_coverage_gate_pass": coverage_gate,
        "scientific_model_execution_performed": False,
        "raw_body_archive": {"path": tar_path.name, "bytes": tar_path.stat().st_size, "sha256": sha256_file(tar_path)},
        "receipt_file": {"path": receipt_path.name, "sha256": sha256_file(receipt_path)},
        "mechanism_file": {"path": mechanisms_path.name, "sha256": sha256_file(mechanisms_path)},
        "source_substitution": False,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    body["directional_acquisition_id"] = "s11dir:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(args.out / "SEISMIC_DIRECTIONAL_ACQUISITION_V1_1.json", body)
    print(json.dumps(body, indent=2, sort_keys=True))
    for path in sorted(raw_root.rglob("*.geojson")):
        path.unlink()
    for directory in sorted((path for path in raw_root.rglob("*") if path.is_dir()), reverse=True):
        directory.rmdir()
    raw_root.rmdir()
    return 0 if all_fetch_complete and coverage_gate else 3


if __name__ == "__main__":
    raise SystemExit(main())
