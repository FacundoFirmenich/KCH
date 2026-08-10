from __future__ import annotations

import hashlib
import json
from typing import Any


class RigorError(ValueError):
    pass


CLAIM_RANK = {
    "NONE": 0,
    "HYPOTHESIS": 1,
    "INTERNAL_SIGNAL": 2,
    "INTERNAL_CHARACTERIZATION": 3,
    "PILOT_EVIDENCE": 4,
    "CONFIRMATORY_LOCAL": 5,
    "EXTERNAL_SCOPED": 6,
    "PRODUCTION_READY": 7,
}

PROFILES: dict[str, dict[str, Any]] = {
    "R0_IDEATION_SANDBOX": {
        "rank": 0, "generative_latitude": 5, "adaptive_latitude": 5,
        "custody_strictness": 5, "claim_ceiling": "HYPOTHESIS", "execution_ceiling": "NONE",
    },
    "R1_DRAFTING": {
        "rank": 1, "generative_latitude": 5, "adaptive_latitude": 4,
        "custody_strictness": 5, "claim_ceiling": "HYPOTHESIS", "execution_ceiling": "NONE",
    },
    "R2_INTERNAL_EXPLORATION": {
        "rank": 2, "generative_latitude": 5, "adaptive_latitude": 5,
        "custody_strictness": 5, "claim_ceiling": "INTERNAL_SIGNAL", "execution_ceiling": "REVERSIBLE",
    },
    "R3_INTERNAL_CHARACTERIZATION": {
        "rank": 3, "generative_latitude": 4, "adaptive_latitude": 4,
        "custody_strictness": 5, "claim_ceiling": "INTERNAL_CHARACTERIZATION", "execution_ceiling": "REVERSIBLE",
    },
    "R4_PILOT": {
        "rank": 4, "generative_latitude": 3, "adaptive_latitude": 2,
        "custody_strictness": 5, "claim_ceiling": "PILOT_EVIDENCE", "execution_ceiling": "REVERSIBLE",
    },
    "R5_CONFIRMATORY": {
        "rank": 5, "generative_latitude": 1, "adaptive_latitude": 0,
        "custody_strictness": 5, "claim_ceiling": "CONFIRMATORY_LOCAL", "execution_ceiling": "REVERSIBLE",
    },
    "R6_EXTERNAL_RELEASE": {
        "rank": 6, "generative_latitude": 1, "adaptive_latitude": 0,
        "custody_strictness": 5, "claim_ceiling": "EXTERNAL_SCOPED", "execution_ceiling": "NONE",
    },
    "R7_PRODUCTION_CRITICAL": {
        "rank": 7, "generative_latitude": 0, "adaptive_latitude": 0,
        "custody_strictness": 5, "claim_ceiling": "PRODUCTION_READY", "execution_ceiling": "IRREVERSIBLE_WITH_AUTHORITY",
    },
}

PURPOSE_PROFILE = {
    "IDEATION": "R0_IDEATION_SANDBOX",
    "DRAFT_WRITING": "R1_DRAFTING",
    "DESIGN_DRAFT": "R1_DRAFTING",
    "INTERNAL_EXPLORATION": "R2_INTERNAL_EXPLORATION",
    "INTERNAL_CHARACTERIZATION": "R3_INTERNAL_CHARACTERIZATION",
    "PILOT": "R4_PILOT",
    "CONFIRMATORY": "R5_CONFIRMATORY",
    "EXTERNAL_COMMUNICATION": "R6_EXTERNAL_RELEASE",
    "PRODUCTION_DECISION": "R7_PRODUCTION_CRITICAL",
}

AUDIENCE_FLOOR = {
    "PRIVATE": 0,
    "INTERNAL_TEAM": 2,
    "EXTERNAL_REVIEW": 4,
    "PUBLIC": 6,
    "PRODUCTION_SYSTEM": 7,
}

RISK_FLOOR = {"LOW": 0, "MODERATE": 2, "HIGH": 4, "IRREVERSIBLE": 7}

SCOPES = {"CLAIM", "ACTION", "ARTIFACT", "GLOBAL"}
ORIGINS = {"USER", "SAFETY", "PREREGISTRATION", "PUBLICATION", "SYSTEM"}
CONSTRAINTS = {
    "PRESERVE_PARENT",
    "REQUIRE_SEPARATE_BRANCH",
    "NO_CONFIRMATORY_PROMOTION",
    "NO_POST_RESULT_ADAPTATION_IN_PARENT",
    "NO_IRREVERSIBLE_EXECUTION",
    "NO_SYNTHETIC_AS_EMPIRICAL_EVIDENCE",
    "STOP_RESEARCH_LINE",
}
ADAPTIVE_ACTIONS = {"ADAPT_DESIGN_AFTER_RESULTS", "ADD_REPLICATIONS_AFTER_RESULTS", "CHANGE_PRIMARY_ENDPOINT_AFTER_RESULTS"}
DRAFT_ACTIONS = {"GENERATE_HYPOTHESES", "DRAFT_TEXT", "DRAFT_DESIGN", "PROPOSE_PILOT"}
VALID_ACTIONS = ADAPTIVE_ACTIONS | DRAFT_ACTIONS | {
    "CREATE_LABELED_SYNTHETIC_FIXTURES",
    "CREATE_SEPARATE_EXTENSION",
    "REINTERPRET_FROZEN_RESULT",
    "EXECUTE_REVERSIBLE",
    "EXECUTE_IRREVERSIBLE",
    "PUBLISH",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def receipt(value: dict[str, Any]) -> dict[str, Any]:
    body = {**value, "mode": "SHADOW_ONLY", "authority_created": False}
    body["receipt_sha256"] = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return body


def required_text(value: Any, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise RigorError(f"{field} must be non-empty")
    return text


def required_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise RigorError(f"{field} must be boolean")
    return value


def profile_by_rank(rank: int) -> str:
    return next(key for key, value in PROFILES.items() if value["rank"] == rank)


def normalize_protocols(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        raise RigorError("protocols must be a list")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict):
            raise RigorError("each protocol must be an object")
        protocol_id = required_text(raw.get("protocol_id"), "protocol_id")
        if protocol_id in seen:
            raise RigorError("protocol_id values must be unique")
        seen.add(protocol_id)
        scope = required_text(raw.get("scope"), "scope")
        origin = required_text(raw.get("origin"), "origin")
        constraints = raw.get("constraints")
        if scope not in SCOPES or origin not in ORIGINS:
            raise RigorError("invalid protocol scope or origin")
        if not isinstance(constraints, list) or not constraints or len(set(constraints)) != len(constraints):
            raise RigorError("protocol constraints must be a non-empty unique list")
        unknown = set(constraints) - CONSTRAINTS
        if unknown:
            raise RigorError(f"unknown protocol constraints: {sorted(unknown)}")
        result.append({"protocol_id": protocol_id, "scope": scope, "origin": origin, "constraints": list(constraints)})
    return result


def resolve_profile(value: dict[str, Any]) -> dict[str, Any]:
    purpose = required_text(value.get("purpose"), "purpose")
    audience = required_text(value.get("audience"), "audience")
    risk = required_text(value.get("risk"), "risk")
    if purpose not in PURPOSE_PROFILE or audience not in AUDIENCE_FLOOR or risk not in RISK_FLOOR:
        raise RigorError("invalid purpose, audience or risk")
    base = PURPOSE_PROFILE[purpose]
    floor = max(PROFILES[base]["rank"], AUDIENCE_FLOOR[audience], RISK_FLOOR[risk])
    selected = profile_by_rank(floor)
    reasons = [f"PURPOSE:{purpose}"]
    if AUDIENCE_FLOOR[audience] > PROFILES[base]["rank"]:
        reasons.append(f"AUDIENCE_FLOOR:{audience}")
    if RISK_FLOOR[risk] > max(PROFILES[base]["rank"], AUDIENCE_FLOOR[audience]):
        reasons.append(f"RISK_FLOOR:{risk}")
    requested = value.get("requested_profile")
    if requested is not None:
        requested = required_text(requested, "requested_profile")
        if requested not in PROFILES:
            raise RigorError("unknown requested_profile")
        if PROFILES[requested]["rank"] >= floor:
            selected = requested
            reasons.append("EXPLICIT_PROFILE_ACCEPTED")
        else:
            reasons.append("EXPLICIT_PROFILE_BELOW_AUDIENCE_OR_RISK_FLOOR_REJECTED")
    profile = PROFILES[selected]
    return receipt({
        "schema": "kch.rigor.profile.receipt.v0.1.0",
        "purpose": purpose,
        "audience": audience,
        "risk": risk,
        "selected_profile": selected,
        "profile": profile,
        "selection_reasons": reasons,
        "nonnegotiable_invariants": [
            "NO_FALSE_DATA_AS_REAL",
            "LABEL_SYNTHETIC_CONTENT",
            "PRESERVE_FROZEN_PARENT",
            "SEPARATE_FACT_CLAIM_AND_ACTION_JUDGMENTS",
            "CLAIM_CEILING_IS_NOT_RESEARCH_CEILING",
        ],
    })


def adjudicate_action(value: dict[str, Any]) -> dict[str, Any]:
    profile_id = required_text(value.get("profile_id"), "profile_id")
    action = required_text(value.get("action"), "action")
    requested_claim = required_text(value.get("requested_claim"), "requested_claim")
    if profile_id not in PROFILES or action not in VALID_ACTIONS or requested_claim not in CLAIM_RANK:
        raise RigorError("invalid profile_id, action or requested_claim")
    parent_frozen = required_bool(value.get("parent_frozen"), "parent_frozen")
    after_results = required_bool(value.get("after_results"), "after_results")
    explicit_user_authority = required_bool(value.get("explicit_user_authority"), "explicit_user_authority")
    reversible = required_bool(value.get("reversible"), "reversible")
    new_branch_id = str(value.get("new_branch_id") or "").strip()
    evidence_use = required_text(value.get("evidence_use", "NOT_APPLICABLE"), "evidence_use")
    protocols = normalize_protocols(value.get("protocols", []))

    profile = PROFILES[profile_id]
    action_disposition = "ALLOW"
    action_reasons: list[str] = []
    requirements: list[str] = []
    scope_escape_rejected: list[str] = []

    applicable_action_constraints: set[str] = set()
    applicable_artifact_constraints: set[str] = set()
    applicable_claim_constraints: set[str] = set()
    for protocol in protocols:
        targets = {protocol["scope"]} if protocol["scope"] != "GLOBAL" else {"ACTION", "ARTIFACT", "CLAIM"}
        for constraint in protocol["constraints"]:
            if constraint == "STOP_RESEARCH_LINE":
                if "ACTION" in targets and protocol["origin"] in {"USER", "SAFETY"}:
                    applicable_action_constraints.add(constraint)
                else:
                    scope_escape_rejected.append(protocol["protocol_id"] + ":STOP_RESEARCH_LINE")
            elif constraint in {"NO_IRREVERSIBLE_EXECUTION"} and "ACTION" in targets:
                applicable_action_constraints.add(constraint)
            elif constraint in {"PRESERVE_PARENT", "REQUIRE_SEPARATE_BRANCH", "NO_POST_RESULT_ADAPTATION_IN_PARENT"} and "ARTIFACT" in targets:
                applicable_artifact_constraints.add(constraint)
            elif constraint in {"NO_CONFIRMATORY_PROMOTION", "NO_SYNTHETIC_AS_EMPIRICAL_EVIDENCE"} and "CLAIM" in targets:
                applicable_claim_constraints.add(constraint)

    if "STOP_RESEARCH_LINE" in applicable_action_constraints:
        action_disposition = "BLOCK"
        action_reasons.append("AUTHORIZED_STOP_RESEARCH_LINE")
    elif action == "REINTERPRET_FROZEN_RESULT":
        action_disposition = "BLOCK"
        action_reasons.append("FROZEN_PARENT_REWRITE_PROHIBITED")
    elif action == "EXECUTE_IRREVERSIBLE":
        if profile_id != "R7_PRODUCTION_CRITICAL" or not explicit_user_authority or reversible:
            action_disposition = "BLOCK"
            action_reasons.append("IRREVERSIBLE_AUTHORITY_MISSING")
        elif "NO_IRREVERSIBLE_EXECUTION" in applicable_action_constraints:
            action_disposition = "BLOCK"
            action_reasons.append("PROTOCOL_VETO_IRREVERSIBLE_EXECUTION")
    elif action == "EXECUTE_REVERSIBLE" and profile["execution_ceiling"] == "NONE":
        action_disposition = "CONDITIONAL"
        action_reasons.append("PROFILE_HAS_NO_EXECUTION_AUTHORITY")
        requirements.append("TRANSITION_TO_INTERNAL_EXECUTION_PROFILE")
    elif action in ADAPTIVE_ACTIONS and after_results:
        branch_required = (
            parent_frozen
            or profile["rank"] >= 4
            or "REQUIRE_SEPARATE_BRANCH" in applicable_artifact_constraints
            or "NO_POST_RESULT_ADAPTATION_IN_PARENT" in applicable_artifact_constraints
        )
        if branch_required and new_branch_id:
            action_disposition = "ALLOW_WITH_SEPARATE_BRANCH"
            action_reasons.append("POST_RESULT_EXTENSION_SEPARATED_FROM_PARENT")
            requirements.extend(["PRESERVE_PARENT", "LABEL_EXTENSION_POST_RESULT", "RESET_CLAIM_IDENTITY"])
        elif branch_required:
            action_disposition = "CONDITIONAL"
            action_reasons.append("SEPARATE_BRANCH_REQUIRED")
            requirements.extend(["NEW_BRANCH_ID", "PRESERVE_PARENT", "RESET_CLAIM_IDENTITY"])
        elif profile["rank"] in {2, 3}:
            action_disposition = "ALLOW"
            action_reasons.append("INTERNAL_ADAPTATION_ALLOWED_AND_MUST_BE_LOGGED")
            requirements.append("LOG_ADAPTATION_AFTER_RESULTS")
        else:
            action_disposition = "CONDITIONAL"
            action_reasons.append("TRANSITION_TO_INTERNAL_RESEARCH_PROFILE")
            requirements.append("NEW_INTERNAL_PROFILE")
    elif action == "CREATE_LABELED_SYNTHETIC_FIXTURES":
        action_reasons.append("SYNTHETIC_FIXTURES_ALLOWED_FOR_METHOD_OR_SOFTWARE_TEST")
        requirements.extend(["LABEL_SYNTHETIC", "DO_NOT_PRESENT_AS_EMPIRICAL_OBSERVATION"])
        if evidence_use == "EMPIRICAL_EFFECT":
            action_disposition = "BLOCK"
            action_reasons.append("SYNTHETIC_CANNOT_SUPPORT_EMPIRICAL_EFFECT")
    elif action in DRAFT_ACTIONS:
        action_reasons.append("GENERATIVE_WORK_ALLOWED_WITH_PROFILE_LABEL")
        requirements.append("LABEL_UNVERIFIED_FACTUAL_ASSERTIONS")
    elif action == "PUBLISH" and profile["rank"] < 6:
        action_disposition = "CONDITIONAL"
        action_reasons.append("EXTERNAL_RELEASE_PROFILE_REQUIRED")
        requirements.append("TRANSITION_TO_R6_EXTERNAL_RELEASE")

    ceiling = profile["claim_ceiling"]
    ceiling_rank = CLAIM_RANK[ceiling]
    claim_disposition = "ALLOW"
    authorized_claim = requested_claim
    claim_reasons: list[str] = []
    if CLAIM_RANK[requested_claim] > ceiling_rank:
        claim_disposition = "DOWNGRADE_REQUIRED"
        authorized_claim = ceiling
        claim_reasons.append("REQUESTED_CLAIM_EXCEEDS_PROFILE_CEILING")
    if "NO_CONFIRMATORY_PROMOTION" in applicable_claim_constraints and CLAIM_RANK[requested_claim] >= CLAIM_RANK["CONFIRMATORY_LOCAL"]:
        claim_disposition = "DOWNGRADE_REQUIRED"
        authorized_claim = min((ceiling, "INTERNAL_CHARACTERIZATION"), key=lambda item: CLAIM_RANK[item])
        claim_reasons.append("PROTOCOL_FORBIDS_CONFIRMATORY_PROMOTION")
    if action == "CREATE_LABELED_SYNTHETIC_FIXTURES" and evidence_use == "EMPIRICAL_EFFECT":
        claim_disposition = "BLOCK"
        authorized_claim = "NONE"
        claim_reasons.append("SYNTHETIC_EVIDENCE_ROLE_VIOLATION")

    overall = "BLOCK" if action_disposition == "BLOCK" else (
        "ALLOW_WITH_CONDITIONS" if action_disposition == "CONDITIONAL" or claim_disposition != "ALLOW" else action_disposition
    )
    return receipt({
        "schema": "kch.rigor.action.receipt.v0.1.0",
        "profile_id": profile_id,
        "action": action,
        "overall": overall,
        "action_disposition": action_disposition,
        "claim_disposition": claim_disposition,
        "requested_claim": requested_claim,
        "authorized_claim": authorized_claim,
        "action_reasons": sorted(set(action_reasons)),
        "claim_reasons": sorted(set(claim_reasons)),
        "requirements": sorted(set(requirements)),
        "scope_escape_rejected": sorted(set(scope_escape_rejected)),
        "parent_mutation_authorized": False,
        "execution_authorized": False,
    })


def audit_review(value: dict[str, Any]) -> dict[str, Any]:
    purpose = required_text(value.get("governing_purpose"), "governing_purpose")
    if purpose not in PURPOSE_PROFILE:
        raise RigorError("invalid governing_purpose")
    observed_signal = required_bool(value.get("observed_signal"), "observed_signal")
    confirmatory_authority = required_bool(value.get("confirmatory_authority"), "confirmatory_authority")
    extension_requested = required_bool(value.get("extension_requested"), "extension_requested")
    parent_preserved = required_bool(value.get("parent_preserved"), "parent_preserved")
    new_branch_id = str(value.get("new_branch_id") or "").strip()
    protocol_gate_status = required_text(value.get("protocol_gate_status"), "protocol_gate_status")
    proposed_action = required_text(value.get("proposed_action_disposition"), "proposed_action_disposition")
    assertions = value.get("review_assertions")
    judgments = value.get("judgments_present")
    if not isinstance(assertions, list) or len(set(assertions)) != len(assertions):
        raise RigorError("review_assertions must be a unique list")
    if not isinstance(judgments, list) or len(set(judgments)) != len(judgments):
        raise RigorError("judgments_present must be a unique list")

    defects: list[str] = []
    if observed_signal and ("NO_SIGNAL" in assertions or "NO_RESULT" in assertions):
        defects.append("DOWNWARD_EVIDENCE_DISTORTION")
    if observed_signal and "NO_VALUE" in assertions:
        defects.append("UNSUPPORTED_VALUE_ERASURE")
    internal_goal = purpose in {"INTERNAL_EXPLORATION", "INTERNAL_CHARACTERIZATION", "PILOT"}
    if internal_goal and extension_requested and "CONTINUATION_PROHIBITED_BY_CONFIRMATORY_GATE" in assertions:
        defects.extend(["CLAIM_ACTION_CONFLATION", "PROTOCOL_SCOPE_OVERREACH"])
    if internal_goal and extension_requested and proposed_action == "BLOCK" and not confirmatory_authority:
        defects.append("CLAIM_ACTION_CONFLATION")
    if not confirmatory_authority and "CONFIRMATORY_CONFIRMED" in assertions:
        defects.append("UPWARD_EVIDENCE_DISTORTION")
    if "REWRITE_FROZEN_PARENT" in assertions or not parent_preserved:
        defects.append("FROZEN_PARENT_CUSTODY_BREACH")
    required_judgments = {"FACT", "CLAIM", "ACTION"}
    if set(judgments) != required_judgments:
        defects.append("INCOMPLETE_THREE_PLANE_REVIEW")

    defects = sorted(set(defects))
    if defects:
        verdict = "REJECT_REVIEW"
    else:
        verdict = "ACCEPT_REVIEW"
    if internal_goal and extension_requested and not confirmatory_authority:
        recommended_action = "PRESERVE_PARENT_AND_OPEN_INTERNAL_EXTENSION" if new_branch_id else "REQUEST_NEW_BRANCH_ID_FOR_INTERNAL_EXTENSION"
    else:
        recommended_action = "RETAIN_PROPOSED_ACTION" if verdict == "ACCEPT_REVIEW" else "REVISE_REVIEW"
    return receipt({
        "schema": "kch.rigor.review.receipt.v0.1.0",
        "verdict": verdict,
        "defects": defects,
        "protocol_gate_status": protocol_gate_status,
        "fact_judgment": "OBSERVED_SIGNAL_PRESENT" if observed_signal else "NO_OBSERVED_SIGNAL_DECLARED",
        "claim_judgment": "CONFIRMATORY_AUTHORITY_PRESENT" if confirmatory_authority else "NO_CONFIRMATORY_AUTHORITY",
        "action_judgment": recommended_action,
        "corrective_principle": "CLAIM_CEILING_IS_NOT_RESEARCH_CEILING",
        "parent_mutation_authorized": False,
    })


def transition_plan(value: dict[str, Any]) -> dict[str, Any]:
    source = required_text(value.get("from_profile"), "from_profile")
    target = required_text(value.get("to_profile"), "to_profile")
    trigger = required_text(value.get("trigger"), "trigger")
    parent_frozen = required_bool(value.get("parent_frozen"), "parent_frozen")
    new_branch_id = str(value.get("new_branch_id") or "").strip()
    if source not in PROFILES or target not in PROFILES:
        raise RigorError("unknown profile")
    source_rank = PROFILES[source]["rank"]
    target_rank = PROFILES[target]["rank"]
    requirements: list[str] = ["PRESERVE_TRANSITION_RECEIPT"]
    if target_rank < source_rank and parent_frozen:
        if new_branch_id:
            disposition = "ALLOW_WITH_SEPARATE_BRANCH"
            requirements.extend(["PRESERVE_PARENT", "RESET_CLAIM_IDENTITY", "LABEL_REGIME_TRANSITION"])
        else:
            disposition = "CONDITIONAL"
            requirements.extend(["NEW_BRANCH_ID", "PRESERVE_PARENT", "RESET_CLAIM_IDENTITY"])
    elif target_rank >= 5 and source_rank < 5:
        disposition = "CONDITIONAL"
        requirements.extend(["FRESH_PREREGISTRATION", "FUTURE_ONLY_EVIDENCE", "FREEZE_BEFORE_EXECUTION"])
    else:
        disposition = "ALLOW"
        requirements.append("LOG_REGIME_TRANSITION")
    return receipt({
        "schema": "kch.rigor.transition.receipt.v0.1.0",
        "from_profile": source,
        "to_profile": target,
        "trigger": trigger,
        "disposition": disposition,
        "requirements": sorted(set(requirements)),
        "parent_mutation_authorized": False,
    })
