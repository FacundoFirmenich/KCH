from __future__ import annotations

import json
from pathlib import Path

from kch_studio.workbench_suite import WorkbenchSuite


ROOT = Path(__file__).resolve().parent


def main() -> None:
    suite = WorkbenchSuite(ROOT / "generated_workbench")
    receipt = suite.ingest(
        source_kind="EXPERIMENT",
        title="KCH PREPILOT 001 adverse preflight case",
        source_path=ROOT / "HISTORICAL_FAILURE_001.md",
        source_uri="codex://kch-prepilot/KCH-PREPILOT-001/HISTORICAL_FAILURE_001",
        workspace_id="KCH-PREPILOT-FAILURES",
        provenance={
            "case_id": "KCH-PREPILOT-001",
            "baseline_thread_id": "019fecfe-cfde-7f81-b29d-4da9a0d8dfc4",
            "harness_thread_id": "019fecff-08ef-7e53-85dc-53fde6705acf",
            "historical_result_immutable": True,
        },
    )
    result = {
        "schema": "kch.prepilot-real-case-ingest.v0.1.0",
        "receipt": receipt,
        "protocols": suite.protocols("KCH-PREPILOT-FAILURES"),
        "skills": suite.skills(),
        "integrity": suite.verify(),
        "status": suite.status(),
    }
    (ROOT / "real_case_generation_receipt.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "protocols": len(result["protocols"]),
                "skills": len(result["skills"]),
                "skill_state": result["skills"][0]["status"] if result["skills"] else None,
                "integrity": result["integrity"]["gate"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
