from __future__ import annotations

import json
import re
import sys
from typing import Any

from kch_native_state import (
    canonical,
    classify_tool_operation,
    connect,
    consume_authorization,
    extract_resources,
    find_or_create_proposal,
    log_event,
    matching_locks,
    setting,
    sha256_text,
    utc_now,
)


PERSISTENCE_RE = re.compile(
    r"(?i)\b(no\s+pares|no\s+te\s+pares|hasta\s+(?:haber\s+)?(?:terminado|completado)|"
    r"persiste|tira\s+millas|prosigue|contin(?:u|ú)a\s+hasta)\b"
)
STOP_RE = re.compile(
    r"(?i)^\s*(?:para|pará|detente|frena|cancela|cancelá)(?:\s+(?:todo|la\s+tarea|este\s+trabajo))?[.!\s]*$"
)


def emit(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def context(event: str, text: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }
    }


def main() -> int:
    payload = json.load(sys.stdin)
    event = payload.get("hook_event_name", "UNKNOWN")
    db = connect()
    try:
        log_event(db, event, payload)
        if event == "SessionStart":
            notice = ""
            if setting(db, "startup_notice") == "true":
                notice = " Ledger local exacto y aviso de arranque activos; el usuario puede configurarlos."
            emit(
                context(
                    event,
                    "KCH 0.11.33 nativo activo como superarnés^[+2]: un arnés que gobierna al arnés. "
                    "Jerarquía: HARNESS > AGENTS > RULES. "
                    "Preserva objetivo, jurisdiccion, evidencia adversa y capability != permission != authority != execution. "
                    "LIBRESOURCE: vocacionalmente soberano, compatible por construccion y sin flush prematuro. "
                    "Usa primero AGENTS/skills/hooks/rules/herramientas nativas; MCP solo si una capacidad externa no tiene via nativa. "
                    "PHL autorizado pero no entrenado ni ejecutado realmente. Llaves constitucionales: "
                    + setting(db, "locks_enabled")
                    + ". Modo de respuesta: "
                    + setting(db, "response_mode")
                    + "."
                    + notice,
                )
            )
        elif event == "UserPromptSubmit":
            prompt = str(payload.get("prompt", ""))
            session_id = str(payload.get("session_id", ""))
            row = db.execute("SELECT governing_prompt FROM session_state WHERE session_id=?", (session_id,)).fetchone()
            governing = row[0] if row and row[0] else prompt
            previous_persistence = db.execute(
                "SELECT persistence_required FROM session_state WHERE session_id=?", (session_id,)
            ).fetchone()
            if STOP_RE.fullmatch(prompt):
                persistence = 0
            else:
                persistence = 1 if (
                    PERSISTENCE_RE.search(prompt)
                    or (previous_persistence and previous_persistence[0])
                ) else 0
            db.execute(
                "INSERT INTO session_state(session_id,governing_prompt,governing_prompt_sha256,persistence_required,updated_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET "
                "persistence_required=excluded.persistence_required, updated_at=excluded.updated_at",
                (session_id, governing, sha256_text(governing), persistence, utc_now()),
            )
            db.commit()
            emit(
                context(
                    event,
                    "KCH: trata este turno como adicion a la mision gobernante salvo reemplazo explicito. "
                    "No pidas contexto ya disponible, no sustituyas ejecucion por preguntas laterales y cierra checkpoints materiales en castellano. "
                    "Selecciona la integracion nativa mas directa antes de considerar MCP.",
                )
            )
        elif event == "PreToolUse":
            tool_name = str(payload.get("tool_name", ""))
            tool_input = payload.get("tool_input", {})
            if setting(db, "locks_enabled") != "true":
                return 0
            resources = extract_resources(tool_name, tool_input, str(payload.get("cwd", "")))
            operation_class = classify_tool_operation(tool_name, tool_input)
            if operation_class == "READ":
                emit(
                    context(
                        event,
                        "KCH classified this operation as an attested simple read; mutation locks do not apply.",
                    )
                )
                return 0
            locks = matching_locks(db, resources)
            if not locks:
                return 0
            args_sha = sha256_text(canonical(tool_input))
            proposal = find_or_create_proposal(
                db,
                str(payload.get("session_id", "")),
                payload.get("turn_id"),
                tool_name,
                tool_input,
                resources,
            )
            consumed = consume_authorization(
                db,
                str(payload.get("session_id", "")),
                tool_name,
                args_sha,
                str(payload.get("tool_use_id", "")),
            )
            if consumed:
                emit(
                    context(
                        event,
                        f"KCH consumio atomicamente la autorizacion de un uso {consumed}; no puede reutilizarse.",
                    )
                )
                return 0
            lock_ids = ",".join(row["id"] for row in locks)
            emit(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            "KCH_BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED "
                            f"proposal={proposal['id']} args_sha256={proposal['args_sha256']} locks={lock_ids} "
                            f"operation={operation_class}. "
                            "Explique razon, impacto y recuperacion con kch_native_admin.py propose; "
                            "solo el usuario puede autorizar desde un terminal interactivo confiable."
                        ),
                    }
                }
            )
        elif event == "PostToolUse":
            response = canonical(payload.get("tool_response", {}))
            if "Script running with cell ID" in response or "running with cell ID" in response:
                emit(
                    context(
                        event,
                        "KCH detecto una ejecucion aun viva: monitoriza proceso, log y artefactos hasta estado terminal; no esperes a que el usuario pida resultados.",
                    )
                )
        elif event == "Stop":
            session_id = str(payload.get("session_id", ""))
            row = db.execute(
                "SELECT persistence_required FROM session_state WHERE session_id=?", (session_id,)
            ).fetchone()
            if row and row[0] and not payload.get("stop_hook_active", False):
                emit(
                    {
                        "decision": "block",
                        "reason": (
                            "KCH objective-continuity gate: realiza una pasada adicional. Reconcilia procesos, gates, "
                            "artefactos y misión gobernante; sólo cierra si alcanzaste una condición terminal real o un bloqueo demostrado."
                        ),
                    }
                )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
