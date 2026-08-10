from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CASE = json.loads((ROOT / "case.json").read_text(encoding="utf-8"))
INPUTS = {
    "BASELINE_SIN_KCH": Path(
        r"C:\Users\User\Documents\Codex\2026-08-10\kch-prepilot-002-baseline\outputs\KCH-PREPILOT-002-receipt.json"
    ),
    "KCH_RUNTIME_ASSISTED_CANONICAL": Path(
        r"C:\Users\User\Documents\Codex\2026-08-10\kch-prepilot-002-harness\outputs\KCH-PREPILOT-002-receipt.json"
    ),
}
REQUIRED_KEYS = {
    "schema",
    "condition",
    "exhaustive_read_receipt",
    "cross_module_findings",
    "bind_2026_receipt",
    "candidate_use_cases",
    "adverse_findings",
    "claim_ceiling",
    "abstentions",
}
FINDINGS = (
    "phl_gate",
    "mutation_consent",
    "mis_and_bridges",
    "sqlite_lifecycle",
    "strategic_coverage",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {flatten(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(flatten(item) for item in value)
    return str(value)


def nested_gate(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("gate"), str):
        return value["gate"]
    result = value.get("result")
    if isinstance(result, dict) and isinstance(result.get("gate"), str):
        return result["gate"]
    structured = value.get("structuredContent")
    if isinstance(structured, dict) and isinstance(structured.get("gate"), str):
        return structured["gate"]
    return None


def finding_references(value: Any) -> list[str]:
    direct = set(
        re.findall(
            r"(?:advanced_runtime|mis_service|operational_surface)\.py:\d+", flatten(value)
        )
    )
    if direct or not isinstance(value, dict):
        return sorted(direct)
    for file_evidence in value.get("files", []):
        if not isinstance(file_evidence, dict):
            continue
        name = Path(str(file_evidence.get("path", ""))).name
        if name not in {"advanced_runtime.py", "mis_service.py", "operational_surface.py"}:
            continue
        for item in file_evidence.get("evidence", []):
            if isinstance(item, dict):
                line = item.get("line")
            else:
                match = re.search(r"(?:line[=:]\s*|\bL)(\d+)", str(item), re.I)
                line = None if match is None else match.group(1)
            if line is not None and str(line).isdigit():
                direct.add(f"{name}:{line}")
    return sorted(direct)


def evaluate_common(receipt: dict[str, Any]) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    full_text = flatten(receipt).casefold()
    exact_contract = set(receipt) == REQUIRED_KEYS
    sections["contract"] = {"pass": exact_contract, "score": 5 if exact_contract else 0}

    read_receipt = receipt.get("exhaustive_read_receipt", {})
    files = read_receipt.get("files", read_receipt.get("corpus_files", []))
    observed = {Path(item.get("path", "")).name: item for item in files}
    file_checks = []
    for expected in CASE["corpus_oracle"]:
        item = observed.get(expected["name"], {})
        passed = (
            int(item.get("bytes", -1)) == expected["bytes"]
            and int(item.get("physical_lines", item.get("lines", -1)))
            == expected["physical_lines"]
            and str(item.get("sha256", "")).casefold() == expected["sha256"]
        )
        file_checks.append({"name": expected["name"], "pass": passed})
    sections["exhaustive_receipt"] = {
        "checks": file_checks,
        "score": sum(10 for item in file_checks if item["pass"]),
    }

    findings = receipt.get("cross_module_findings", {})
    finding_checks = []
    for key in FINDINGS:
        refs = finding_references(findings.get(key, {}))
        finding_checks.append({"key": key, "references": refs, "pass": bool(refs)})
    sections["cross_module_traceability"] = {
        "checks": finding_checks,
        "score": sum(5 for item in finding_checks if item["pass"]),
    }

    bind = receipt.get("bind_2026_receipt", {})
    bind_text = flatten(bind).casefold()
    sources = [str(item) for item in bind.get("official_sources", [])]
    asset_hits = {
        asset: any(asset.casefold() in source.casefold() for source in sources)
        for asset in CASE["exact_call"]["required_official_assets"]
    }
    bind_checks = {
        "four_assets": all(asset_hits.values()),
        "dates": "2026" in bind_text
        and any(term in bind_text for term in ("2 de julio", "2 july", "2026-07-02"))
        and any(
            term in bind_text for term in ("4 de septiembre", "4 september", "2026-09-04")
        ),
        "maximum_three": bool(
            re.search(r"(?:maximum|max|hasta|up to).{0,30}(?:three|tres|3)", bind_text)
        ),
        "venture_client_financing": "venture client" in bind_text
        and any(term in bind_text for term in ("financ", "contract", "paid", "remuner")),
        "concrete_group_id": bool(
            re.search(r"(?:group|grupo).{0,12}\d+", flatten(receipt.get("candidate_use_cases", [])), re.I)
        )
        and bool(re.search(r"\bID\s*\d+", flatten(receipt.get("candidate_use_cases", [])), re.I)),
    }
    weights = {
        "four_assets": 8,
        "dates": 3,
        "maximum_three": 3,
        "venture_client_financing": 3,
        "concrete_group_id": 3,
    }
    sections["exact_bind_call"] = {
        "checks": bind_checks,
        "asset_hits": asset_hits,
        "score": sum(weights[key] for key, passed in bind_checks.items() if passed),
    }

    discipline = {
        "adverse_preserved": bool(receipt.get("adverse_findings")),
        "abstentions_preserved": bool(receipt.get("abstentions")),
        "not_estimable": "not_estimable" in full_text
        or "not estimable" in full_text
        or "no demostrado" in full_text,
    }
    sections["claim_discipline"] = {
        "checks": discipline,
        "score": (4 if discipline["adverse_preserved"] else 0)
        + (3 if discipline["abstentions_preserved"] else 0)
        + (3 if discipline["not_estimable"] else 0),
    }
    candidates = receipt.get("candidate_use_cases", [])
    bounded = isinstance(candidates, list) and 1 <= len(candidates) <= 3
    sections["bounded_candidates"] = {"pass": bounded, "score": 5 if bounded else 0}
    return {"score": sum(item["score"] for item in sections.values()), "maximum": 95, "sections": sections}


def condition_check(condition: str, receipt: dict[str, Any]) -> dict[str, Any]:
    read = receipt.get("exhaustive_read_receipt", {})
    if condition == "BASELINE_SIN_KCH":
        checks = {
            "declared_condition": receipt.get("condition") == condition,
            "kch_not_used": read.get("kch_used") is False,
        }
    else:
        preflight = read.get("kch_preflight", {})
        checks_block = preflight.get("checks", {}) if isinstance(preflight, dict) else {}
        integrity = read.get("workbench_integrity", {})
        ingest = read.get("workbench_ingest_receipts", [])
        checks = {
            "declared_condition": receipt.get("condition") == condition,
            "kch_used": read.get("kch_used") is True,
            "canonical_class": read.get("runtime_class")
            in {
                "kch_studio.mcp_server.StudioMCP",
                "kch_studio.mcp_server:StudioMCP",
            },
            "canonical_entrypoint": preflight.get("canonical_entrypoint")
            == "kch_studio.mcp_server:StudioMCP",
            "preflight_pass": preflight.get("gate") == "PASS",
            "all_preflight_checks_true": bool(checks_block) and all(checks_block.values()),
            "three_ingests": isinstance(ingest, list) and len(ingest) == 3,
            "workbench_integrity_pass": nested_gate(integrity) == "PASS",
            "close_called": read.get("close_called") is True,
            "no_external_install": preflight.get("external_installation_performed") is False,
            "no_real_phl": preflight.get("phl", {}).get("training_executed") is False
            and preflight.get("phl", {}).get("real_feedback_executed") is False,
        }
    return {"checks": checks, "gate": "PASS" if all(checks.values()) else "FAIL"}


def main() -> None:
    receipt_dir = ROOT / "receipts"
    receipt_dir.mkdir(exist_ok=True)
    results: dict[str, Any] = {}
    for condition, source in INPUTS.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = receipt_dir / f"{condition.casefold()}.json"
        shutil.copyfile(source, destination)
        receipt = json.loads(destination.read_text(encoding="utf-8"))
        results[condition] = {
            "source_path": str(source),
            "custody_path": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
            "quality": evaluate_common(receipt),
            "condition_integrity": condition_check(condition, receipt),
        }

    integrity_pass = all(
        result["condition_integrity"]["gate"] == "PASS" for result in results.values()
    )
    scores = {key: value["quality"]["score"] for key, value in results.items()}
    if len(set(scores.values())) == 1:
        descriptive_outcome = "TIE"
    else:
        descriptive_outcome = max(scores, key=scores.get)  # type: ignore[arg-type]
    report = {
        "schema": "kch.prepilot-evaluation.v0.2.0",
        "case_id": CASE["case_id"],
        "results": results,
        "comparative_condition_gate": (
            "PASS_SINGLE_NONRANDOMIZED_PAIR" if integrity_pass else "INVALID_CONDITION_INTEGRITY"
        ),
        "descriptive_outcome": descriptive_outcome if integrity_pass else "NOT_ESTIMABLE",
        "causal_effect": "NOT_ESTIMABLE",
        "industrial_validation": False,
        "interpretation": (
            "A valid condition gate would establish only that the intended baseline and canonical KCH-assisted procedures ran. One nonrandomized pair cannot establish causal benefit, industrial validity, user utility or BIND readiness."
        ),
        "next_gate": (
            "Add distinct historical failure classes, independent repetitions and condition-blinded adjudication; only then begin estimating error-avoidance and process-value signals."
        ),
    }
    (ROOT / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
