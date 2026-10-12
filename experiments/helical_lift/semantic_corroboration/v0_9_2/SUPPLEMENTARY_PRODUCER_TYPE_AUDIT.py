#!/usr/bin/env python3
"""Post-run audit of producer-specific labels; does not change frozen results."""
from collections import Counter
import hashlib
import json
import sys
from pathlib import Path

base = Path(sys.argv[1]).resolve() / "corroboration"
cache = base.parent / "catalog-cache"
receipts = json.loads((base / "SOURCE_DOWNLOAD_RECEIPTS.json").read_text())
sc_receipts = [r for r in receipts if r["network"] == "SC"]
counts = Counter()
bad_shape = 0
for receipt in sc_receipts:
    path = cache / "SC" / Path(receipt["path"]).name
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != receipt["sha256"]:
        raise ValueError("Source hash changed")
    for line in payload.decode("utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        columns = line.split()
        if len(columns) != 13:
            bad_shape += 1
            continue
        counts[columns[2]] += 1
result = {
    "format": "KCH_POST_RUN_PRODUCER_TYPE_AUDIT_V0_9_2",
    "timing": "Supplementary audit after frozen corroboration; not a prospective contract change",
    "source_receipts_sha256": hashlib.sha256((base / "SOURCE_DOWNLOAD_RECEIPTS.json").read_bytes()).hexdigest(),
    "frozen_result_sha256": hashlib.sha256((base / "CORROBORATION_RESULT.json").read_bytes()).hexdigest(),
    "SC_files_verified": len(sc_receipts),
    "SC_type_counts_including_unparseable_origin_times": dict(counts),
    "SC_unparseable_shape_rows": bad_shape,
    "SC_ex_count": counts["ex"],
    "global_ex_mapping_limitation_affects_observed_SC_rows": counts["ex"] > 0 or bad_shape > 0,
    "certification_permitted": False,
    "frozen_outcome_changed": False,
    "labels_replaced": False,
    "directional_fields_accessed": False,
    "authority_ceiling": "NONE",
}
with open(base / "SUPPLEMENTARY_PRODUCER_TYPE_AUDIT.json", "x") as f:
    json.dump(result, f, indent=2, sort_keys=True)
    f.write("\n")
print(json.dumps(result, sort_keys=True))
