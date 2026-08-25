from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def sha_file(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = root / "results" / "KCH_MIS_V03_BUILD_MANIFEST_v0.1.0.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    defects: list[str] = []
    for row in manifest["files"]:
        path = root / row["path"]
        if not path.is_file():
            defects.append(f"MISSING:{row['path']}")
        elif path.stat().st_size != row["bytes"] or sha_file(path) != row["sha256"]:
            defects.append(f"HASH_OR_SIZE:{row['path']}")
    result = json.loads((root / "results" / "KCH_MIS_V03_EFFECTIVE_INTEGRATION_RESULT_v0.1.0.json").read_text(encoding="utf-8"))
    if result.get("gate") != "PASS_BOUNDED" or result.get("checks_passed") != result.get("checks_total"):
        defects.append("GATE_RESULT_NOT_PASS_BOUNDED")
    sys.path.insert(0, str(root / "src"))
    from kch_mis_v03_integration.adapter import MISV03Adapter
    adapter = MISV03Adapter(
        wheel=root / "vendor" / "mis_qualitative_bayes-0.3.1-py3-none-any.whl",
        corpus=root / "evidence" / "KHC_TWO_BATTERY_MASTER_RESULTS_v2.0.7.json",
        report=root / "evidence" / "MIS_v0_3_EXPERIMENT_REPORT.json",
        ledgers=root / "evidence" / "MIS_v0_3_KHC_FUTURE_ONLY_LEDGERS.json",
        manifest=root / "evidence" / "MIS_RELEASE_MANIFEST_v0.3.1.json",
    )
    live = adapter.audit_historical_khc()
    frozen = json.loads((root / "results" / "KCH_MIS_V03_HISTORICAL_CERTIFICATE_v0.1.0.json").read_text(encoding="utf-8"))
    if live != frozen or not adapter.verify_certificate(live)["valid"]:
        defects.append("LIVE_CERTIFICATE_REPLAY_MISMATCH")
    value = {
        "schema": "kch.mis.v03.release-verification.v0.1.0",
        "gate": "PASS" if not defects else "FAIL",
        "defects": defects,
        "manifest_entries": len(manifest["files"]),
        "historical_certificate_sha256": live["certificate_sha256"],
        "records": live["records"],
        "streams": live["streams"],
    }
    print(json.dumps(value, ensure_ascii=False))
    return 0 if not defects else 1


if __name__ == "__main__":
    raise SystemExit(main())

