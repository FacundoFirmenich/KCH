from __future__ import annotations

import json
import re
import sys
from typing import Any

from kch_native_state import connect, setting


MODES = ("adaptive", "exploratory", "balanced", "strict", "constitutional")
MODE_LEVELS = {
    "exploratory": 35,
    "balanced": 65,
    "strict": 85,
    "constitutional": 100,
}
HARD_FLOORS = {
    "external_platform": 100,
    "evidence_truth": 100,
    "authority_permission": 100,
    "constitutional_locks": 100,
    "destructive_recovery": 90,
    "scientific_claims": 80,
    "experimental_design": 55,
    "production_mutation": 75,
    "construct_implementation": 30,
    "creative_conjecture": 0,
    "response_formality": 0,
    "documentation_ceremony": 0,
}
FIELD_DEFAULTS = {
    "external_platform": 100,
    "evidence_truth": 100,
    "authority_permission": 100,
    "constitutional_locks": 100,
    "destructive_recovery": 95,
    "scientific_claims": 90,
    "experimental_design": 82,
    "production_mutation": 90,
    "construct_implementation": 65,
    "creative_conjecture": 35,
    "response_formality": 50,
    "documentation_ceremony": 45,
}

HIGH_RE = re.compile(
    r"(?i)\b(audit|audita|freeze|congela|evidence|evidencia|production|produccion|"
    r"deploy|desplieg|release|publica|borra|delete|legal|medic|financial|financier)\b"
)
EXPERIMENT_RE = re.compile(
    r"(?i)\b(experiment|experimento|validate|validacion|benchmark|causal|holdout|preregister)\b"
)
EXPLORATORY_RE = re.compile(
    r"(?i)\b(brainstorm|explora|conjetura|creativ|audaz|hipotesis|idea|construct)\b"
)


def clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def json_setting(db: Any, key: str) -> dict[str, int]:
    raw = setting(db, key)
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return {str(k): clamp(int(v)) for k, v in value.items()}


def infer_adaptive_level(prompt: str) -> tuple[int, str]:
    if HIGH_RE.search(prompt):
        return 90, "HIGH_STAKES_OR_CUSTODY"
    if EXPERIMENT_RE.search(prompt):
        return 82, "EXPERIMENTAL"
    if EXPLORATORY_RE.search(prompt):
        return 40, "EXPLORATORY_CONSTRUCT"
    return 65, "BALANCED_DEFAULT"


def resolve(db: Any, prompt: str = "") -> dict[str, Any]:
    mode = (setting(db, "rigor_mode") or "adaptive").lower()
    if mode not in MODES:
        mode = "adaptive"
    configured = setting(db, "rigor_default_intensity")
    configured_level = clamp(int(configured)) if configured else 65
    if mode == "adaptive":
        level, reason = infer_adaptive_level(prompt)
        level = clamp(round((level + configured_level) / 2))
    else:
        level = MODE_LEVELS[mode]
        reason = "USER_FIXED_PROFILE"

    overrides = json_setting(db, "rigor_field_overrides_json")
    fields: dict[str, dict[str, Any]] = {}
    for name, default in FIELD_DEFAULTS.items():
        requested = overrides.get(name, clamp(default + level - 65))
        effective = max(requested, HARD_FLOORS[name])
        fields[name] = {
            "requested": requested,
            "hard_floor": HARD_FLOORS[name],
            "effective": effective,
            "relaxable": HARD_FLOORS[name] < 100,
        }
    return {
        "schema": "kch.contractual-rigor-fader.v1",
        "mode": mode,
        "intensity": level,
        "reason": reason,
        "fields": fields,
        "non_relaxable": [
            "external_platform",
            "evidence_truth",
            "authority_permission",
            "constitutional_locks",
        ],
        "does_not_create_authority": True,
    }


def hook_context(event: str, profile: dict[str, Any]) -> dict[str, Any]:
    flexible = profile["fields"]
    text = (
        "KCH Contractual Rigor Fader: "
        f"mode={profile['mode']} intensity={profile['intensity']}/100 reason={profile['reason']}. "
        f"construct={flexible['construct_implementation']['effective']}, "
        f"experiment={flexible['experimental_design']['effective']}, "
        f"creative={flexible['creative_conjecture']['effective']}, "
        f"claims={flexible['scientific_claims']['effective']}. "
        "La intensidad es graduable por jurisdiccion; no relaja verdad de evidencia, "
        "autoridad/permiso, llaves constitucionales ni restricciones externas."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }
    }


def main() -> int:
    payload = json.load(sys.stdin)
    event = str(payload.get("hook_event_name", "UNKNOWN"))
    if event not in {"SessionStart", "UserPromptSubmit"}:
        return 0
    prompt = str(payload.get("prompt", ""))
    db = connect()
    try:
        profile = resolve(db, prompt)
    finally:
        db.close()
    sys.stdout.write(json.dumps(hook_context(event, profile), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
