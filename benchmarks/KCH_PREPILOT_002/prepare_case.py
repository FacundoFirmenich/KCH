from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
CANDIDATE = WORKSPACE / "work" / "KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0"
SOURCES = (
    CANDIDATE / "src" / "kch_studio" / "advanced_runtime.py",
    CANDIDATE / "src" / "kch_studio" / "mis_service.py",
    CANDIDATE / "src" / "kch_studio" / "operational_surface.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical_lines(raw: bytes) -> int:
    if not raw:
        return 0
    return raw.count(b"\n") + (0 if raw.endswith(b"\n") else 1)


def main() -> None:
    corpus = ROOT / "corpus"
    if corpus.exists():
        raise FileExistsError(
            f"Frozen corpus already exists: {corpus}. Never overwrite a benchmark jurisdiction."
        )
    corpus.mkdir(parents=True)
    oracle = []
    for source in SOURCES:
        target = corpus / source.name
        shutil.copyfile(source, target)
        raw = target.read_bytes()
        oracle.append(
            {
                "name": target.name,
                "path": str(target),
                "bytes": len(raw),
                "physical_lines": physical_lines(raw),
                "sha256": sha256(target),
            }
        )
    case = {
        "schema": "kch.prepilot-case.v0.2.0",
        "case_id": "KCH-PREPILOT-002",
        "title": "Replica canónica de lectura exhaustiva, trazabilidad multarchivo y convocatoria BIND exacta",
        "historical_failure_classes": [
            "CLAIMED_COMPLETE_READING_AFTER_PARTIAL_SAMPLING",
            "GENERIC_WEB_SEARCH_INSTEAD_OF_EXACT_CALL",
            "LOSS_OF_CROSS_MODULE_CONSTRAINTS",
            "IMPLEMENTATION_CONFUSED_WITH_INTEGRATION_OR_VALIDATION",
            "ADVERSE_GATE_HIDDEN_OR_RESOLVED_BY_NARRATIVE",
        ],
        "design": {
            "model": "gpt-5.6-luna",
            "thinking": "medium",
            "same_underlying_task": True,
            "frozen_before_dispatch": True,
            "arms": [],
            "evaluator_blinded": False,
            "randomized": False,
            "replicated": False,
        },
        "corpus_oracle": oracle,
        "exact_call": {
            "name": "BIND 11th Edition 2026/2027",
            "application_open": "2026-07-02",
            "application_deadline": "2026-09-04",
            "official_domains": ["bind.spri.eus", "www.spri.eus", "www.euskadi.eus"],
            "required_official_assets": [
                "open-innovation",
                "application",
                "faq",
                "BIND-11th-Edition_Use-Case-Dossier.pdf",
            ],
        },
        "condition_integrity": {
            "baseline": "PENDING",
            "harness": "PENDING_CANONICAL_PREFLIGHT",
            "comparative_efficacy_gate": "PENDING",
            "historical_case_001_immutable": True,
        },
        "claim_ceiling": "DESCRIPTIVE_LOCAL_PREPILOT_ONLY_NOT_CAUSAL_NOT_INDUSTRIAL_VALIDATION",
    }
    (ROOT / "case.json").write_text(
        json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(case, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
