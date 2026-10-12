#!/usr/bin/env python3
"""Independent, exhaustive blind code corroboration; never grants eligibility.

Freeze a contract before inspecting joined results. Source labels are never
written into the mechanism data. A missing, ambiguous or conflicting record
keeps this corroboration on HOLD. Uses no pickle or directional fields.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

import numpy as np

SNAPSHOTS = {
    "NC": ("NCEDC/NCSS-catalogs", "77d864e102b817b8662bd707f39ad34dd069cc97", "EHP_CSV", "ehpcsv"),
    "SC": ("SCEDC/SCEDC-catalogs", "aa31ff760b35c2e7f52ea25a338108414997101b", "SCEC_DC", "catalog"),
}
INPUT_FIELDS = ["evid", "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second"]
SAFE_FIELDS = set(INPUT_FIELDS + ["lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob", "time_utc"])
TYPE_LABELS = {"eq": "earthquake", "qb": "blast", "ex": "blast"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def write_new(path, value):
    with open(path, "x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")


def freeze(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for network, repo_dir in (("NC", args.nc_repo), ("SC", args.sc_repo)):
        repo, commit, folder, extension = SNAPSHOTS[network]
        got = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir, text=True).strip()
        if got != commit:
            raise ValueError(f"Unexpected {network} snapshot: {got}")
        tree = subprocess.check_output(["git", "ls-tree", "-r", commit], cwd=repo_dir, text=True)
        blobs = {}
        for line in tree.splitlines():
            info, path = line.split("\t", 1)
            mode, kind, blob = info.split()
            if kind == "blob":
                blobs[path] = blob
        for year in range(1981, 2022):
            path = f"{folder}/{year}.{extension}"
            files.append({"network": network, "year": year, "repository": repo,
                          "commit": commit, "path": path, "git_blob_sha1": blobs[path],
                          "url": f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"})
    contract = {
        "format": "KCH_BLIND_EVENT_CODE_CORROBORATION_CONTRACT_V0_9_2",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_npz_sha256": sha256_file(args.npz),
        "script_sha256": sha256_file(__file__),
        "input_fields": INPUT_FIELDS,
        "source_files": files,
        "network_bijections": [{"1": "NC", "2": "SC"}, {"1": "SC", "2": "NC"}],
        "event_bijections": [{"0": "earthquake", "1": "blast"}, {"0": "blast", "1": "earthquake"}],
        "documented_source_types": TYPE_LABELS,
        "identity": "producer network plus exact integer event ID plus calendar UTC origin within tolerance",
        "maximum_origin_time_difference_seconds": 1.0,
        "required_coverage": 1.0,
        "required_label_consistency": 1.0,
        "required_unique_passing_bijection": True,
        "other_source_event_types": "HOLD; no coercion",
        "duplicate_source_rows": "HOLD for every matched duplicated ID, even identical source rows",
        "missing_ambiguous_conflicting_rows": "HOLD; no imputation, deletion, replacement or tolerance changes",
        "eligibility_authorized": False,
        "angular_access_authorized": False,
        "model_fitting_authorized": False,
        "authority_ceiling": "NONE",
        "producer_documentation": [
            "https://github.com/NCEDC/NCSS-catalogs/blob/77d864e102b817b8662bd707f39ad34dd069cc97/README.md",
            "https://github.com/SCEDC/SCEDC-catalogs/blob/aa31ff760b35c2e7f52ea25a338108414997101b/README.md",
            "https://scedc.caltech.edu/eq-catalogs/docs/scec_dc.html",
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/csv.php",
        ],
    }
    contract["contract_id"] = "h9codecontract:" + hashlib.sha256(canonical(contract)).hexdigest()
    write_new(out / "CONTRACT_FROZEN_BEFORE_JOIN.json", contract)
    print(json.dumps({"contract_id": contract["contract_id"], "files": len(files)}, sort_keys=True), flush=True)


def download_one(item, cache):
    path = cache / item["network"] / Path(item["path"]).name
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = dict(item)
    try:
        if not path.exists():
            tmp = path.with_suffix(path.suffix + ".partial")
            request = urllib.request.Request(item["url"], headers={"User-Agent": "KCH-blind-semantic-corroboration/0.9.2"})
            with urllib.request.urlopen(request, timeout=90) as response, open(tmp, "xb") as dest:
                receipt["http_status"] = response.status
                receipt["final_url"] = response.url
                if response.url != item["url"] or response.status != 200:
                    raise ValueError("Unanticipated redirect or HTTP status")
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    dest.write(block)
            tmp.replace(path)
        receipt["bytes"] = path.stat().st_size
        receipt["sha256"] = sha256_file(path)
        h = hashlib.sha1(f"blob {receipt['bytes']}\0".encode())
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        receipt["observed_git_blob_sha1"] = h.hexdigest()
        receipt["outcome"] = "VERIFIED" if h.hexdigest() == item["git_blob_sha1"] else "HOLD_IDENTITY_MISMATCH"
    except Exception as exc:
        receipt["outcome"] = "HOLD_DOWNLOAD_FAILURE"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
    return receipt, path


def origin_seconds(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def parse_source(path, network, wanted_ids):
    found = {}
    counts = Counter()
    malformed_examples = []
    with open(path, encoding="utf-8") as f:
        rows = csv.DictReader(f) if network == "NC" else f
        for line_number, row in enumerate(rows, 2 if network == "NC" else 1):
            if network == "SC" and (not row.strip() or row.startswith("#")):
                continue
            counts["rows"] += 1
            try:
                if network == "NC":
                    event_id = int(row["id"])
                    timestamp = origin_seconds(row["time"])
                    event_type = row["type"]
                    if row["net"].upper() != "NC":
                        raise ValueError("Unexpected network")
                else:
                    fields = row.split()
                    if len(fields) != 13:
                        raise ValueError(f"Expected 13 SCEDC fields; found {len(fields)}")
                    event_id = int(fields[10])
                    timestamp = origin_seconds(fields[0].replace("/", "-") + "T" + fields[1] + "+00:00")
                    event_type = fields[2]
                counts["source_type_" + event_type] += 1
                if event_id in wanted_ids:
                    counts["wanted_id_rows"] += 1
                    if event_id in found:
                        found[event_id] = None
                        counts["duplicated_wanted_id_rows"] += 1
                    else:
                        found[event_id] = (timestamp, event_type)
            except Exception as exc:
                counts["malformed_rows"] += 1
                if len(malformed_examples) < 5:
                    malformed_examples.append({"line": line_number, "error": str(exc)})
    return found, dict(counts), malformed_examples


def run(args):
    out = Path(args.output)
    contract_path = out / "CONTRACT_FROZEN_BEFORE_JOIN.json"
    contract = json.loads(contract_path.read_text())
    cid = contract.pop("contract_id")
    if cid != "h9codecontract:" + hashlib.sha256(canonical(contract)).hexdigest():
        raise ValueError("Contract identity mismatch")
    contract["contract_id"] = cid
    if contract["script_sha256"] != sha256_file(__file__) or contract["source_npz_sha256"] != sha256_file(args.npz):
        raise ValueError("Frozen input or script changed")
    cache = Path(args.cache)
    receipts = []
    paths = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(download_one, item, cache) for item in contract["source_files"]]
        for future in as_completed(futures):
            receipt, path = future.result()
            receipts.append(receipt)
            paths.append((receipt, path))
            print(json.dumps({"downloaded": len(receipts), "of": len(futures), "network": receipt["network"],
                              "year": receipt["year"], "outcome": receipt["outcome"]}), flush=True)
    receipts.sort(key=lambda r: (r["network"], r["year"]))
    write_new(out / "SOURCE_DOWNLOAD_RECEIPTS.json", receipts)
    report = {"format": "KCH_BLIND_EVENT_CODE_CORROBORATION_RESULT_V0_9_2", "contract_id": cid,
              "contract_file_sha256": sha256_file(contract_path), "source_npz_sha256": contract["source_npz_sha256"],
              "directional_fields_accessed": False, "input_fields_accessed": INPUT_FIELDS,
              "eligibility_executed": False, "labels_replaced": False, "imputations": 0, "rows_deleted": 0,
              "authority_ceiling": "NONE", "downloads_verified": sum(r["outcome"] == "VERIFIED" for r in receipts),
              "downloads_expected": len(receipts), "download_bytes": sum(r.get("bytes", 0) for r in receipts)}
    if report["downloads_verified"] != report["downloads_expected"]:
        report["outcome"] = "HOLD_INCOMPLETE_SOURCE_ACQUISITION"
        write_new(out / "CORROBORATION_RESULT.json", report)
        return 21
    with np.load(args.npz, allow_pickle=False) as z:
        if set(z.files) - SAFE_FIELDS:
            raise ValueError("Input contains fields beyond the frozen blind allowlist")
        arrays = {k: z[k] for k in INPUT_FIELDS}
    n = len(arrays["evid"])
    if any(a.ndim != 1 or len(a) != n or a.dtype.hasobject for a in arrays.values()):
        raise ValueError("Invalid input shape or object array")
    ids = np.asarray([int(x) for x in arrays["evid"]], dtype=np.int64)
    if any(str(int(x)) != str(x) for x in arrays["evid"]):
        raise ValueError("Noncanonical integer event ID")
    if set(np.unique(arrays["nc_sc"])) != {1.0, 2.0} or set(np.unique(arrays["ev_bl"])) != {0.0, 1.0}:
        raise ValueError("Input category vocabulary differs from frozen bijections")
    for field in ("year", "month", "day", "hour", "minute"):
        if not np.all(np.isfinite(arrays[field])) or not np.all(arrays[field] == np.floor(arrays[field])):
            raise ValueError("Nonintegral calendar field")
    if not np.all(np.isfinite(arrays["second"])):
        raise ValueError("Nonfinite seconds")
    times = np.asarray([(datetime(int(y), int(m), int(d), int(h), int(mi), tzinfo=timezone.utc)
                         + timedelta(seconds=float(s))).timestamp()
                        for y, m, d, h, mi, s in zip(*(arrays[k] for k in INPUT_FIELDS[3:]))])
    wanted_ids = set(map(int, ids))
    catalogs = {"NC": {}, "SC": {}}
    parsing = []
    for receipt, path in sorted(paths, key=lambda x: (x[0]["network"], x[0]["year"])):
        found, counts, examples = parse_source(path, receipt["network"], wanted_ids)
        target = catalogs[receipt["network"]]
        for event_id, value in found.items():
            if event_id in target:
                target[event_id] = None
                counts["duplicate_id_across_years"] = counts.get("duplicate_id_across_years", 0) + 1
            else:
                target[event_id] = value
        parsing.append({"network": receipt["network"], "year": receipt["year"], "counts": counts,
                        "malformed_examples": examples})
    write_new(out / "SOURCE_PARSING_AUDIT.json", parsing)
    source_parse_errors = sum(p["counts"].get("malformed_rows", 0) for p in parsing)
    report.update({"rows": n, "source_parse_errors": source_parse_errors, "candidate_results": []})
    diagnostic = {}
    for nc_code in (1, 2):
        idx = np.flatnonzero(arrays["nc_sc"] == nc_code)
        for network in ("NC", "SC"):
            counts = Counter()
            for i in idx:
                event_id = int(ids[i])
                source = catalogs[network]
                if event_id not in source:
                    counts["missing_id"] += 1
                elif source[event_id] is None:
                    counts["ambiguous_id"] += 1
                else:
                    timestamp, event_type = source[event_id]
                    if abs(timestamp - times[i]) > contract["maximum_origin_time_difference_seconds"]:
                        counts["origin_time_mismatch"] += 1
                    elif event_type not in TYPE_LABELS:
                        counts["unsupported_source_type_" + event_type] += 1
                    else:
                        counts[f"code_{int(arrays['ev_bl'][i])}_source_{TYPE_LABELS[event_type]}"] += 1
            diagnostic[(nc_code, network)] = counts
    report["network_diagnostics"] = [{"nc_sc": key[0], "producer": key[1], "counts": dict(value)}
                                      for key, value in diagnostic.items()]
    for network_map in contract["network_bijections"]:
        counts = Counter()
        for code, network in network_map.items():
            counts.update(diagnostic[(int(code), network)])
        matched = sum(v for k, v in counts.items() if k.startswith("code_"))
        for event_map in contract["event_bijections"]:
            consistent = sum(counts[f"code_{code}_source_{label}"] for code, label in event_map.items())
            passed = matched == n and consistent == n and source_parse_errors == 0
            report["candidate_results"].append({"network_bijection": network_map, "event_bijection": event_map,
                                               "matched_supported_rows": matched, "consistent_rows": consistent,
                                               "label_contradictions": matched - consistent,
                                               "unmatched_or_ambiguous_rows": n - matched,
                                               "coverage": matched / n, "consistency_all_rows": consistent / n,
                                               "passed_all_frozen_checks": passed, "counts": dict(counts)})
    passing = [r for r in report["candidate_results"] if r["passed_all_frozen_checks"]]
    report["outcome"] = "EXHAUSTIVE_CODE_CORROBORATION_PASS" if len(passing) == 1 else "HOLD_CODES_NOT_EXHAUSTIVELY_CORROBORATED"
    report["unique_passing_bijection"] = passing[0] if len(passing) == 1 else None
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["receipt_id"] = "h9codecorroboration:" + hashlib.sha256(canonical(report)).hexdigest()
    write_new(out / "CORROBORATION_RESULT.json", report)
    print(json.dumps({"outcome": report["outcome"], "rows": n, "receipt_id": report["receipt_id"]}), flush=True)
    return 0 if passing else 21


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("freeze", "run"))
    p.add_argument("--npz", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--cache")
    p.add_argument("--nc-repo")
    p.add_argument("--sc-repo")
    args = p.parse_args()
    if args.mode == "freeze":
        if not args.nc_repo or not args.sc_repo:
            p.error("freeze requires --nc-repo and --sc-repo")
        freeze(args)
        return 0
    if not args.cache:
        p.error("run requires --cache")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
