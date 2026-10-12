from __future__ import annotations

import argparse
import calendar
import importlib.util
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd


def load_base(path: Path):
    spec = importlib.util.spec_from_file_location("kch_mhd_solar_census_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base census module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-script", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    base = load_base(args.base_script)

    def query_year_monthly(client: Any, year: int, out: Path):
        annual_path = out / "jsoc_raw" / f"sharp_cea_6h_{year}.csv"
        if annual_path.exists() and annual_path.stat().st_size > 0:
            frame = pd.read_csv(annual_path, low_memory=False)
            return frame, {
                "year": year,
                "transport": "REUSED_EXACT_FROM_PREDECESSOR_ARTIFACT",
                "series": base.JSOC_SERIES,
                "keys": base.KEYS,
                "rows": int(len(frame)),
                "columns": list(frame.columns),
                "bytes": annual_path.stat().st_size,
                "sha256": base.sha256_file(annual_path),
                "monthly_receipts": [],
            }

        monthly_frames = []
        receipts = []
        first_month = 5 if year == 2010 else 1
        last_month = 12
        for month in range(first_month, last_month + 1):
            if year == 2025 and month > 12:
                break
            last_day = calendar.monthrange(year, month)[1]
            start = pd.Timestamp(year=year, month=month, day=1, hour=0, tz="UTC")
            end = pd.Timestamp(year=year, month=month, day=last_day, hour=18, tz="UTC")
            if start < base.START:
                start = base.START
            if end > base.END:
                end = base.END
            if start > end:
                continue
            qstart = start.strftime("%Y.%m.%d_%H:%M_TAI")
            qend = end.strftime("%Y.%m.%d_%H:%M_TAI")
            qstr = f"{base.JSOC_SERIES}[][{qstart}-{qend}@6h]"
            last_error = None
            frame = None
            for attempt in range(1, 6):
                try:
                    frame = client.query(qstr, key=",".join(base.KEYS)).reset_index(drop=False)
                    break
                except Exception as exc:
                    last_error = repr(exc)
                    if attempt == 5:
                        raise RuntimeError(f"JSOC monthly query failed after retries: {qstr}: {last_error}") from exc
                    time.sleep(5.0 * attempt)
            assert frame is not None
            month_path = out / "jsoc_raw_monthly" / f"sharp_cea_6h_{year}_{month:02d}.csv"
            month_path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(month_path, index=False, lineterminator="\n")
            monthly_frames.append(frame)
            receipts.append({
                "year": year,
                "month": month,
                "query": qstr,
                "rows": int(len(frame)),
                "bytes": month_path.stat().st_size,
                "sha256": base.sha256_file(month_path),
            })
            time.sleep(0.5)

        if not monthly_frames:
            raise RuntimeError(f"no monthly JSOC frames for {year}")
        annual = pd.concat(monthly_frames, ignore_index=True)
        if "T_REC" in annual.columns:
            sort_columns = [column for column in ["T_REC", "HARPNUM"] if column in annual.columns]
            annual = annual.sort_values(sort_columns, kind="stable").reset_index(drop=True)
        annual_path.parent.mkdir(parents=True, exist_ok=True)
        annual.to_csv(annual_path, index=False, lineterminator="\n")
        return annual, {
            "year": year,
            "transport": "MONTHLY_CHUNKED_WITH_RETRY",
            "series": base.JSOC_SERIES,
            "keys": base.KEYS,
            "rows": int(len(annual)),
            "columns": list(annual.columns),
            "bytes": annual_path.stat().st_size,
            "sha256": base.sha256_file(annual_path),
            "monthly_receipts": receipts,
        }

    base.query_year = query_year_monthly
    sys.argv = [str(args.base_script), "--out", str(args.out)]
    return int(base.main())


if __name__ == "__main__":
    raise SystemExit(main())
