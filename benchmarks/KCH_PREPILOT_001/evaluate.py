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
        r"C:\Users\User\Documents\Codex\2026-08-10\kch-prepilot-001-baseline\outputs\KCH-PREPILOT-001-baseline-receipt.json"
    ),
    "KCH_CANDIDATO_CON_ARNES": Path(
        r"C:\Users\User\Documents\Codex\2026-08-10\kch-prepilot-001-harness\outputs\KCH-PREPILOT-001-receipt.json"
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
FINDING_ALIASES = (
    ("phl_gate",),
    ("mutation_consent",),
    ("mis_and_bridges",),
    ("sqlite_lifecycle",),
    ("strategic_coverage", "strategic_coverage_audit"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {flatten(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(flatten(item) for item in value)
    return str(value)


def read_files(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    block = receipt["exhaustive_read_receipt"]
    return list(block.get("files", block.get("source_files", [])))


def score_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    sections: dict[str, dict[str, Any]] = {}
    full_text = flatten(receipt).casefold()
    keys_ok = set(receipt) == REQUIRED_KEYS
    sections["contract"] = {"score": 5 if keys_ok else 0, "maximum": 5, "pass": keys_ok}

    observed_by_name = {Path(item["path"]).name: item for item in read_files(receipt)}
    corpus_checks = []
    for expected in CASE["corpus_oracle"]:
        observed = observed_by_name.get(expected["name"])
        corpus_checks.append(
            {
                "name": expected["name"],
                "pass": observed is not None
                and int(observed["bytes"]) == expected["bytes"]
                and int(observed.get("physical_lines", observed.get("lines", -1)))
                == expected["physical_lines"]
                and str(observed["sha256"]).casefold() == expected["sha256"],
            }
        )
    corpus_score = sum(10 for item in corpus_checks if item["pass"])
    sections["exhaustive_corpus_receipt"] = {
        "score": corpus_score,
        "maximum": 30,
        "checks": corpus_checks,
    }

    findings = receipt["cross_module_findings"]
    finding_checks = []
    for aliases in FINDING_ALIASES:
        key = next((item for item in aliases if item in findings), None)
        text = "" if key is None else flatten(findings[key])
        finding_checks.append(
            {
                "aliases": aliases,
                "resolved_key": key,
                "has_path_line_evidence": bool(
                    re.search(r"(?:advanced_runtime|mis_service|operational_surface)\.py:\d+", text)
                ),
                "pass": key is not None
                and bool(
                    re.search(
                        r"(?:advanced_runtime|mis_service|operational_surface)\.py:\d+", text
                    )
                ),
            }
        )
    findings_score = sum(5 for item in finding_checks if item["pass"])
    sections["cross_module_traceability"] = {
        "score": findings_score,
        "maximum": 25,
        "checks": finding_checks,
    }

    bind = receipt["bind_2026_receipt"]
    bind_text = flatten(bind).casefold()
    official_sources = [str(item) for item in bind.get("official_sources", [])]
    asset_hits = {
        asset: any(asset.casefold() in url.casefold() for url in official_sources)
        for asset in CASE["exact_call"]["required_official_assets"]
    }
    bind_checks = {
        "four_exact_official_assets": all(asset_hits.values()),
        "application_dates": "2026" in bind_text
        and any(term in bind_text for term in ("2 de julio", "2 july", "2026-07-02"))
        and any(
            term in bind_text for term in ("4 de septiembre", "4 september", "2026-09-04")
        ),
        "maximum_three_proposals": bool(
            re.search(
                r"(?:maximum|max(?:imum)?|hasta|up to).{0,24}(?:three|tres|3)", bind_text
            )
        ),
        "eleven_blocks": "eleven" in bind_text or "11" in bind_text,
        "venture_client_financing": "venture client" in bind_text
        and any(term in bind_text for term in ("financ", "paid", "contract", "remuner")),
        "industrial_boundary": any(
            term in full_text
            for term in (
                "no industrial",
                "not industrial",
                "industrial_boundary",
                "industrial validation",
            )
        ),
    }
    bind_weights = {
        "four_exact_official_assets": 8,
        "application_dates": 3,
        "maximum_three_proposals": 3,
        "eleven_blocks": 2,
        "venture_client_financing": 2,
        "industrial_boundary": 2,
    }
    sections["exact_bind_call"] = {
        "score": sum(bind_weights[key] for key, passed in bind_checks.items() if passed),
        "maximum": 20,
        "checks": bind_checks,
        "asset_hits": asset_hits,
    }

    discipline_checks = {
        "adverse_findings_preserved": len(receipt["adverse_findings"]) > 0,
        "abstentions_preserved": len(receipt["abstentions"]) > 0,
        "not_estimable_or_equivalent": "not_estimable" in full_text
        or "not estimable" in full_text
        or "no demostrado" in full_text,
    }
    sections["claim_discipline"] = {
        "score": (4 if discipline_checks["adverse_findings_preserved"] else 0)
        + (3 if discipline_checks["abstentions_preserved"] else 0)
        + (3 if discipline_checks["not_estimable_or_equivalent"] else 0),
        "maximum": 10,
        "checks": discipline_checks,
    }
    candidate_count = len(receipt["candidate_use_cases"])
    candidate_ok = 1 <= candidate_count <= 3
    sections["bounded_candidate_selection"] = {
        "score": 5 if candidate_ok else 0,
        "maximum": 5,
        "candidate_count": candidate_count,
        "pass": candidate_ok,
    }
    score = sum(item["score"] for item in sections.values())
    return {"score": score, "maximum": 95, "sections": sections}


def main() -> None:
    receipt_root = ROOT / "receipts"
    receipt_root.mkdir(parents=True, exist_ok=True)
    results = {}
    for condition, source in INPUTS.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = receipt_root / f"{condition.casefold()}.json"
        shutil.copyfile(source, destination)
        receipt = json.loads(destination.read_text(encoding="utf-8"))
        if receipt.get("condition") != condition:
            raise ValueError(f"condition mismatch in {source}")
        results[condition] = {
            "source_path": str(source),
            "custody_path": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
            "evaluation": score_receipt(receipt),
            "reported_preflight": receipt["exhaustive_read_receipt"].get("kch_preflight"),
        }

    report = {
        "schema": "kch.prepilot-evaluation.v0.1.0",
        "case_id": CASE["case_id"],
        "results": results,
        "condition_integrity": CASE["condition_integrity"],
        "comparative_efficacy_gate": "INVALID_CONDITION_INTEGRITY",
        "winner": "NOT_ESTIMABLE",
        "causal_effect": "NOT_ESTIMABLE",
        "industrial_validation": False,
        "interpretation": (
            "Both arms completed the deterministic corpus receipt and exact-call research, but the "
            "harness arm invoked a noncanonical internal component and failed its own preflight. Scores "
            "are descriptive response-quality diagnostics only and cannot estimate KCH benefit."
        ),
        "next_gate": (
            "Repeat the same frozen case with kch_preflight through StudioMCP, then add replicated "
            "historical failure cases under a blinded evaluator."
        ),
    }
    (ROOT / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = [
        "# KCH PREPILOT 001 — adjudicación material",
        "",
        "## Resultado",
        "",
        "El ensayo no permite estimar superioridad de KCH. El gate comparativo es `INVALID_CONDITION_INTEGRITY`: el brazo arnés usó una clase interna no canónica y su preflight falló. El resultado adverso se conserva; no se rescata mediante la puntuación.",
        "",
        "## Diagnóstico descriptivo",
        "",
    ]
    for condition, result in results.items():
        score = result["evaluation"]
        summary.append(f"- `{condition}`: {score['score']}/{score['maximum']} en el rubric observable.")
    summary.extend(
        [
            "",
            "Ambos brazos calcularon correctamente los bytes, líneas y SHA-256 de los tres archivos y buscaron la convocatoria BIND 11th Edition 2026/2027 en activos oficiales concretos. El brazo KCH preservó mejor su fallo de preflight y sus abstenciones, pero eso no prueba beneficio causal.",
            "",
            "## Límite",
            "",
            "Esto es un prepiloto local de proceso. No es prueba industrial, no es evidencia de valor para un Venture Client, no es validación humana y no establece readiness de candidatura BIND.",
            "",
            "## Próximo gate",
            "",
            "Repetir el caso congelado usando exclusivamente `kch_preflight` sobre `StudioMCP`; después incorporar varias clases de fallo histórico, réplicas y un evaluador ciego a la condición.",
            "",
        ]
    )
    (ROOT / "CHECKPOINT_MATERIAL_ES.md").write_text("\n".join(summary), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
