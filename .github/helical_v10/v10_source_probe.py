from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

OUT = Path(os.environ.get("V10_OUT", "/tmp/kch_helical_v10_probe"))
OUT.mkdir(parents=True, exist_ok=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def get(url: str, **kwargs: Any) -> requests.Response:
    headers = {"User-Agent": "KCH-Helical-v1.0-source-probe/2026-10-11"}
    headers.update(kwargs.pop("headers", {}))
    response = requests.get(url, headers=headers, timeout=120, **kwargs)
    response.raise_for_status()
    return response


def probe_jsoc() -> dict[str, Any]:
    import drms

    client = drms.Client()
    keys = [
        "HARPNUM", "T_REC", "NOAA_AR", "NOAA_NUM", "NOAA_ARS", "QUALITY",
        "USFLUX", "MEANJZH", "ABSNJZH", "TOTUSJH", "MEANALP", "MEANSHR",
        "SHRGT45", "R_VALUE", "TOTUSJZ", "TOTPOT", "AREA_ACR", "LAT_FWT", "LON_FWT",
    ]
    available = set(client.keys("hmi.sharp_cea_720s"))
    selected_keys = [k for k in keys if k in available]
    candidates = [
        "hmi.sharp_cea_720s[][2024.01.01_00:00_TAI/24h@6h]",
        "hmi.sharp_cea_720s[][2024.01.01_00:00_TAI-2024.01.02_00:00_TAI@6h]",
        "hmi.sharp_cea_720s[][2024.01.01_00:00_TAI/1d]",
        "hmi.sharp_cea_720s[][2024.01.01_00:00_TAI]",
    ]
    attempts = []
    result_df = None
    winner = None
    for qstr in candidates:
        try:
            frame = client.query(qstr, key=",".join(selected_keys))
            attempts.append({"query": qstr, "status": "PASS", "rows": int(len(frame)), "columns": list(frame.columns)})
            if len(frame) > 0 and result_df is None:
                result_df = frame
                winner = qstr
        except Exception as exc:
            attempts.append({"query": qstr, "status": "FAIL", "error": repr(exc)})
    if result_df is None:
        raise RuntimeError(f"no JSOC probe query succeeded with rows: {attempts}")
    sample_path = OUT / "jsoc_probe_sample.csv"
    result_df.to_csv(sample_path, index=True)
    return {
        "series": "hmi.sharp_cea_720s",
        "selected_keys": selected_keys,
        "available_key_count": len(available),
        "query_attempts": attempts,
        "winning_query": winner,
        "sample_rows": int(len(result_df)),
        "sample_sha256": sha256_bytes(sample_path.read_bytes()),
    }


def probe_goes_flare_report() -> dict[str, Any]:
    base = "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/"
    listing = get(base).content
    (OUT / "goes_flare_listing.html").write_bytes(listing)
    names = sorted(set(re.findall(rb'sci_xrsf-l2-flrpt_geo_s\d+_e\d+_v[\d-]+\.csv', listing)))
    if not names:
        raise RuntimeError("mission-length GOES flare CSV not found in official listing")
    selected = names[-1].decode("ascii")
    response = get(base + selected)
    body = response.content
    path = OUT / selected
    path.write_bytes(body)
    frame = pd.read_csv(path)
    summary = {
        "official_listing_url": base,
        "listing_bytes": len(listing),
        "listing_sha256": sha256_bytes(listing),
        "selected_file": selected,
        "selected_url": base + selected,
        "selected_bytes": len(body),
        "selected_sha256": sha256_bytes(body),
        "rows": int(len(frame)),
        "columns": list(frame.columns),
    }
    for column in ["flare_class", "active_region", "time", "start_time", "end_time"]:
        if column in frame.columns:
            summary[f"non_null_{column}"] = int(frame[column].notna().sum())
    return summary


REGIONS = {
    "CALIFORNIA_STATEWIDE": (32.0, -125.0, 42.2, -113.5),
    "BAY_AREA": (36.5, -123.5, 38.8, -120.5),
    "PARKFIELD_CENTRAL_SAF": (35.0, -121.5, 36.7, -119.3),
    "MENDOCINO_TRIPLE_JUNCTION": (39.0, -126.0, 42.0, -122.0),
    "NORTHERN_WALKER_LANE": (36.5, -120.5, 40.5, -116.0),
    "SOUTHERN_CALIFORNIA": (32.0, -121.0, 36.5, -113.5),
}


def comcat_count(params: dict[str, Any]) -> tuple[int, bytes, str]:
    url = "https://earthquake.usgs.gov/fdsnws/event/1/count"
    response = get(url, params=params)
    body = response.content
    return int(body.decode("ascii").strip()), body, response.url


def probe_comcat() -> dict[str, Any]:
    root = OUT / "comcat_counts"
    root.mkdir(exist_ok=True)
    rows: list[dict[str, Any]] = []
    for region, (minlat, minlon, maxlat, maxlon) in REGIONS.items():
        for producttype in ["focal-mechanism", "moment-tensor"]:
            for year in range(2022, 2027):
                end = f"{year+1}-01-01" if year < 2026 else "2026-10-11"
                params = {
                    "starttime": f"{year}-01-01",
                    "endtime": end,
                    "minlatitude": minlat,
                    "minlongitude": minlon,
                    "maxlatitude": maxlat,
                    "maxlongitude": maxlon,
                    "producttype": producttype,
                    "orderby": "time-asc",
                }
                count, body, effective_url = comcat_count(params)
                filename = f"{region}__{producttype}__{year}.txt"
                (root / filename).write_bytes(body)
                rows.append({
                    "region": region,
                    "producttype": producttype,
                    "year": year,
                    "count": count,
                    "effective_url": effective_url,
                    "body_sha256": sha256_bytes(body),
                })
    path = OUT / "comcat_count_census.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return {
        "date_window": ["2022-01-01", "2026-10-11"],
        "regions": REGIONS,
        "rows": len(rows),
        "csv_sha256": sha256_bytes(path.read_bytes()),
        "totals_by_region_product": pd.DataFrame(rows).groupby(["region", "producttype"])["count"].sum().to_dict(),
    }


def main() -> int:
    report: dict[str, Any] = {
        "format": "KCH_HELICAL_V1_0_SOURCE_PROBE",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "runner": {
            "repository": os.getenv("GITHUB_REPOSITORY"),
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "sha": os.getenv("GITHUB_SHA"),
        },
        "results": {},
        "failures": {},
    }
    for name, function in [
        ("jsoc_sharp", probe_jsoc),
        ("goes_flare_report", probe_goes_flare_report),
        ("comcat_post2021", probe_comcat),
    ]:
        try:
            report["results"][name] = function()
        except Exception as exc:
            report["failures"][name] = {"error": repr(exc), "traceback": traceback.format_exc()}
    report["all_probes_pass"] = not report["failures"]
    write_json(OUT / "SOURCE_PROBE_REPORT.json", report)
    files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt")
    (OUT / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256_bytes(path.read_bytes())}  {path.relative_to(OUT).as_posix()}\n" for path in files),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if report["all_probes_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
