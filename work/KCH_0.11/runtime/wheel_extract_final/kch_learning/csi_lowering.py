from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _operation(session_id: str, kind: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"kind": kind, "session_id": session_id, "params": params}


def lower_obl_launch(launch: dict[str, Any], session_provenance: dict[str, Any]) -> dict[str, Any]:
    decision = launch["decision"]
    seed = ["OBL", decision["record_hash"], session_provenance["initiator"], session_provenance["trigger"]]
    session_id = "csi:obl:" + _sha(seed)[:24]
    identitas = {
        "statements": [
            "Onboard user preference at interaction time",
            "Present the exact immutable KCH decision",
            "Permit user feedback but no model self-grading",
            "Learning is future-only and cannot rewrite the current decision",
        ],
        "strata": [["OBL", "ONBOARDING_LEARNING"], ["USER_INVOKED_OR_MODEL_LAUNCHED", "NO_EXECUTION_AUTHORITY"]],
        "explicitly_extensible": False,
    }
    raw_program = [
        _operation(session_id, "OPEN_SESSION", {"label": "kch.preset.obl.launch", "epoch": 0}),
        _operation(session_id, "SEAL_IDENTITAS", identitas),
        _operation(session_id, "ADD_DATUM", {"datum": {"datum_id": "obl-initiation", "role": "CONSTRAINT", "payload": {"initiator": session_provenance["initiator"], "trigger": session_provenance["trigger"]}, "priority": 2, "source": "kch-obl/0.1.0"}}),
        _operation(session_id, "MODE_ON", {"modus": {"modus_id": "ONBOARDING_LEARNING", "description": "One-line dual-launch onboarding", "preserves_identitas": True, "parameters": {"interface": "ONE_LINE_COMMAND_BOX", "future_only": True}}}),
        _operation(session_id, "ADD_DATUM", {"datum": {"datum_id": "reviewed-decision", "role": "EVIDENCE", "payload": decision, "priority": 2, "source": "kch-decision-ledger"}}),
    ]
    return {
        "schema": "kch.learning.csi-lowering.v0.1.0",
        "preset_id": "kch.preset.obl.launch",
        "topological_address": ["KCH", "LEARNING", "OBL", "ONE_LINE_BOX"],
        "identitas_sha256": _sha(identitas),
        "decision_record_hash": decision["record_hash"],
        "raw_csi_program": raw_program,
        "raw_csi_program_sha256": _sha(raw_program),
        "authority_created": False,
        "historical_decision_mutated": False,
    }


def lower_phl_session(session: dict[str, Any], decisions: list[dict[str, Any]], feedback: list[dict[str, Any]]) -> dict[str, Any]:
    record_hashes = [row["record_hash"] for row in decisions]
    seed = ["PHL", session["session_id"], record_hashes, [row["record_hash"] for row in feedback]]
    session_id = "csi:phl:" + _sha(seed)[:24]
    identitas = {
        "statements": [
            "Train the user's personal KCH preference layer retrospectively",
            "Expose extensive evidence-rich KCH decision inventories",
            "Preserve exact 000..100 grades and contextual text without invented calibration",
            "Block ordinary KCH work for the active PHL session",
            "Emit only future-policy candidates pending replay and user approval",
        ],
        "strata": [["PHL", "POST_HOC_LEARNING"], ["EXCLUSIVE_PERSONAL_TRAINING", "NO_RETROACTIVE_REPAIR"]],
        "explicitly_extensible": False,
    }
    raw_program = [
        _operation(session_id, "OPEN_SESSION", {"label": "kch.preset.phl.session", "epoch": 0}),
        _operation(session_id, "SEAL_IDENTITAS", identitas),
        _operation(session_id, "ADD_DATUM", {"datum": {"datum_id": "phl-session-contract", "role": "CONSTRAINT", "payload": {"exclusive": bool(session["exclusive"]), "score_format": "000..100", "known_anchor": {"100": "MAXIMUM_POSITIVE_10_OF_10"}, "reward_mapping": "UNRESOLVED_NO_LINEARITY_ASSUMED"}, "priority": 2, "source": "kch-phl/0.1.0"}}),
        _operation(session_id, "MODE_ON", {"modus": {"modus_id": "POST_HOC_LEARNING", "description": "Exclusive personal retrospective training workbench", "preserves_identitas": True, "parameters": {"interface": "INTERACTIVE_PYTHON_WORKBENCH", "ordinary_work_allowed": False}}}),
    ]
    for index, decision in enumerate(decisions, start=1):
        raw_program.append(_operation(session_id, "ADD_DATUM", {"datum": {"datum_id": f"decision-{index:04d}", "role": "EVIDENCE", "payload": decision, "priority": 2, "source": "kch-decision-ledger"}}))
    for index, item in enumerate(feedback, start=1):
        raw_program.append(_operation(session_id, "ADD_DATUM", {"datum": {"datum_id": f"feedback-{index:04d}", "role": "EVIDENCE", "payload": item, "priority": 2, "source": "kch-learning-ledger"}}))
    return {
        "schema": "kch.learning.csi-lowering.v0.1.0",
        "preset_id": "kch.preset.phl.session",
        "topological_address": ["KCH", "LEARNING", "PHL", "PERSONAL_TRAINING_WORKBENCH"],
        "identitas_sha256": _sha(identitas),
        "decision_record_hashes": record_hashes,
        "feedback_record_hashes": [row["record_hash"] for row in feedback],
        "raw_csi_program": raw_program,
        "raw_csi_program_sha256": _sha(raw_program),
        "authority_created": False,
        "historical_decisions_mutated": False,
    }
