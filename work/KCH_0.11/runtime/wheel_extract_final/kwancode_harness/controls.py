from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .canonical import sha256_json

Verdict = str
VALID_VERDICTS = {"PASS", "BLOCK", "ABSTAIN", "UNAVAILABLE"}
EVIDENCE_ROLES = {"DIRECT", "DERIVED", "TRANSPORT", "EXECUTION", "OUTCOME"}


@dataclass(frozen=True, slots=True)
class Control:
    control_id: str
    name: str
    required_fields: tuple[str, ...]
    evaluator: Callable[[dict[str, Any]], tuple[Verdict, list[str]]]
    evidence_state_at_baseline: str

    def describe(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "name": self.name,
            "required_fields": list(self.required_fields),
            "baseline_evidence_state": self.evidence_state_at_baseline,
            "outcomes": sorted(VALID_VERDICTS),
        }


def _missing(context: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if field not in context or context[field] is None]


def _bool(context: dict[str, Any], key: str) -> bool:
    if not isinstance(context.get(key), bool):
        raise ValueError(f"{key} must be boolean")
    return context[key]


def _r01(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    return ("PASS", []) if c["governing_objective_id"] == c["candidate_objective_id"] else ("BLOCK", ["OBJECTIVE_DRIFT"])


def _r02(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    if c["source_project_id"] == c["target_project_id"]:
        return "PASS", []
    if _bool(c, "transfer_contract_verified") and not _bool(c, "authority_inherited"):
        return "PASS", ["CROSS_PROJECT_TRANSFER_BOUNDED"]
    return "BLOCK", ["PROJECT_FIREWALL_VIOLATION"]


def _r03(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    requested, granted = set(c["requested_authority"]), set(c["granted_authority"])
    if not _bool(c, "action_classified"):
        return "ABSTAIN", ["ACTION_UNCLASSIFIED"]
    return ("PASS", []) if requested <= granted else ("BLOCK", ["AUTHORITY_EXPANSION"])


def _r04(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    return ("PASS", []) if _bool(c, "external_observer") and _bool(c, "observer_independence_verified") else ("BLOCK", ["SELF_GOVERNANCE_OBSERVER_NOT_INDEPENDENT"])


def _r05(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    valid = all(bool(c[key]) for key in ("scope", "deliverables", "cost_receipt"))
    return ("PASS", []) if valid else ("ABSTAIN", ["PREWORK_COST_SCOPE_RECEIPT_INCOMPLETE"])


def _r06(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    if min(c["token_budget"], c["fanout_budget"], c["projected_tokens"], c["projected_fanout"]) < 0:
        raise ValueError("budgets and projections must be non-negative")
    reasons = []
    if c["projected_tokens"] > c["token_budget"]:
        reasons.append("TOKEN_BUDGET_EXCEEDED")
    if c["projected_fanout"] > c["fanout_budget"]:
        reasons.append("FANOUT_BUDGET_EXCEEDED")
    return ("BLOCK", reasons) if reasons else ("PASS", [])


def _r07(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    if not _bool(c, "probe_applicable"):
        return "PASS", ["PROBE_NOT_APPLICABLE"]
    if not _bool(c, "probe_executed"):
        return "ABSTAIN", ["REQUIRED_CHEAP_PROBE_NOT_EXECUTED"]
    return ("PASS", []) if c["probe_result"] == "PASS" else ("BLOCK", ["CHEAP_PROBE_FAILED"])


def _r08(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    state = c["relevance_state"]
    if state == "DIRECT":
        return "PASS", []
    if state == "TRANSFERABLE":
        return "PASS", ["TRANSFER_CONDITIONS_REQUIRED"] if not c.get("transfer_conditions") else []
    if state == "NOT_APPLICABLE":
        return "BLOCK", ["WORK_IRRELEVANT_TO_GOVERNING_OBJECTIVE"]
    return "ABSTAIN", ["RELEVANCE_UNAVAILABLE"]


def _r09(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    allowed = {"SCIENCE", "PRODUCT", "COMMERCIAL"}
    if c["governing_mode"] not in allowed or c["claim_mode"] not in allowed:
        raise ValueError("invalid governing_mode or claim_mode")
    return ("PASS", []) if c["governing_mode"] == c["claim_mode"] or _bool(c, "boundary_explicit") else ("BLOCK", ["SCIENCE_PRODUCT_BOUNDARY_COLLAPSE"])


def _r10(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    state = c["applicability"]
    if state not in {"DIRECT", "TRANSFERABLE", "NOT_APPLICABLE"}:
        raise ValueError("invalid applicability")
    if state == "TRANSFERABLE" and not c.get("transfer_conditions"):
        return "ABSTAIN", ["TRANSFER_CONDITIONS_UNAVAILABLE"]
    return "PASS", []


def _r11(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    allowed = {"BETTER", "UNCHANGED", "WORSE", "DIFFERENTLY_POSITIONED"}
    if c["position_change"] not in allowed:
        raise ValueError("invalid position_change")
    return ("PASS", []) if c["evidence_delta"] else ("ABSTAIN", ["ADVANCE_MEANING_HAS_NO_EVIDENCE_DELTA"])


def _r12(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    options = c["options"]
    if not isinstance(options, list) or not options:
        return "UNAVAILABLE", ["NO_ALTERNATIVES_RECORDED"]
    if sum(1 for row in options if isinstance(row, dict) and row.get("chosen")) != 1:
        return "ABSTAIN", ["CHOICE_NOT_UNIQUE"]
    if any(not isinstance(row, dict) or "opportunity_cost" not in row for row in options):
        return "ABSTAIN", ["OPPORTUNITY_COST_MISSING"]
    return "PASS", []


def _r13(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    missing = [key for key in ("observed_result", "meaning", "limitations", "next_critical_action") if not c.get(key)]
    return ("ABSTAIN", [f"COMMUNICATION_SECTION_MISSING:{key}" for key in missing]) if missing else ("PASS", [])


def _r14(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    if not _bool(c, "commercial_readiness_claimed"):
        return "PASS", ["NO_COMMERCIAL_READINESS_CLAIM"]
    evidence = c["readiness_evidence"]
    required = {"pilot", "outcomes", "deployment", "authority"}
    return ("PASS", []) if isinstance(evidence, dict) and required <= set(evidence) and all(evidence[key] for key in required) else ("BLOCK", ["COMMERCIAL_READINESS_UNSUPPORTED"])


def _r15(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    claims = c["claims"]
    if not isinstance(claims, list) or not claims:
        return "UNAVAILABLE", ["NO_CLAIMS_SUPPLIED"]
    required = {"claim_id", "source_ids", "execution_id", "jurisdiction"}
    bad = [str(i) for i, claim in enumerate(claims) if not isinstance(claim, dict) or not required <= set(claim) or not all(claim[key] for key in required)]
    return ("BLOCK", ["CLAIM_LINEAGE_INCOMPLETE:" + ",".join(bad)]) if bad else ("PASS", [])


def _r16(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    if not c["canonical_name"] or not c["genealogy"]:
        return "ABSTAIN", ["CANONICAL_IDENTITY_INCOMPLETE"]
    return ("PASS", []) if _bool(c, "collision_free") else ("BLOCK", ["CANONICAL_NAME_COLLISION"])


def _r17(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    corrections = c["corrections"]
    if not isinstance(corrections, list):
        raise ValueError("corrections must be a list")
    unapplied = [str(row.get("correction_id", "UNKNOWN")) for row in corrections if not isinstance(row, dict) or not row.get("applied")]
    return ("BLOCK", ["USER_CORRECTIONS_UNAPPLIED:" + ",".join(unapplied)]) if unapplied else ("PASS", [])


def _r18(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    hits = c["contamination_hits"]
    if not isinstance(hits, list):
        raise ValueError("contamination_hits must be a list")
    return ("BLOCK", ["CROSS_TASK_CONTAMINATION:" + ",".join(map(str, hits))]) if hits else ("PASS", [])


def _r19(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    required = {"source", "governing_objective", "chronology", "evidence_boundary", "pending_gates", "next_action"}
    missing = sorted(key for key in required if not c["handoff"].get(key)) if isinstance(c["handoff"], dict) else sorted(required)
    return ("ABSTAIN", ["HANDOFF_FIELD_MISSING:" + key for key in missing]) if missing else ("PASS", [])


def _r20(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    planned = set(c["planned_artifacts"])
    necessary = set(c["necessary_artifacts"])
    redundant = planned - necessary
    return ("BLOCK", ["UNJUSTIFIED_DOCUMENT_PROLIFERATION:" + ",".join(sorted(redundant))]) if redundant and not c.get("redundancy_justification") else ("PASS", [])


def _r21(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    rows = c["adverse_results"]
    if not isinstance(rows, list):
        raise ValueError("adverse_results must be a list")
    bad = [str(i) for i, row in enumerate(rows) if not isinstance(row, dict) or not row.get("retained") or not row.get("design_update")]
    return ("BLOCK", ["ADVERSE_RESULT_NOT_PRESERVED:" + ",".join(bad)]) if bad else ("PASS", [])


def _r22(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    rows = c["repairs"]
    required = {"original_sha256", "defect", "change", "validation", "replacement_sha256"}
    bad = [str(i) for i, row in enumerate(rows) if not isinstance(row, dict) or not required <= set(row) or row.get("original_sha256") == row.get("replacement_sha256")]
    return ("ABSTAIN", ["REPAIR_LEDGER_INCOMPLETE:" + ",".join(bad)]) if bad else ("PASS", [])


def _r23(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    return ("BLOCK", ["HUMAN_INTERRUPT_PENDING"]) if _bool(c, "human_interrupt_pending") else ("PASS", [])


def _r24(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    if _bool(c, "decision_equivalent") and not _bool(c, "evidence_contract_equivalent"):
        return "BLOCK", ["DECISION_EQUIVALENCE_WITH_EVIDENCE_DIVERGENCE"]
    return "PASS", []


def _r25(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    roles = c["evidence_roles"]
    if not isinstance(roles, dict) or not roles:
        return "UNAVAILABLE", ["EVIDENCE_ROLES_UNAVAILABLE"]
    invalid = sorted({str(role) for role in roles.values()} - EVIDENCE_ROLES)
    return ("BLOCK", ["INVALID_EVIDENCE_ROLES:" + ",".join(invalid)]) if invalid else ("PASS", [])


def _r26(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    if c["sample_count"] < 2:
        return "UNAVAILABLE", ["METRIC_SAMPLE_INSUFFICIENT"]
    if c["unique_values"] < 2 or not _bool(c, "metric_discriminates"):
        return "BLOCK", ["DEGENERATE_METRIC"]
    return "PASS", []


def _r27(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    if not _bool(c, "transport_complete"):
        return "UNAVAILABLE", ["TRANSPORT_INCOMPLETE"]
    failures = c["unit_failures"]
    if not isinstance(failures, list):
        raise ValueError("unit_failures must be a list")
    return ("BLOCK", ["UNIT_FAILURES:" + ",".join(map(str, failures))]) if failures else ("PASS", [])


def _r28(c: dict[str, Any]) -> tuple[Verdict, list[str]]:
    if _bool(c, "evidence_available"):
        return "PASS", []
    if c["authority_after_loss"] in {"NONE", "READ_ONLY", "SHADOW"}:
        return "PASS", ["AUTHORITY_DEGRADED_ON_EVIDENCE_LOSS"]
    return "BLOCK", ["AUTHORITY_NOT_DEGRADED_AFTER_EVIDENCE_LOSS"]


_SPECS = [
    ("R01", "Bloqueo del objetivo gobernante", ("governing_objective_id", "candidate_objective_id"), _r01, "NO_DIRECT_EXECUTABLE_EVIDENCE"),
    ("R02", "Firewall entre proyectos", ("source_project_id", "target_project_id", "transfer_contract_verified", "authority_inherited"), _r02, "PARTIAL_EXECUTABLE"),
    ("R03", "Compilador de autorización", ("requested_authority", "granted_authority", "action_classified"), _r03, "PARTIAL_EXECUTABLE"),
    ("R04", "KCH aplicado al propio agente", ("external_observer", "observer_independence_verified"), _r04, "NO_DIRECT_EXECUTABLE_EVIDENCE"),
    ("R05", "Recibo previo de coste y alcance", ("scope", "deliverables", "cost_receipt"), _r05, "NO_DIRECT_EXECUTABLE_EVIDENCE"),
    ("R06", "Presupuesto de tokens y fan-out", ("token_budget", "fanout_budget", "projected_tokens", "projected_fanout"), _r06, "NO_DIRECT_EXECUTABLE_EVIDENCE"),
    ("R07", "Probe barato obligatorio", ("probe_applicable", "probe_executed", "probe_result"), _r07, "PROTOCOL_ONLY"),
    ("R08", "Parada por irrelevancia", ("relevance_state",), _r08, "NO_DIRECT_EXECUTABLE_EVIDENCE"),
    ("R09", "Firewall ciencia-producto", ("governing_mode", "claim_mode", "boundary_explicit"), _r09, "PARTIAL_CONTRACT"),
    ("R10", "Mapa directo-transferible-no aplicable", ("applicability",), _r10, "NO_DIRECT_EXECUTABLE_EVIDENCE"),
    ("R11", "Auditor del significado de avance", ("position_change", "evidence_delta"), _r11, "PARTIAL_EXECUTABLE"),
    ("R12", "Ledger de coste de oportunidad", ("options",), _r12, "NO_DIRECT_EXECUTABLE_EVIDENCE"),
    ("R13", "Control de comunicación completa", ("observed_result", "meaning", "limitations", "next_critical_action"), _r13, "PARTIAL_EXECUTABLE"),
    ("R14", "Firewall de readiness comercial", ("commercial_readiness_claimed", "readiness_evidence"), _r14, "EXPERIMENT_EXECUTABLE_SEPARATE"),
    ("R15", "Enlace claim-fuente-ejecución-jurisdicción", ("claims",), _r15, "PARTIAL_EXECUTABLE"),
    ("R16", "Registro canónico de nombre y genealogía", ("canonical_name", "genealogy", "collision_free"), _r16, "PARTIAL_EXECUTABLE"),
    ("R17", "Ledger de últimas correcciones del usuario", ("corrections",), _r17, "PARTIAL_EXECUTABLE"),
    ("R18", "Detector de contaminación entre tareas", ("contamination_hits",), _r18, "PARTIAL_EXECUTABLE"),
    ("R19", "Validador de handoff mínimo y suficiente", ("handoff",), _r19, "PARTIAL_EXECUTABLE"),
    ("R20", "Limitador de proliferación documental", ("planned_artifacts", "necessary_artifacts"), _r20, "NO_DIRECT_EXECUTABLE_EVIDENCE"),
    ("R21", "Extractor de valor de resultados adversos", ("adverse_results",), _r21, "PARTIAL_EXECUTABLE"),
    ("R22", "Ledger de reparación", ("repairs",), _r22, "PARTIAL_INFRASTRUCTURE"),
    ("R23", "Interrupción humana prioritaria", ("human_interrupt_pending",), _r23, "NO_DIRECT_EXECUTABLE_EVIDENCE"),
    ("R24", "Auditor de divergencia decisión-evidencia", ("decision_equivalent", "evidence_contract_equivalent"), _r24, "EXPERIMENT_EXECUTABLE_SEPARATE"),
    ("R25", "Canonicalizador de roles de evidencia", ("evidence_roles",), _r25, "PARTIAL_EXECUTABLE"),
    ("R26", "Veto de métricas degeneradas", ("sample_count", "unique_values", "metric_discriminates"), _r26, "EXPERIMENT_OBSERVED_NO_RUNTIME_VETO"),
    ("R27", "Control de completitud de transporte y fallos unitarios", ("transport_complete", "unit_failures"), _r27, "PARTIAL_EXECUTABLE"),
    ("R28", "Degradación automática de autoridad cuando se pierde evidencia", ("evidence_available", "authority_after_loss"), _r28, "PARTIAL_EXECUTABLE"),
]

CONTROL_CATALOG: dict[str, Control] = {row[0]: Control(*row) for row in _SPECS}


def evaluate_control(control_id: str, context: dict[str, Any]) -> dict[str, Any]:
    if control_id not in CONTROL_CATALOG:
        raise ValueError("unknown KCH reflexive control")
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    control = CONTROL_CATALOG[control_id]
    missing = _missing(context, control.required_fields)
    if missing:
        verdict, reasons = "UNAVAILABLE", ["MISSING_FIELD:" + field for field in missing]
    else:
        verdict, reasons = control.evaluator(context)
    if verdict not in VALID_VERDICTS:
        raise AssertionError("invalid control verdict")
    core = {
        "schema": "kch.control.receipt.v0.11.0",
        "release": "KCH 0.11",
        "control_id": control.control_id,
        "control_name": control.name,
        "verdict": verdict,
        "reasons": sorted(set(reasons)),
        "context_sha256": sha256_json(context),
        "authority_created": False,
        "automatic_promotion": False,
    }
    return {**core, "receipt_sha256": sha256_json(core)}


def describe_controls() -> dict[str, Any]:
    rows = [CONTROL_CATALOG[key].describe() for key in sorted(CONTROL_CATALOG)]
    return {
        "schema": "kch.control-catalog.v0.11.0",
        "release": "KCH 0.11",
        "count": len(rows),
        "controls": rows,
        "catalog_sha256": sha256_json(rows),
        "implementation_claim": "28_INVOKABLE_DETERMINISTIC_CONTROL_CONTRACTS",
        "effectiveness_claim": "NOT_ESTABLISHED_WITH_REAL_USE_FOR_ALL_CONTROLS",
    }
