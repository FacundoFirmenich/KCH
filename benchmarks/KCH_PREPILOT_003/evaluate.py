from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CASE = json.loads((ROOT / "case.json").read_text(encoding="utf-8"))
INPUTS = {
    "BASELINE_RELEASE_AUDIT": Path(
        r"C:\Users\User\Documents\Codex\2026-08-10\kch-prepilot-003-baseline\outputs\KCH-PREPILOT-003-receipt.json"
    ),
    "KCH_INSTALLED_R9_ASSISTED": Path(
        r"C:\Users\User\Documents\Codex\2026-08-10\kch-prepilot-003-harness\outputs\KCH-PREPILOT-003-receipt.json"
    ),
}
REQUIRED_KEYS = {
    "schema",
    "condition",
    "input_receipt",
    "archive_verification",
    "adverse_chronology",
    "installed_gate_verification",
    "prepilot_reconciliation",
    "release_adjudication",
    "bind_boundary",
    "claim_ceiling",
    "abstentions",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {flatten(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(flatten(item) for item in value)
    return str(value)


def input_items(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    block = receipt.get("input_receipt", {})
    if isinstance(block, list):
        return block
    for key in ("files", "inputs", "items"):
        if isinstance(block.get(key), list):
            return block[key]
    return []


def independently_verify_archive() -> dict[str, Any]:
    archive = Path(CASE["input_oracle"][0]["path"])
    with zipfile.ZipFile(archive) as stream:
        crc = stream.testzip()
        names = [info.filename for info in stream.infolist() if not info.is_dir()]
        roots = {Path(name).parts[0] for name in names}
        manifest_name = next(name for name in names if name.endswith("MANIFEST_PRESEAL.json"))
        manifest = json.loads(stream.read(manifest_name))
        mismatches = []
        for item in manifest["files"]:
            member = f"{next(iter(roots))}/{item['path']}"
            raw = stream.read(member)
            if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                mismatches.append(member)
        declared = {f"{next(iter(roots))}/{item['path']}" for item in manifest["files"]}
        undeclared = sorted(set(names) - declared - {manifest_name})
    return {
        "archive_sha256": sha256(archive),
        "crc_pass": crc is None,
        "single_root": len(roots) == 1,
        "member_count": len(names),
        "manifest_file_count": manifest["file_count"],
        "manifest_mismatches": mismatches,
        "undeclared_except_manifest": undeclared,
    }


def score(receipt: dict[str, Any], independent: dict[str, Any]) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    sections["contract"] = {
        "pass": set(receipt) == REQUIRED_KEYS,
        "score": 5 if set(receipt) == REQUIRED_KEYS else 0,
    }

    by_path = {str(item.get("path", "")).casefold(): item for item in input_items(receipt)}
    checks = []
    for expected in CASE["input_oracle"]:
        item = by_path.get(expected["path"].casefold(), {})
        observed_bytes = item.get("bytes", item.get("actual_bytes", -1))
        observed_sha256 = item.get("sha256", item.get("actual_sha256", ""))
        checks.append(
            {
                "path": expected["path"],
                "pass": int(observed_bytes) == expected["bytes"]
                and str(observed_sha256).casefold() == expected["sha256"],
            }
        )
    sections["input_receipt"] = {
        "checks": checks,
        "score": 20 if checks and all(item["pass"] for item in checks) else 0,
    }

    archive_text = flatten(receipt.get("archive_verification", {})).casefold()
    archive_checks = {
        "archive_hash": independent["archive_sha256"] in archive_text,
        "crc": independent["crc_pass"] and any(term in archive_text for term in ("crc", "testzip")),
        "single_root": independent["single_root"] and "root" in archive_text,
        "manifest_all": not independent["manifest_mismatches"]
        and any(term in archive_text for term in ("mismatch", "all", "every", "todos")),
        "undeclared_none": not independent["undeclared_except_manifest"],
    }
    sections["archive"] = {
        "checks": archive_checks,
        "score": sum(4 for passed in archive_checks.values() if passed),
    }

    chronology = flatten(receipt.get("adverse_chronology", {})).casefold()
    chronology_checks = {
        "r6": "r6" in chronology and "fail" in chronology,
        "r7": "r7" in chronology and any(term in chronology for term in ("wrapper", "check")),
        "r8": "r8" in chronology and "tzdata" in chronology,
        "r9": "r9" in chronology and any(term in chronology for term in ("14/14", "14 de 14", "pass")),
    }
    sections["chronology"] = {
        "checks": chronology_checks,
        "score": sum(4 for passed in chronology_checks.values() if passed),
    }

    gate = flatten(receipt.get("installed_gate_verification", {})).casefold()
    gate_checks = {
        "247_tools": "247" in gate,
        "14_checks": "14" in gate,
        "17_governance": "17" in gate,
        "mis_480_60": "480" in gate and "60" in gate,
        "authority_false": "authority" in gate and "false" in gate,
        "preflight_pass": "preflight" in gate and "pass" in gate,
        "workbench_pass": "workbench" in gate and "pass" in gate,
    }
    sections["installed_gate"] = {
        "checks": gate_checks,
        "score": 14 if all(gate_checks.values()) else 0,
    }

    prepilot_block = receipt.get("prepilot_reconciliation", {})
    prepilot = flatten(prepilot_block).casefold()
    case_002_tie = "tie" in prepilot
    if isinstance(prepilot_block, dict):
        case_002 = prepilot_block.get("KCH-PREPILOT-002", {})
        if isinstance(case_002, dict):
            case_002_tie = case_002_tie or (
                case_002.get("baseline_score") is not None
                and case_002.get("baseline_score") == case_002.get("candidate_score")
            )
    prepilot_ok = (
        "001" in prepilot
        and "invalid_condition_integrity" in prepilot
        and "002" in prepilot
        and case_002_tie
        and ("not_estimable" in prepilot or "not estimable" in prepilot)
    )
    sections["prepilots"] = {"pass": prepilot_ok, "score": 10 if prepilot_ok else 0}

    adjudication = flatten(receipt.get("release_adjudication", {}))
    adjudication_ok = "READY_FOR_CONTROLLED_DOGFOOD_NOT_INDUSTRIAL_VALIDATION" in adjudication
    sections["adjudication"] = {
        "pass": adjudication_ok,
        "score": 5 if adjudication_ok else 0,
    }

    bind = flatten(receipt.get("bind_boundary", {})).casefold()
    bind_ok = ("group 6" in bind or "grupo 6" in bind) and "id36" in bind and any(
        term in bind for term in ("not industrial", "no industrial", "no equivale", "not equivalent")
    )
    sections["bind"] = {"pass": bind_ok, "score": 5 if bind_ok else 0}

    abstentions = flatten(receipt.get("abstentions", [])).casefold()
    discipline = bool(receipt.get("abstentions")) and any(
        term in abstentions for term in ("industrial", "causal", "bind", "ergonom")
    )
    sections["discipline"] = {"pass": discipline, "score": 5 if discipline else 0}
    return {"score": sum(item["score"] for item in sections.values()), "maximum": 100, "sections": sections}


def condition_integrity(condition: str, receipt: dict[str, Any]) -> dict[str, Any]:
    gate = receipt.get("installed_gate_verification", {})
    text = flatten(gate).casefold()
    if condition == "BASELINE_RELEASE_AUDIT":
        checks = {
            "condition": receipt.get("condition") == condition,
            "live_kch_false": gate.get("live_kch_used") is False,
        }
    else:
        live = gate.get("live", {}) if isinstance(gate, dict) else {}
        direct_or_live = live if isinstance(live, dict) and live else gate
        checks = {
            "condition": receipt.get("condition") == condition,
            "live_kch_true": direct_or_live.get("live_kch_used") is True,
            "installed_executable": "856fac9b029b" in text and "kch-super-mcp-studio" in text,
            "247_tools": "247" in text,
            "preflight_pass": "preflight" in text and "pass" in text,
            "workbench_pass": "workbench" in text and "pass" in text,
            "mis_480_60": "480" in text and "60" in text,
            "closed": direct_or_live.get("close_called") is True,
        }
    return {"checks": checks, "gate": "PASS" if all(checks.values()) else "FAIL"}


def main() -> None:
    independent = independently_verify_archive()
    custody = ROOT / "receipts"
    custody.mkdir(exist_ok=True)
    results = {}
    for condition, source in INPUTS.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        target = custody / f"{condition.casefold()}.json"
        shutil.copyfile(source, target)
        receipt = json.loads(target.read_text(encoding="utf-8"))
        results[condition] = {
            "bytes": target.stat().st_size,
            "sha256": sha256(target),
            "quality": score(receipt, independent),
            "condition_integrity": condition_integrity(condition, receipt),
        }
    valid = all(item["condition_integrity"]["gate"] == "PASS" for item in results.values())
    scores = {key: item["quality"]["score"] for key, item in results.items()}
    descriptive = "TIE" if len(set(scores.values())) == 1 else max(scores, key=scores.get)  # type: ignore[arg-type]
    report = {
        "schema": "kch.prepilot-evaluation.v0.3.0",
        "case_id": CASE["case_id"],
        "independent_archive_oracle": independent,
        "results": results,
        "comparative_condition_gate": (
            "PASS_SINGLE_NONRANDOMIZED_PAIR" if valid else "INVALID_CONDITION_INTEGRITY"
        ),
        "descriptive_outcome": descriptive if valid else "NOT_ESTIMABLE",
        "causal_effect": "NOT_ESTIMABLE",
        "industrial_validation": False,
        "release_state": "READY_FOR_CONTROLLED_DOGFOOD_NOT_INDUSTRIAL_VALIDATION",
        "next_gate": "Replicate distinct failure cases with condition-blinded adjudication and then perform controlled host dogfooding without real PHL.",
    }
    (ROOT / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
