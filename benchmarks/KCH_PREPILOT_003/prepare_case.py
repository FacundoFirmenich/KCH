from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
CANDIDATE = WORKSPACE / "work" / "KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0"
INPUTS = (
    CANDIDATE / "release_build" / "KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R9.zip",
    CANDIDATE / "results" / "KCH_PORTABLE_INSTALL_FAILURE_R6.json",
    CANDIDATE / "results" / "KCH_PORTABLE_POST_INSTALL_FAILURE_R7.json",
    CANDIDATE / "results" / "KCH_PORTABLE_POST_INSTALL_TIMEOUT_R8.json",
    CANDIDATE / "results" / "KCH_R8_INITIALIZE_DIAGNOSIS.json",
    CANDIDATE / "results" / "KCH_PORTABLE_INSTALL_RECEIPT_R9.json",
    CANDIDATE / "results" / "KCH_PORTABLE_POST_INSTALL_GATE_R9.json",
    WORKSPACE / "benchmarks" / "KCH_PREPILOT_001" / "evaluation.json",
    WORKSPACE / "benchmarks" / "KCH_PREPILOT_002" / "evaluation.json",
    CANDIDATE / "docs" / "BIND_2026_PREPILOTO.md",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    oracle = []
    for path in INPUTS:
        if not path.is_file():
            raise FileNotFoundError(path)
        oracle.append(
            {
                "name": path.name,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    case = {
        "schema": "kch.prepilot-case.v0.3.0",
        "case_id": "KCH-PREPILOT-003",
        "title": "Auditoría de release portable, cronología adversa y techo industrial",
        "historical_failure_classes": [
            "SOURCE_TESTS_CONFUSED_WITH_CLEAN_INSTALLATION",
            "FAILED_RELEASES_ERASED_BY_LATEST_PASS",
            "PACKAGE_CONTENT_NOT_RECONCILED_WITH_MANIFEST",
            "LOCAL_GATE_PROMOTED_TO_INDUSTRIAL_VALIDATION",
            "GENERIC_BIND_FIT_INSTEAD_OF_EXACT_USE_CASE_BOUNDARY",
        ],
        "design": {
            "model": "gpt-5.6-luna",
            "thinking": "medium",
            "same_underlying_task": True,
            "arms": [],
            "randomized": False,
            "evaluator_blinded": False,
            "replicated": False,
        },
        "input_oracle": oracle,
        "installed_runtime": {
            "package_root": r"C:\Users\User\AppData\Local\KCH\packages\pre2g-r9\KCH_0.11_PRE2G_R9",
            "runtime_root": r"C:\Users\User\AppData\Local\KCH\runtimes\856fac9b029b",
            "mcp_command": r"C:\Users\User\AppData\Local\KCH\runtimes\856fac9b029b\venv\Scripts\kch-super-mcp-studio.exe",
        },
        "required_release_adjudication": "READY_FOR_CONTROLLED_DOGFOOD_NOT_INDUSTRIAL_VALIDATION",
        "claim_ceiling": "LOCAL_PORTABLE_PREPRODUCTION_AND_PREPILOT_EVIDENCE_ONLY",
    }
    target = ROOT / "case.json"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite benchmark case: {target}")
    target.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(case, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
