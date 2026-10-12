#!/usr/bin/env python3
"""Independent post-run diagnostics for one expressly unvalidated candidate."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

base = Path(sys.argv[1]).resolve() / "corroboration"
receipts = json.loads((base / "SOURCE_DOWNLOAD_RECEIPTS.json").read_text())
contract = json.loads((base / "CONTRACT_FROZEN_BEFORE_JOIN.json").read_text())
frozen = json.loads((base / "CORROBORATION_RESULT.json").read_text())
npz = base.parent / "remote-run9/expanded/blind/blind_columns.npz"
if hashlib.sha256(npz.read_bytes()).hexdigest() != contract["source_npz_sha256"]:
    raise ValueError("NPZ differs from frozen input")
with np.load(npz, allow_pickle=False) as z:
    fields = {k: z[k] for k in ("evid", "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second")}
ids = np.array([int(v) for v in fields["evid"]], dtype=np.int64)
times = []
for i in range(len(ids)):
    t = datetime(*(int(fields[k][i]) for k in ("year", "month", "day", "hour", "minute")),
                 tzinfo=timezone.utc) + timedelta(seconds=float(fields["second"][i]))
    times.append(t.timestamp())
candidate_network = {1: "NC", 2: "SC"}
candidate_type = {0: "earthquake", 1: "blast"}
producer_types = {"NC": {"eq": "earthquake", "ex": "blast", "qb": "blast"},
                  "SC": {"eq": "earthquake", "qb": "blast"}}
wanted = {net: set(map(int, ids[fields["nc_sc"] == code])) for code, net in candidate_network.items()}
catalogs = {"NC": {}, "SC": {}}
parse_failures = []
for receipt in receipts:
    network = receipt["network"]
    path = base.parent / "catalog-cache" / network / Path(receipt["path"]).name
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != receipt["sha256"]:
        raise ValueError("Source snapshot hash mismatch")
    with path.open(encoding="utf-8") as stream:
        rows = csv.DictReader(stream) if network == "NC" else stream
        for line_number, row in enumerate(rows, 2 if network == "NC" else 1):
            if network == "SC" and (not row.strip() or row.startswith("#")):
                continue
            try:
                if network == "NC":
                    event_id, origin, kind = int(row["id"]), row["time"], row["type"]
                    if row["net"].upper() != "NC":
                        raise ValueError("Unexpected source network")
                else:
                    parts = row.split()
                    if len(parts) != 13:
                        raise ValueError("Unexpected source row shape")
                    event_id = int(parts[10])
                    kind = parts[2]
                    origin = parts[0].replace("/", "-") + "T" + parts[1] + "+00:00"
                # Deliberately retains the frozen run's second=60 parser failure.
                seconds = datetime.fromisoformat(origin.replace("Z", "+00:00")).timestamp()
                if event_id in wanted[network]:
                    if event_id in catalogs[network]:
                        catalogs[network][event_id] = None
                    else:
                        catalogs[network][event_id] = (seconds, kind, origin, receipt, line_number)
            except Exception as exc:
                parse_failures.append({"network": network, "source_path": receipt["path"],
                                       "source_line": line_number, "reason": str(exc)})

columns = ["input_row_zero_based", "evid", "nc_sc", "ev_bl", "candidate_network", "candidate_event_label",
           "source_event_type_json", "source_event_label", "mechanism_calendar_utc", "source_origin_utc",
           "absolute_time_difference_seconds", "source_repository", "source_commit", "source_path",
           "source_line", "source_file_sha256"]
counts = {net: Counter() for net in candidate_network.values()}
outputs = {"contradiction": "LABEL_CONTRADICTIONS_ALL_2438.csv", "unsupported": "UNSUPPORTED_SOURCE_TYPES_ALL_1370.csv"}
handles = {k: open(base / name, "x", newline="", encoding="utf-8") for k, name in outputs.items()}
writers = {k: csv.DictWriter(h, fieldnames=columns) for k, h in handles.items()}
for writer in writers.values():
    writer.writeheader()
try:
    for i, event_id in enumerate(ids):
        code = int(fields["nc_sc"][i])
        network = candidate_network[code]
        cnt = counts[network]
        cnt["input_rows"] += 1
        catalog = catalogs[network]
        if int(event_id) not in catalog:
            cnt["missing_id"] += 1
            continue
        source = catalog[int(event_id)]
        if source is None:
            cnt["ambiguous_id"] += 1
            continue
        origin_seconds, source_type, origin, receipt, line_number = source
        delta = abs(times[i] - origin_seconds)
        if delta > 1.0:
            cnt["origin_time_mismatch"] += 1
            continue
        assumed_type = candidate_type[int(fields["ev_bl"][i])]
        source_label = producer_types[network].get(source_type)
        if source_label is None:
            category = "unsupported"
        elif source_label == assumed_type:
            cnt["consistent_rows"] += 1
            continue
        else:
            category = "contradiction"
        cnt[category + "_rows"] += 1
        writers[category].writerow({
            "input_row_zero_based": i, "evid": int(event_id), "nc_sc": code, "ev_bl": int(fields["ev_bl"][i]),
            "candidate_network": network, "candidate_event_label": assumed_type,
            "source_event_type_json": json.dumps(source_type), "source_event_label": source_label or "UNSUPPORTED",
            "mechanism_calendar_utc": datetime.fromtimestamp(times[i], timezone.utc).isoformat(),
            "source_origin_utc": origin, "absolute_time_difference_seconds": format(delta, ".9f"),
            "source_repository": receipt["repository"], "source_commit": receipt["commit"],
            "source_path": receipt["path"], "source_line": line_number, "source_file_sha256": receipt["sha256"]})
finally:
    for handle in handles.values():
        handle.close()
table = []
for network, cnt in counts.items():
    n = cnt["input_rows"]
    supported = cnt["consistent_rows"] + cnt["contradiction_rows"]
    table.append({"producer_candidate": network, **dict(cnt), "supported_matched_rows": supported,
                  "supported_coverage_fraction": supported / n, "consistent_fraction_of_all_rows": cnt["consistent_rows"] / n})
assert sum(c["input_rows"] for c in table) == frozen["rows"]
assert sum(c.get("contradiction_rows", 0) for c in table) == 2438
assert sum(c.get("unsupported_rows", 0) for c in table) == 1370
assert len(parse_failures) == frozen["source_parse_errors"] == 30
result = {
    "format": "KCH_POST_RUN_BLIND_FORENSIC_DIAGNOSTIC_V0_9_2",
    "candidate_is_validated": False, "candidate_network": candidate_network, "candidate_type": candidate_type,
    "purpose": "Locate every contradiction and unsupported source type for producer codebook clarification",
    "prospective_contract_changed": False, "tolerance_seconds_changed": False,
    "frozen_result_sha256": hashlib.sha256((base / "CORROBORATION_RESULT.json").read_bytes()).hexdigest(),
    "rows": frozen["rows"], "per_network": table, "parser_failures_preserved": parse_failures,
    "output_files": {name: hashlib.sha256((base / name).read_bytes()).hexdigest() for name in outputs.values()},
    "all_2438_contradictions_reproduced_independently": True,
    "all_1370_unsupported_rows_reproduced_independently": True,
    "directional_fields_accessed": False, "eligibility_authorized": False,
    "labels_replaced": False, "authority_ceiling": "NONE",
    "cause_of_disagreements": "Unresolved; later catalog revisions are a hypothesis, not an established explanation",
}
with open(base / "FORENSIC_DIAGNOSTIC.json", "x") as f:
    json.dump(result, f, indent=2, sort_keys=True)
    f.write("\n")
lines = ["# Diagnóstico por red", "", "El candidato 1→NC/2→SC y 0→terremoto/1→explosión se usa sólo para localizar desacuerdos; no está validado.", "",
         "| Red candidata | Filas | Coincidencias con tipo admitido | Cobertura | Coherentes | Contradicciones | ID ausente | Origen >1 s | Tipo no admitido |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
for row in table:
    lines.append(f"| {row['producer_candidate']} | {row['input_rows']:,} | {row['supported_matched_rows']:,} | {100*row['supported_coverage_fraction']:.4f}% | {row['consistent_rows']:,} | {row.get('contradiction_rows',0):,} | {row.get('missing_id',0):,} | {row.get('origin_time_mismatch',0):,} | {row.get('unsupported_rows',0):,} |")
lines.extend(["", "Las 2.438 contradicciones y 1.370 filas de tipo no admitido se reproducen con un lector independiente y están listadas íntegramente con ID, fila, tiempos y procedencia en los CSV adjuntos.", "",
              "El parser original dejó 30 orígenes SC con segundos fuera de 0–59 (26 con 60.00 y 4 con 60.99) sin interpretar. Esta limitación se preservó y no se corrigió retroactivamente. Las discrepancias permanecen sin explicación; posibles revisiones de los catálogos son una hipótesis, no una causa demostrada.", "",
              "No se cambiaron el contrato, los resultados congelados, los datos ni la tolerancia de 1 segundo. No se accedió a campos direccionales ni se autorizó elegibilidad.", ""])
(base / "NETWORK_DIAGNOSTIC.md").write_text("\n".join(lines))
print(json.dumps({"per_network": table, "contradictions": 2438, "unsupported_rows": 1370, "parser_failures": 30}))
