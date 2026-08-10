from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import sqlite_connection

SCOPE_ORDER = ("GLOBAL", "WORKSPACE", "SCO", "TASK", "SESSION", "MESSAGE")
SCOPE_CONTEXT_KEYS = {
    "WORKSPACE": "workspace_id",
    "SCO": "sco_id",
    "TASK": "task_id",
    "SESSION": "session_id",
    "MESSAGE": "message_id",
}
CONSTITUTIONAL_RESPONSE_INVARIANTS = {
    "chat_text_only": True,
    "outputs_out_of_scope": True,
    "outputs_do_not_consume_viewport_budget": True,
    "informative": True,
    "explanatory": True,
    "holistic": True,
    "archival_execution_log_is_not_the_main_answer": True,
    "execution_register_is_never_offered": True,
    "execution_register_is_saved_as_markdown": True,
    "execution_register_notice_is_one_final_line": True,
    "evidence_claims_and_adverse_results_cannot_be_suppressed": True,
    "mandatory_material_checkpoints_cannot_be_suppressed": True,
}


def _preset(
    profile_id: str,
    name: str,
    *,
    target_screens: int | None,
    max_screens: int | None,
    min_scrolls: int | None,
    max_scrolls: int | None,
    length_rule: str,
) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "name": name,
        "description": length_rule,
        "built_in": True,
        "base_profile_id": None,
        "config": {
            "response_channel": "CHAT_AUTHORED_TEXT",
            "length_rule": length_rule,
            "viewport": {
                "unit": "USER_VISIBLE_RENDERED_VIEWPORT",
                "target_screens": target_screens,
                "max_screens": max_screens,
                "min_scrolls": min_scrolls,
                "max_scrolls": max_scrolls,
                "output_footprint_excluded": True,
                "requires_host_measurement": True,
            },
            "composition": {
                "lead_with_substantive_result": True,
                "include_integrated_explanation": True,
                "prefer_synthesis_over_execution_chronology": True,
                "compress_repetition_before_substance": True,
            },
            "execution_trace": {
                "include_by_default": False,
                "followup_policy": "DO_NOT_OFFER",
                "record_policy": "AUTO_SAVE_MARKDOWN",
                "final_notice_policy": "ONE_LINE_PATH_ONLY",
            },
        },
    }


BUILTIN_PROFILES = {
    item["profile_id"]: item
    for item in (
        _preset(
            "builtin.conciso",
            "Conciso",
            target_screens=1,
            max_screens=2,
            min_scrolls=0,
            max_scrolls=1,
            length_rule=(
                "La contestación redactada debe poder leerse en un pantallazo; como límite, "
                "dos pantallas o un scroll, sin contar outputs."
            ),
        ),
        _preset(
            "builtin.explicativo",
            "Explicativo",
            target_screens=None,
            max_screens=None,
            min_scrolls=2,
            max_scrolls=5,
            length_rule=(
                "La contestación redactada debe ocupar aproximadamente entre dos y cinco "
                "scrolls, sin contar outputs."
            ),
        ),
        _preset(
            "builtin.extenso",
            "Extenso",
            target_screens=None,
            max_screens=None,
            min_scrolls=None,
            max_scrolls=None,
            length_rule=(
                "La contestación redactada puede extenderse tanto como resulte necesario "
                "para explicar íntegramente el asunto, sin contar outputs."
            ),
        ),
    )
}


class ResponseModeManager:
    """Persistent response-policy engine for authored chat text, never for outputs."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "response_modes.sqlite3"
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _canonical(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    profile_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    built_in INTEGER NOT NULL CHECK (built_in IN (0,1)),
                    base_profile_id TEXT,
                    config_json TEXT NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
                    revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scope_bindings (
                    scope_type TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    profile_id TEXT NOT NULL REFERENCES profiles(profile_id),
                    revision INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (scope_type, scope_key)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                """
            )
            now = self._now()
            for profile in BUILTIN_PROFILES.values():
                connection.execute(
                    """
                    INSERT OR IGNORE INTO profiles
                    (profile_id,name,description,built_in,base_profile_id,config_json,
                     archived,revision,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,0,1,?,?)
                    """,
                    (
                        profile["profile_id"],
                        profile["name"],
                        profile["description"],
                        1,
                        None,
                        self._canonical(profile["config"]),
                        now,
                        now,
                    ),
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO scope_bindings
                (scope_type,scope_key,profile_id,revision,updated_at)
                VALUES ('GLOBAL','*','builtin.explicativo',1,?)
                """,
                (now,),
            )

    def _append_event(
        self, connection: sqlite3.Connection, action: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        previous = connection.execute(
            "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(previous[0]) if previous else "GENESIS"
        event = {
            "occurred_at": self._now(),
            "action": action,
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event_hash = hashlib.sha256(self._canonical(event).encode("utf-8")).hexdigest()
        connection.execute(
            """
            INSERT INTO audit_events
            (occurred_at,action,payload_json,previous_hash,event_hash)
            VALUES (?,?,?,?,?)
            """,
            (
                event["occurred_at"],
                action,
                self._canonical(payload),
                previous_hash,
                event_hash,
            ),
        )
        return {**event, "event_hash": event_hash}

    @staticmethod
    def _row_profile(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "profile_id": row["profile_id"],
            "name": row["name"],
            "description": row["description"],
            "built_in": bool(row["built_in"]),
            "base_profile_id": row["base_profile_id"],
            "config": json.loads(row["config_json"]),
            "archived": bool(row["archived"]),
            "revision": row["revision"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def profiles(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM profiles"
        parameters: tuple[Any, ...] = ()
        if not include_archived:
            query += " WHERE archived=0"
        query += " ORDER BY built_in DESC, name COLLATE NOCASE, profile_id"
        with self.connect() as connection:
            return [self._row_profile(row) for row in connection.execute(query, parameters)]

    @staticmethod
    def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = ResponseModeManager._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    @staticmethod
    def _validate_profile_id(profile_id: str) -> str:
        value = profile_id.strip().casefold()
        if not re.fullmatch(r"custom\.[a-z0-9][a-z0-9._-]{1,79}", value):
            raise ValueError("custom profile_id must match custom.[a-z0-9._-]{2,80}")
        return value

    @staticmethod
    def _validate_config(config: dict[str, Any]) -> None:
        if config.get("response_channel") != "CHAT_AUTHORED_TEXT":
            raise ValueError("response_channel must remain CHAT_AUTHORED_TEXT")
        viewport = config.get("viewport")
        if not isinstance(viewport, dict) or viewport.get("output_footprint_excluded") is not True:
            raise ValueError("outputs must remain excluded from the response viewport budget")
        trace = config.get("execution_trace")
        if not isinstance(trace, dict):
            raise ValueError("execution_trace configuration is required")
        required_trace = {
            "include_by_default": False,
            "followup_policy": "DO_NOT_OFFER",
            "record_policy": "AUTO_SAVE_MARKDOWN",
            "final_notice_policy": "ONE_LINE_PATH_ONLY",
        }
        if any(trace.get(key) != value for key, value in required_trace.items()):
            raise ValueError(
                "execution register policy is constitutional: save Markdown, never offer it, "
                "and mention only its path in one final line"
            )

    def upsert_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        profile_id = self._validate_profile_id(str(profile["profile_id"]))
        name = str(profile["name"]).strip()
        description = str(profile.get("description", "")).strip()
        if not name:
            raise ValueError("profile name is required")
        base_profile_id = str(profile.get("base_profile_id") or "builtin.explicativo")
        with self.connect() as connection:
            base_row = connection.execute(
                "SELECT * FROM profiles WHERE profile_id=? AND archived=0", (base_profile_id,)
            ).fetchone()
            if base_row is None:
                raise KeyError(f"unknown active base profile: {base_profile_id}")
            existing = connection.execute(
                "SELECT * FROM profiles WHERE profile_id=?", (profile_id,)
            ).fetchone()
            if existing is not None and bool(existing["built_in"]):
                raise ValueError("built-in profiles are immutable; create a custom profile")
            base_config = json.loads(base_row["config_json"])
            overrides = dict(profile.get("config", {}))
            materialized = self._deep_merge(base_config, overrides)
            self._validate_config(materialized)
            now = self._now()
            revision = int(existing["revision"]) + 1 if existing else 1
            created_at = str(existing["created_at"]) if existing else now
            connection.execute(
                """
                INSERT INTO profiles
                (profile_id,name,description,built_in,base_profile_id,config_json,
                 archived,revision,created_at,updated_at)
                VALUES (?,?,?,0,?,?,0,?,?,?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    base_profile_id=excluded.base_profile_id,
                    config_json=excluded.config_json,
                    archived=0,
                    revision=excluded.revision,
                    updated_at=excluded.updated_at
                """,
                (
                    profile_id,
                    name,
                    description,
                    base_profile_id,
                    self._canonical(materialized),
                    revision,
                    created_at,
                    now,
                ),
            )
            event = self._append_event(
                connection,
                "PROFILE_UPSERTED",
                {"profile_id": profile_id, "revision": revision, "profile": profile},
            )
            row = connection.execute(
                "SELECT * FROM profiles WHERE profile_id=?", (profile_id,)
            ).fetchone()
        return {
            "schema": "kch.response-mode-profile-receipt.v0.1.0",
            "profile": self._row_profile(row),
            "audit": event,
            "constitutional_invariants": CONSTITUTIONAL_RESPONSE_INVARIANTS,
        }

    def archive_profile(self, profile_id: str) -> dict[str, Any]:
        if profile_id.startswith("builtin."):
            raise ValueError("built-in profiles cannot be archived")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM profiles WHERE profile_id=? AND archived=0", (profile_id,)
            ).fetchone()
            if row is None:
                raise KeyError(profile_id)
            bindings = connection.execute(
                "SELECT scope_type,scope_key FROM scope_bindings WHERE profile_id=?", (profile_id,)
            ).fetchall()
            if bindings:
                raise ValueError("clear every active scope binding before archiving this profile")
            connection.execute(
                "UPDATE profiles SET archived=1,revision=revision+1,updated_at=? WHERE profile_id=?",
                (self._now(), profile_id),
            )
            event = self._append_event(
                connection, "PROFILE_ARCHIVED", {"profile_id": profile_id}
            )
        return {
            "schema": "kch.response-mode-profile-archive.v0.1.0",
            "profile_id": profile_id,
            "archived": True,
            "audit": event,
        }

    @staticmethod
    def _normalize_scope(scope_type: str, scope_key: str) -> tuple[str, str]:
        normalized_type = scope_type.strip().upper()
        if normalized_type not in SCOPE_ORDER:
            raise ValueError(f"scope_type must be one of {list(SCOPE_ORDER)}")
        normalized_key = "*" if normalized_type == "GLOBAL" else scope_key.strip()
        if not normalized_key:
            raise ValueError("scope_key is required outside GLOBAL")
        return normalized_type, normalized_key

    def set_scope(self, scope_type: str, scope_key: str, profile_id: str) -> dict[str, Any]:
        normalized_type, normalized_key = self._normalize_scope(scope_type, scope_key)
        with self.connect() as connection:
            profile = connection.execute(
                "SELECT profile_id FROM profiles WHERE profile_id=? AND archived=0", (profile_id,)
            ).fetchone()
            if profile is None:
                raise KeyError(f"unknown active profile: {profile_id}")
            current = connection.execute(
                "SELECT revision FROM scope_bindings WHERE scope_type=? AND scope_key=?",
                (normalized_type, normalized_key),
            ).fetchone()
            revision = int(current["revision"]) + 1 if current else 1
            now = self._now()
            connection.execute(
                """
                INSERT INTO scope_bindings
                (scope_type,scope_key,profile_id,revision,updated_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(scope_type,scope_key) DO UPDATE SET
                    profile_id=excluded.profile_id,
                    revision=excluded.revision,
                    updated_at=excluded.updated_at
                """,
                (normalized_type, normalized_key, profile_id, revision, now),
            )
            event = self._append_event(
                connection,
                "SCOPE_BOUND",
                {
                    "scope_type": normalized_type,
                    "scope_key": normalized_key,
                    "profile_id": profile_id,
                    "revision": revision,
                },
            )
        return {
            "schema": "kch.response-mode-scope-receipt.v0.1.0",
            "scope_type": normalized_type,
            "scope_key": normalized_key,
            "profile_id": profile_id,
            "revision": revision,
            "audit": event,
        }

    def clear_scope(self, scope_type: str, scope_key: str) -> dict[str, Any]:
        normalized_type, normalized_key = self._normalize_scope(scope_type, scope_key)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM scope_bindings WHERE scope_type=? AND scope_key=?",
                (normalized_type, normalized_key),
            ).fetchone()
            if row is None:
                raise KeyError(f"scope binding not found: {normalized_type}/{normalized_key}")
            connection.execute(
                "DELETE FROM scope_bindings WHERE scope_type=? AND scope_key=?",
                (normalized_type, normalized_key),
            )
            event = self._append_event(
                connection,
                "SCOPE_CLEARED",
                {
                    "scope_type": normalized_type,
                    "scope_key": normalized_key,
                    "previous_profile_id": row["profile_id"],
                },
            )
        return {
            "schema": "kch.response-mode-scope-clear.v0.1.0",
            "scope_type": normalized_type,
            "scope_key": normalized_key,
            "cleared": True,
            "audit": event,
        }

    def resolve(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = dict(context or {})
        candidates: list[tuple[str, str]] = [("GLOBAL", "*")]
        for scope_type in SCOPE_ORDER[1:]:
            key = context.get(SCOPE_CONTEXT_KEYS[scope_type])
            if key is not None and str(key).strip():
                candidates.append((scope_type, str(key).strip()))
        with self.connect() as connection:
            selected: sqlite3.Row | None = None
            for scope_type, scope_key in reversed(candidates):
                row = connection.execute(
                    """
                    SELECT p.*,
                           b.scope_type AS selected_scope_type,
                           b.scope_key AS selected_scope_key,
                           b.revision AS binding_revision
                    FROM scope_bindings b
                    JOIN profiles p ON p.profile_id=b.profile_id
                    WHERE b.scope_type=? AND b.scope_key=? AND p.archived=0
                    """,
                    (scope_type, scope_key),
                ).fetchone()
                if row is not None:
                    selected = row
                    break
            if selected is None:
                selected = connection.execute(
                    "SELECT * FROM profiles WHERE profile_id='builtin.explicativo'"
                ).fetchone()
                selected_scope = {"scope_type": "FALLBACK", "scope_key": "*", "revision": 0}
            else:
                selected_scope = {
                    "scope_type": selected["selected_scope_type"],
                    "scope_key": selected["selected_scope_key"],
                    "revision": selected["binding_revision"],
                }
        profile = self._row_profile(selected)
        return {
            "schema": "kch.response-mode-resolution.v0.1.0",
            "context": context,
            "selected_scope": selected_scope,
            "profile": profile,
            "constitutional_invariants": CONSTITUTIONAL_RESPONSE_INVARIANTS,
            "viewport_guarantee": {
                "state": "HOST_RENDERER_MEASUREMENT_REQUIRED",
                "guaranteed_without_host_metrics": False,
            },
        }

    def compile_contract(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        resolution = self.resolve(context)
        profile = resolution["profile"]
        config = profile["config"]
        trace = config["execution_trace"]
        instruction = (
            f"MODO DE CONTESTACIÓN ACTIVO: {profile['name']} ({profile['profile_id']}). "
            f"{config['length_rule']} Esta regla alcanza únicamente la contestación redactada "
            "en el chat: no limita, recorta ni contabiliza outputs, código, archivos, tablas de "
            "resultados o artefactos. La contestación siempre debe ser informativa, explicativa "
            "y de conjunto; no debe convertirse en un log archivístico de acciones. "
            "La ficha técnica de ejecución se guarda aparte en Markdown: no se ofrece ni se "
            "incorpora a la explicación; sólo se informa su ruta en una última línea."
        )
        return {
            "schema": "kch.response-mode-host-contract.v0.1.0",
            "resolution": resolution,
            "host_instruction": instruction,
            "execution_trace_followup": {
                "policy": trace["followup_policy"],
                "include_by_default": bool(trace.get("include_by_default", False)),
                "record_policy": trace["record_policy"],
                "final_notice_policy": trace["final_notice_policy"],
            },
            "outputs_affected": False,
            "automatic_application": {
                "kch_policy_default": True,
                "host_adapter_must_resolve_before_each_response": True,
                "direct_model_control_claimed": False,
            },
        }

    @staticmethod
    def _redact(value: Any, key: str = "") -> Any:
        sensitive = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key)")
        if sensitive.search(key):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {str(k): ResponseModeManager._redact(v, str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [ResponseModeManager._redact(item) for item in value]
        return value

    @staticmethod
    def _markdown_value(value: Any) -> str:
        if isinstance(value, str):
            return value
        return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"

    def record_execution(self, record: dict[str, Any]) -> dict[str, Any]:
        clean = self._redact(dict(record))
        occurred_at = self._now()
        identity = hashlib.sha256(
            (occurred_at + self._canonical(clean)).encode("utf-8")
        ).hexdigest()
        record_id = f"response-{occurred_at[:10]}-{identity[:16]}"
        directory = self.root / "registers" / occurred_at[:10]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{record_id}.md"
        title = str(clean.pop("title", "Ficha técnica de ejecución KCH"))
        lines = [f"# {title}", "", f"- ID: `{record_id}`", f"- Fecha UTC: `{occurred_at}`", ""]
        preferred = (
            ("substantive_result", "Resultado sustantivo"),
            ("meaning", "Qué significa"),
            ("changes", "Cambios realizados"),
            ("evidence", "Evidencia y verificaciones"),
            ("claim_limits", "Límites de claims"),
            ("artifacts", "Artefactos"),
            ("next_action", "Próxima acción crítica"),
        )
        consumed: set[str] = set()
        for key, heading in preferred:
            if key not in clean:
                continue
            consumed.add(key)
            lines.extend([f"## {heading}", "", self._markdown_value(clean[key]), ""])
        remainder = {key: value for key, value in clean.items() if key not in consumed}
        if remainder:
            lines.extend(["## Registro estructurado adicional", "", self._markdown_value(remainder), ""])
        raw = ("\n".join(lines).rstrip() + "\n").encode("utf-8")
        temporary = path.with_suffix(".md.tmp")
        temporary.write_bytes(raw)
        temporary.replace(path)
        digest = hashlib.sha256(raw).hexdigest()
        with self.connect() as connection:
            event = self._append_event(
                connection,
                "EXECUTION_REGISTER_SAVED",
                {"record_id": record_id, "path": str(path), "bytes": len(raw), "sha256": digest},
            )
        return {
            "schema": "kch.response-execution-register.v0.1.0",
            "record_id": record_id,
            "path": str(path),
            "bytes": len(raw),
            "sha256": digest,
            "saved": True,
            "offered_to_user": False,
            "final_notice": f"Ficha técnica guardada en `{path}`.",
            "audit": event,
        }

    def verify(self) -> dict[str, Any]:
        errors: list[str] = []
        with self.connect() as connection:
            for profile_id, expected in BUILTIN_PROFILES.items():
                row = connection.execute(
                    "SELECT * FROM profiles WHERE profile_id=?", (profile_id,)
                ).fetchone()
                if row is None:
                    errors.append(f"missing built-in profile: {profile_id}")
                    continue
                if json.loads(row["config_json"]) != expected["config"]:
                    errors.append(f"built-in profile drift: {profile_id}")
            previous_hash = "GENESIS"
            for row in connection.execute("SELECT * FROM audit_events ORDER BY sequence"):
                event = {
                    "occurred_at": row["occurred_at"],
                    "action": row["action"],
                    "payload": json.loads(row["payload_json"]),
                    "previous_hash": row["previous_hash"],
                }
                expected_hash = hashlib.sha256(
                    self._canonical(event).encode("utf-8")
                ).hexdigest()
                if row["previous_hash"] != previous_hash or row["event_hash"] != expected_hash:
                    errors.append(f"audit chain mismatch at sequence {row['sequence']}")
                previous_hash = row["event_hash"]
            foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_errors:
                errors.append(f"foreign key failures: {len(foreign_key_errors)}")
            counts = {
                "profiles": connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0],
                "active_profiles": connection.execute(
                    "SELECT COUNT(*) FROM profiles WHERE archived=0"
                ).fetchone()[0],
                "bindings": connection.execute(
                    "SELECT COUNT(*) FROM scope_bindings"
                ).fetchone()[0],
                "audit_events": connection.execute(
                    "SELECT COUNT(*) FROM audit_events"
                ).fetchone()[0],
            }
        return {
            "schema": "kch.response-mode-integrity.v0.1.0",
            "gate": "PASS" if not errors else "FAIL",
            "counts": counts,
            "errors": errors,
        }

    def status(self) -> dict[str, Any]:
        resolution = self.resolve({})
        return {
            "schema": "kch.response-mode-status.v0.1.0",
            "presets": [
                {
                    "profile_id": profile["profile_id"],
                    "name": profile["name"],
                    "viewport": profile["config"]["viewport"],
                }
                for profile in self.profiles()
                if profile["built_in"]
            ],
            "default_profile": resolution["profile"]["profile_id"],
            "scope_precedence": list(SCOPE_ORDER),
            "normalized_transcription": {
                "raw_variant": "modo ampliado",
                "canonical_term": "modo explicativo",
                "basis": "latest explicit enumeration: conciso, explicativo y extenso",
            },
            "constitutional_invariants": CONSTITUTIONAL_RESPONSE_INVARIANTS,
            "integrity": self.verify(),
            "industrial_validation_established": False,
        }
