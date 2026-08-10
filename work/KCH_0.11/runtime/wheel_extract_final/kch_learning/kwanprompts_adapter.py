from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .service import LearningService


def import_kwanprompts_ts01r(service: LearningService, result_path: Path, fixture_path: Path) -> list[dict]:
    result_bytes = result_path.read_bytes()
    result = json.loads(result_bytes.decode("utf-8"))
    fixture = json.loads(fixture_path.read_text(encoding="utf-8-sig"))
    cases = {case["case_id"]: case for case in fixture["cases"]}
    receipts = []
    for row in result["cases"]:
        case = cases[row["case_id"]]
        observed = row["observed"]
        receipts.append(
            service.register_decision(
                {
                    "decision_id": f"kwanprompts.ts01r.{row['case_id']}",
                    "component": "KwanPrompts",
                    "decision_type": "FIRST_SEPARATOR_CLASSIFICATION",
                    "summary": f"Classified {row['case_id']} as {observed['disposition']} / {observed['branch']}",
                    "rationale": "Deterministic KwanPrompts v0.1.0 first-separator rules over an exact preserved message.",
                    "alternatives": ["STRATEGIC_OR_INFORMATIVE", "INTERMEDIATE_OR_IRRELEVANT", "REVIEW_REQUIRED"],
                    "evidence": [
                        {"raw_sha256": observed["raw_sha256"]},
                        {"ts01r_result_sha256": hashlib.sha256(result_bytes).hexdigest()},
                        {"expected_exact_match": row["expected_exact_match"]},
                        {"parent_semantic_identity": row["parent_semantic_identity"]},
                    ],
                    "uncertainty": "LOCAL_SEVEN_MESSAGE_CONFORMANCE_ONLY",
                    "consequence": "Routes the message to immediate strategic handling, intermediate handling, or explicit review without canonization.",
                    "source_uri": str(result_path.resolve()),
                    "policy_version": "kwanprompts.first_separator.v0.1.0-final",
                    "claim_scope": "DETERMINISTIC_LOCAL_CONFORMANCE_ON_SEVEN_REAL_MESSAGES",
                    "gate_status": "PASS" if row["expected_exact_match"] else "FAIL",
                    "risk_level": "MEDIUM",
                    "raw_message_preview": case["raw_text"][:240],
                }
            )
        )
    return receipts
