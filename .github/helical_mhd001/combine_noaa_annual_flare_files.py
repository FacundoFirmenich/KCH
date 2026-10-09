from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_HEADER_FIELDS = {"start_time", "flare_class", "active_region"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def find_header(lines: list[bytes], name: str) -> tuple[int, bytes, tuple[str, ...]]:
    for index, raw in enumerate(lines[:100]):
        text = raw.decode("utf-8-sig", errors="strict").strip("\r\n")
        fields = tuple(field.strip() for field in text.split(","))
        if REQUIRED_HEADER_FIELDS.issubset(set(fields)):
            return index, raw, fields
    raise RuntimeError(f"{name}: no header containing {sorted(REQUIRED_HEADER_FIELDS)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    parser.add_argument("--years", nargs="+", required=True, type=int)
    args = parser.parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_manifest.parent.mkdir(parents=True, exist_ok=True)

    first_fields: tuple[str, ...] | None = None
    first_header: bytes | None = None
    records: list[dict[str, Any]] = []
    with args.output_csv.open("wb") as destination:
        for sequence, year in enumerate(sorted(args.years)):
            name = f"sci_xrsf-l2-flrpt_geo_y{year}_v1-0-1.csv"
            path = args.source_dir / name
            payload = path.read_bytes()
            if not payload:
                raise RuntimeError(f"{name}: empty exact source body")
            prefix = payload[:4096].lstrip().lower()
            if prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<body" in prefix:
                raise RuntimeError(f"{name}: HTML body rejected")
            lines = payload.splitlines(keepends=True)
            header_index, raw_header, fields = find_header(lines, name)
            normalized_header = tuple(field.lstrip("\ufeff") for field in fields)
            if first_fields is None:
                first_fields = normalized_header
                first_header = ",".join(normalized_header).encode("utf-8") + b"\n"
                destination.write(first_header)
            elif normalized_header != first_fields:
                raise RuntimeError(f"{name}: annual schema drift")
            data_lines = lines[header_index + 1 :]
            if data_lines and data_lines[-1] and not data_lines[-1].endswith((b"\n", b"\r")):
                data_lines[-1] += b"\n"
            for line in data_lines:
                if line.strip():
                    destination.write(line)
            records.append(
                {
                    "year": year,
                    "file": name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                    "header_line_index": header_index,
                    "header_fields": list(normalized_header),
                    "nonempty_data_line_count": sum(1 for line in data_lines if line.strip()),
                }
            )

    body = {
        "format": "KCH_MHD001_NOAA_ANNUAL_SOURCE_MANIFEST",
        "source_resolution_id": "mhd001labelsource:88504ec15ade35820b339a04d23f2090ed502c96e13dfb54dd0ab6e14da29ef4",
        "years": sorted(args.years),
        "sources": records,
        "combination_rule": "IDENTICAL_HEADER_REQUIRED_KEEP_FIRST_HEADER_APPEND_NONEMPTY_DATA_ROWS_IN_ASCENDING_YEAR",
        "combined_csv": {
            "file": args.output_csv.name,
            "bytes": args.output_csv.stat().st_size,
            "sha256": sha256(args.output_csv),
        },
        "source_bytes_modified": False,
        "combined_file_is_derived": True,
        "authority_ceiling": "NONE",
    }
    body["manifest_id"] = "mhd001annual:" + hashlib.sha256(canonical(body)).hexdigest()
    args.output_manifest.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
