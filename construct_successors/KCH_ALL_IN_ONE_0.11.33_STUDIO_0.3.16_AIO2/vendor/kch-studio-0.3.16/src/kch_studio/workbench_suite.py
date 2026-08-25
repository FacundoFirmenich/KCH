from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    canonical_json,
    safe_child,
    sha256_bytes,
    sha256_json,
    sqlite_connection,
)
from .recovery import RecoveryVault

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL,
    source_uri TEXT,
    title TEXT NOT NULL,
    workspace_id TEXT,
    session_id TEXT,
    captured_at TEXT NOT NULL,
    original_sha256 TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    storage_state TEXT NOT NULL,
    raw_characters INTEGER,
    normalized_path TEXT,
    normalized_sha256 TEXT,
    normalization_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS secret_references (
    secret_ref_id TEXT PRIMARY KEY,
    source_id TEXT,
    secret_kind TEXT NOT NULL,
    value_sha256 TEXT NOT NULL,
    masked_hint TEXT NOT NULL,
    external_locator TEXT,
    created_at TEXT NOT NULL,
    storage_state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
    lesson_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    lesson_kind TEXT NOT NULL,
    domain TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    statement TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    confidence_state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    lesson_hash TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS protocols (
    protocol_id TEXT PRIMARY KEY,
    scope_key TEXT NOT NULL,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    pre_generation_hash TEXT NOT NULL,
    path TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(scope_key,version),
    UNIQUE(scope_key,pre_generation_hash)
);
CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    protocol_id TEXT NOT NULL REFERENCES protocols(protocol_id),
    skill_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    path TEXT NOT NULL,
    pre_generation_hash TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    installed INTEGER NOT NULL,
    activated INTEGER NOT NULL,
    UNIQUE(skill_name,version),
    UNIQUE(skill_name,pre_generation_hash)
);
CREATE TABLE IF NOT EXISTS archive_groups (
    group_id TEXT PRIMARY KEY,
    parent_group_id TEXT REFERENCES archive_groups(group_id),
    title TEXT NOT NULL,
    group_kind TEXT NOT NULL,
    rank INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    archived INTEGER NOT NULL,
    UNIQUE(parent_group_id,rank)
);
CREATE TABLE IF NOT EXISTS archive_members (
    group_id TEXT NOT NULL REFERENCES archive_groups(group_id),
    item_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    rank INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(group_id,item_type,item_id)
);
CREATE TABLE IF NOT EXISTS graph_edges (
    edge_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    dimensions_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS budget_accounts (
    account_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    unit TEXT NOT NULL,
    weekly_limit TEXT,
    currency TEXT,
    week_anchor TEXT NOT NULL,
    telemetry_source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    enabled INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS budget_samples (
    sample_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES budget_accounts(account_id),
    observed_at TEXT NOT NULL,
    used_value TEXT,
    available_percent TEXT,
    source_receipt_json TEXT NOT NULL,
    source_receipt_hash TEXT NOT NULL,
    adjudication_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS handoffs (
    handoff_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    trigger TEXT NOT NULL,
    budget_state_json TEXT NOT NULL,
    path TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
"""


DOMAINS: dict[str, tuple[str, ...]] = {
    "THEORETICAL": ("teoría", "teórico", "theory", "formalism"),
    "FORMAL": ("formal", "axioma", "invariante", "proof", "demostración"),
    "MATHEMATICAL": ("matem", "ecuación", "bayes", "probabilidad", "pérdida", "loss"),
    "COMPUTING": ("código", "python", "software", "api", "mcp", "script", "sqlite", "hash"),
    "STATISTICAL": ("estadíst", "muestra", "posterior", "prior", "intervalo", "estim"),
    "DEPLOYMENT": ("deploy", "instala", "vps", "docker", "host", "cline", "vscode", "ruta"),
    "EXPERIMENTAL": ("experimento", "campaña", "holdout", "benchmark", "prueba", "test"),
    "METHODOLOGICAL": ("método", "metodol", "procedimiento", "workflow", "proceso"),
    "EPISTEMOLOGICAL": ("claim", "evidencia", "autoridad", "epistem", "no demuestra", "límite"),
    "PROTOCOL": ("protocolo", "paso", "primero", "después", "antes de", "rutina"),
    "REFINEMENT_GENERAL": ("refinement", "mejora", "pulimento", "optimiza", "general"),
    "PARTICULAR": ("caso", "workspace", "sesión", "específico", "particular"),
}

KINDS: dict[str, tuple[str, ...]] = {
    "FAILURE": ("fallo", "error", "fracas", "no funcion", "crash", "failed"),
    "CORRECTION": ("corrección", "correg", "rectific", "en vez de", "perdón"),
    "PROCEDURE_STEP": ("paso ", "primero", "segundo", "tercero", "después", "luego", "antes de"),
    "DECISION": ("decisión", "queda fijado", "vinculante", "se hará", "debe ", "tiene que"),
    "INVARIANT": ("invariante", "bajo ningún concepto", "sin excepción", "nunca ", "siempre "),
    "CASE": ("caso", "campaña", "sesión", "workspace", "ejemplo"),
    "CLAIM_LIMIT": ("no demuestra", "no probado", "not_estimable", "límite", "claim ceiling"),
    "IMPROVEMENT": ("mejora", "pulimento", "optimiza", "superador", "refinement"),
}

SECRET_PATTERNS = (
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{16,}\b")),
    (
        "GENERIC_SECRET_ASSIGNMENT",
        re.compile(
            r"(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*"
            r"(?!\[SECRET_REF:)([^\s,;]{8,})"
        ),
    ),
    (
        "PRIVATE_KEY",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ),
)

DEFAULT_POLICY = {
    "schema": "kch.workbench-budget-policy.v0.1.0",
    "design_status": "USER_CUSTOMIZABLE_DEFAULT_NOT_EMPIRICALLY_CALIBRATED",
    "refresh_at_remaining_percent": 50.0,
    "checkpoint_at_remaining_percent": 25.0,
    "handoff_at_remaining_percent": 15.0,
    "critical_at_remaining_percent": 5.0,
    "interval_minutes": {
        "NORMAL": 120,
        "REFRESH": 60,
        "CHECKPOINT": 30,
        "HANDOFF": 10,
        "CRITICAL": 2,
    },
    "min_protocol_evidence": 3,
    "min_procedure_steps": 2,
    "require_failure_or_correction": True,
    "automatic_stage_skills": True,
    "automatic_external_task_creation": False,
    "automatic_external_task_archival": False,
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized[:64] or "work-protocol"


def decimal_text(value: Any) -> str:
    number = float(value)
    if number < 0:
        raise ValueError("budget values cannot be negative")
    return format(number, ".12g")


class WorkbenchSuite:
    """User-facing work archive, evidence-derived learning and staged skill factory."""

    SOURCE_KINDS = {
        "CHAT",
        "SESSION",
        "WORKSPACE",
        "FILE",
        "TOOL_EVENT",
        "EXPERIMENT",
        "DICTATION",
        "AUDIO_TRANSCRIPT",
        "OTHER",
    }
    DICTION_NORMALIZATION_KINDS = {"DICTATION", "AUDIO_TRANSCRIPT"}
    BUDGET_UNITS = {"TOKENS", "CURRENCY", "PERCENT"}

    def __init__(
        self,
        root: str | Path,
        *,
        normalizer: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.raw = self.root / "raw"
        self.normalized = self.root / "normalized"
        self.protocol_root = self.root / "protocols"
        self.skill_root = self.root / "skills" / "candidates"
        self.handoff_root = self.root / "handoffs"
        for path in (
            self.raw,
            self.normalized,
            self.protocol_root,
            self.skill_root,
            self.handoff_root,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "workbench.sqlite3"
        self.vault = RecoveryVault(self.root / "recovery")
        self.normalizer = normalizer
        with self.connect() as connection:
            connection.executescript(DDL)
            columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(sources)").fetchall()
            }
            if "normalized_path" not in columns:
                connection.execute("ALTER TABLE sources ADD COLUMN normalized_path TEXT")
            connection.commit()
        if self._setting("budget_policy") is None:
            self._set_setting("budget_policy", DEFAULT_POLICY)
        if self._setting("last_maintenance_at") is None:
            self._set_setting("last_maintenance_at", None)
        self._ensure_root_group()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _setting(self, key: str) -> Any:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT value_json FROM settings WHERE key=?", (key,)
            ).fetchone()
        return None if row is None else json.loads(str(row[0]))

    def _set_setting(self, key: str, value: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO settings VALUES(?,?,?)",
                (key, canonical_json(value), utc_now()),
            )
            connection.commit()

    def _event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = utc_now()
        event_id = f"WBEVT-{uuid.uuid4()}"
        with self.connect() as connection:
            previous_row = connection.execute(
                "SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            previous = "0" * 64 if previous_row is None else str(previous_row[0])
            body = {
                "event_id": event_id,
                "timestamp": timestamp,
                "event_type": event_type,
                "payload": payload,
            }
            digest = sha256_json({**body, "previous_hash": previous})
            connection.execute(
                "INSERT INTO events(event_id,timestamp,event_type,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?)",
                (event_id, timestamp, event_type, canonical_json(payload), previous, digest),
            )
            connection.commit()
        return {**body, "previous_hash": previous, "event_hash": digest}

    def _ensure_root_group(self) -> None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT group_id FROM archive_groups WHERE group_id='GROUP-ROOT'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO archive_groups VALUES(?,?,?,?,?,?,?)",
                    ("GROUP-ROOT", None, "Todo el trabajo KCH", "ROOT", 1, utc_now(), 0),
                )
                connection.commit()

    @staticmethod
    def _secret_redaction(text: str) -> tuple[str, list[dict[str, Any]]]:
        redacted = text
        observed: list[dict[str, Any]] = []
        for kind, pattern in SECRET_PATTERNS:
            while True:
                match = pattern.search(redacted)
                if match is None:
                    break
                value = match.group(1) if match.lastindex else match.group(0)
                reference = f"SECRET-{uuid.uuid4()}"
                observed.append(
                    {
                        "secret_ref_id": reference,
                        "secret_kind": kind,
                        "value_sha256": sha256_bytes(value.encode("utf-8")),
                        "masked_hint": f"REDACTED:{kind}:LENGTH={len(value)}",
                    }
                )
                start, end = match.span(1) if match.lastindex else match.span(0)
                redacted = redacted[:start] + f"[SECRET_REF:{reference}]" + redacted[end:]
        return redacted, observed

    def _normalize(self, text: str, *, source_kind: str) -> tuple[str, dict[str, Any]]:
        if source_kind not in self.DICTION_NORMALIZATION_KINDS:
            return text, {
                "state": "BYPASSED_NON_TRANSCRIPTION_SOURCE",
                "raw_preserved": True,
                "normalized_changed": False,
                "eligible_source_kinds": sorted(self.DICTION_NORMALIZATION_KINDS),
            }
        if self.normalizer is None:
            return text, {
                "state": "TRANSCRIPTION_RAW_ONLY_NO_NORMALIZER",
                "raw_preserved": True,
                "normalized_changed": False,
            }
        resolution = self.normalizer(text)
        normalized = str(resolution.get("normalized_transcription", text))
        return normalized, {
            "state": "CONTEXTUAL_RESOLVER_APPLIED",
            "raw_preserved": True,
            "normalized_changed": normalized != text,
            "resolution_id": resolution.get("resolution_id"),
            "resolver_hash": resolution.get("resolver_hash"),
            "competing_candidates": resolution.get("competing_candidates", []),
        }

    @staticmethod
    def _domains(line: str) -> list[str]:
        lowered = line.casefold()
        matched = [
            domain for domain, terms in DOMAINS.items() if any(term in lowered for term in terms)
        ]
        return matched or ["PARTICULAR"]

    @staticmethod
    def _kinds(line: str) -> list[str]:
        lowered = line.casefold()
        return [kind for kind, terms in KINDS.items() if any(term in lowered for term in terms)]

    def ingest(
        self,
        *,
        source_kind: str,
        title: str,
        raw_text: str | None = None,
        source_path: str | Path | None = None,
        source_uri: str | None = None,
        workspace_id: str | None = None,
        session_id: str | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source_kind = source_kind.upper()
        if source_kind not in self.SOURCE_KINDS:
            raise ValueError(f"source_kind must be one of {sorted(self.SOURCE_KINDS)}")
        if (raw_text is None) == (source_path is None):
            raise ValueError("provide exactly one of raw_text or source_path")
        if source_path is not None:
            path = Path(source_path).resolve()
            raw_bytes = path.read_bytes()
            decoded = raw_bytes.decode("utf-8", errors="replace")
            source_uri = source_uri or path.as_uri()
        else:
            decoded = str(raw_text)
            raw_bytes = decoded.encode("utf-8")
        source_id = f"SOURCE-{uuid.uuid4()}"
        original_sha = sha256_bytes(raw_bytes)
        redacted, secrets = self._secret_redaction(decoded)
        normalized, normalization = self._normalize(redacted, source_kind=source_kind)
        normalized_path = self.normalized / f"{source_id}.normalized.txt"
        normalized_path.write_bytes(normalized.encode("utf-8"))
        if secrets:
            stored = self.raw / f"{source_id}.redacted.txt"
            stored.write_text(redacted, encoding="utf-8")
            storage_state = "REDACTED_TEXT_ONLY_ORIGINAL_SECRET_BYTES_NOT_STORED"
        else:
            suffix = ".txt" if source_path is None else Path(str(source_path)).suffix or ".bin"
            stored = self.raw / f"{source_id}{suffix}"
            stored.write_bytes(raw_bytes)
            storage_state = "EXACT_ORIGINAL_BYTES_STORED"
        scope_key = workspace_id or session_id or "GLOBAL"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sources(
                    source_id,source_kind,source_uri,title,workspace_id,session_id,captured_at,
                    original_sha256,stored_path,storage_state,raw_characters,normalized_path,
                    normalized_sha256,normalization_json,provenance_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    source_id,
                    source_kind,
                    source_uri,
                    title,
                    workspace_id,
                    session_id,
                    utc_now(),
                    original_sha,
                    str(stored),
                    storage_state,
                    len(decoded),
                    str(normalized_path),
                    sha256_bytes(normalized.encode("utf-8")),
                    canonical_json(normalization),
                    canonical_json(provenance or {}),
                ),
            )
            for secret in secrets:
                connection.execute(
                    "INSERT INTO secret_references VALUES(?,?,?,?,?,?,?,?)",
                    (
                        secret["secret_ref_id"],
                        source_id,
                        secret["secret_kind"],
                        secret["value_sha256"],
                        secret["masked_hint"],
                        None,
                        utc_now(),
                        "REFERENCE_HASH_ONLY_NO_SECRET_VALUE_STORED",
                    ),
                )
            connection.commit()
        lessons = self._detect_lessons(source_id, normalized, scope_key)
        custody = self.vault.save_json(
            f"sources/{source_id}.json",
            {
                "source_id": source_id,
                "original_sha256": original_sha,
                "stored_path": str(stored),
                "normalized_path": str(normalized_path),
                "storage_state": storage_state,
                "normalization": normalization,
                "secret_references": secrets,
            },
            kind="WORKBENCH_SOURCE_RECEIPT",
            actor="USER",
            operation="INGEST_AND_DETECT",
        )
        event = self._event(
            "SOURCE_INGESTED",
            {"source_id": source_id, "scope_key": scope_key, "lesson_count": len(lessons)},
        )
        maintenance = self.run_maintenance(
            trigger="AUTOMATIC_AFTER_SOURCE_INGEST", force=True, scope_key=scope_key
        )
        return {
            "schema": "kch.workbench-source-ingest.v0.1.0",
            "source_id": source_id,
            "source_kind": source_kind,
            "scope_key": scope_key,
            "original_sha256": original_sha,
            "stored_path": str(stored),
            "normalized_path": str(normalized_path),
            "storage_state": storage_state,
            "raw_preserved": not secrets,
            "normalization": normalization,
            "secret_references": [
                {key: value for key, value in item.items() if key != "value_sha256"}
                for item in secrets
            ],
            "detected_lessons": lessons,
            "automatic_maintenance": maintenance,
            "custody": custody,
            "event": event,
        }

    def _detect_lessons(self, source_id: str, text: str, scope_key: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        lines = [line.strip(" \t-*•") for line in text.splitlines() if len(line.strip()) >= 10]
        for ordinal, statement in enumerate(lines, start=1):
            kinds = self._kinds(statement)
            if not kinds:
                continue
            domains = self._domains(statement)
            for kind in kinds:
                for domain in domains:
                    lesson_id = f"LESSON-{uuid.uuid4()}"
                    evidence = {
                        "source_id": source_id,
                        "line_ordinal": ordinal,
                        "detector": "DETERMINISTIC_LEXICAL_V0.1.0",
                        "matched_kind": kind,
                        "matched_domain": domain,
                    }
                    body = {
                        "lesson_id": lesson_id,
                        "source_id": source_id,
                        "lesson_kind": kind,
                        "domain": domain,
                        "scope_key": scope_key,
                        "statement": statement,
                        "evidence": evidence,
                        "confidence_state": "DETECTED_CANDIDATE_REQUIRES_EVIDENCE_REVIEW",
                    }
                    digest = sha256_json(body)
                    with self.connect() as connection:
                        connection.execute(
                            "INSERT INTO lessons VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                lesson_id,
                                source_id,
                                kind,
                                domain,
                                scope_key,
                                statement,
                                canonical_json(evidence),
                                body["confidence_state"],
                                utc_now(),
                                digest,
                                "ACTIVE_CANDIDATE",
                            ),
                        )
                        connection.commit()
                    results.append({**body, "lesson_hash": digest})
        return results

    def lessons(
        self, *, scope_key: str | None = None, domain: str | None = None
    ) -> list[dict[str, Any]]:
        clauses = ["status='ACTIVE_CANDIDATE'"]
        values: list[Any] = []
        if scope_key:
            clauses.append("scope_key=?")
            values.append(scope_key)
        if domain:
            clauses.append("domain=?")
            values.append(domain.upper())
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM lessons WHERE {' AND '.join(clauses)} ORDER BY created_at,lesson_id",
                values,
            ).fetchall()
        return [{**dict(row), "evidence": json.loads(str(row["evidence_json"]))} for row in rows]

    def _protocol_for_scope(self, scope_key: str) -> dict[str, Any]:
        evidence = self.lessons(scope_key=scope_key)
        policy = self._setting("budget_policy")
        steps = [item for item in evidence if item["lesson_kind"] == "PROCEDURE_STEP"]
        failures = [item for item in evidence if item["lesson_kind"] in {"FAILURE", "CORRECTION"}]
        blockers = []
        if len(evidence) < int(policy["min_protocol_evidence"]):
            blockers.append("INSUFFICIENT_TOTAL_EVIDENCE")
        if len(steps) < int(policy["min_procedure_steps"]):
            blockers.append("INSUFFICIENT_PROCEDURE_STEPS")
        if policy["require_failure_or_correction"] and not failures:
            blockers.append("NO_FAILURE_OR_CORRECTION_EVIDENCE")
        if blockers:
            return {
                "state": "NOT_ESTIMABLE_INSUFFICIENT_EVIDENCE",
                "scope_key": scope_key,
                "blockers": blockers,
                "evidence_count": len(evidence),
                "protocol_generated": False,
            }
        evidence_ids = [item["lesson_id"] for item in evidence]
        pre_hash = sha256_json(
            [
                {"lesson_id": item["lesson_id"], "lesson_hash": item["lesson_hash"]}
                for item in evidence
            ]
        )
        with closing(self.connect()) as connection:
            existing = connection.execute(
                "SELECT * FROM protocols WHERE scope_key=? AND pre_generation_hash=?",
                (scope_key, pre_hash),
            ).fetchone()
            version = int(
                connection.execute(
                    "SELECT COALESCE(MAX(version),0)+1 FROM protocols WHERE scope_key=?",
                    (scope_key,),
                ).fetchone()[0]
            )
        if existing is not None:
            return {**dict(existing), "state": "UNCHANGED_EXACT_EVIDENCE_ALREADY_GENERATED"}
        protocol_id = f"PROTOCOL-{uuid.uuid4()}"
        title = f"Protocolo operativo — {scope_key}"
        created = utc_now()
        domains = sorted({item["domain"] for item in evidence})
        decisions = [item for item in evidence if item["lesson_kind"] in {"DECISION", "INVARIANT"}]
        limits = [item for item in evidence if item["lesson_kind"] == "CLAIM_LIMIT"]
        cases = [item for item in evidence if item["lesson_kind"] == "CASE"]
        secret_refs = self._secret_refs_for_lessons(evidence)

        def section(name: str, items: list[dict[str, Any]]) -> list[str]:
            lines = [f"## {name}", ""]
            lines.extend(
                f"- {item['statement']}  `[{item['lesson_id']} · {item['source_id']}]`"
                for item in items
            )
            if not items:
                lines.append("- `NOT_ESTIMABLE`: no existe evidencia admitida en esta versión.")
            return [*lines, ""]

        markdown = [
            f"# {title}",
            "",
            f"- Fecha UTC: `{created}`",
            f"- Versión: `{version}`",
            f"- Ámbito: `{scope_key}`",
            f"- Pre-hash de evidencia: `{pre_hash}`",
            f"- Dominios: `{', '.join(domains)}`",
            "- Estado: `GENERATED_FROM_DETECTED_EVIDENCE_REVIEW_REQUIRED`",
            "",
            "Este protocolo sólo recompone evidencia detectada y enlazada. No convierte detección lexical en verdad ni reemplaza revisión humana.",
            "",
            *section("Pasos observados", steps),
            *section("Fallos y correcciones que no deben repetirse", failures),
            *section("Decisiones e invariantes", decisions),
            *section("Casos y particularidades", cases),
            *section("Límites epistemológicos y de claims", limits),
            "## Secretos y credenciales",
            "",
            "Los valores secretos nunca se incorporan al protocolo. Sólo se admiten referencias externas y hashes no reversibles.",
            "",
            *(
                [
                    f"- `{item['secret_ref_id']}` · {item['secret_kind']} · {item['storage_state']}"
                    for item in secret_refs
                ]
                or ["- Ninguna referencia secreta detectada."]
            ),
            "",
            "## Trazabilidad",
            "",
            *[
                f"- `{item['lesson_id']}` ← `{item['source_id']}` · `{item['lesson_hash']}`"
                for item in evidence
            ],
            "",
        ]
        path = self.protocol_root / f"{slug(scope_key)}-v{version:03d}-{protocol_id}.md"
        path.write_text("\n".join(markdown), encoding="utf-8")
        manifest_hash = sha256_bytes(path.read_bytes())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO protocols VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    protocol_id,
                    scope_key,
                    version,
                    title,
                    created,
                    canonical_json(evidence_ids),
                    pre_hash,
                    str(path),
                    manifest_hash,
                    "GENERATED_REVIEW_REQUIRED",
                ),
            )
            connection.commit()
        self._event(
            "PROTOCOL_GENERATED",
            {"protocol_id": protocol_id, "scope_key": scope_key, "pre_hash": pre_hash},
        )
        return {
            "protocol_id": protocol_id,
            "scope_key": scope_key,
            "version": version,
            "title": title,
            "created_at": created,
            "evidence_ids": evidence_ids,
            "pre_generation_hash": pre_hash,
            "path": str(path),
            "manifest_hash": manifest_hash,
            "state": "GENERATED_REVIEW_REQUIRED",
        }

    def _secret_refs_for_lessons(self, lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
        source_ids = sorted({item["source_id"] for item in lessons})
        if not source_ids:
            return []
        placeholders = ",".join("?" for _ in source_ids)
        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"SELECT secret_ref_id,secret_kind,masked_hint,external_locator,storage_state FROM secret_references WHERE source_id IN ({placeholders}) ORDER BY created_at",
                source_ids,
            ).fetchall()
        return [dict(row) for row in rows]

    def _skill_for_protocol(self, protocol: dict[str, Any]) -> dict[str, Any]:
        if protocol.get("protocol_id") is None:
            return {"state": "NOT_GENERATED_WITHOUT_PROTOCOL", "protocol": protocol}
        protocol_id = str(protocol["protocol_id"])
        scope_key = str(protocol["scope_key"])
        skill_name = f"kch-{slug(scope_key)}-operating-protocol"
        pre_hash = str(protocol["pre_generation_hash"])
        with closing(self.connect()) as connection:
            existing = connection.execute(
                "SELECT * FROM skills WHERE skill_name=? AND pre_generation_hash=?",
                (skill_name, pre_hash),
            ).fetchone()
            version = int(
                connection.execute(
                    "SELECT COALESCE(MAX(version),0)+1 FROM skills WHERE skill_name=?",
                    (skill_name,),
                ).fetchone()[0]
            )
        if existing is not None:
            return {**dict(existing), "state": "UNCHANGED_EXACT_EVIDENCE_ALREADY_GENERATED"}
        skill_id = f"SKILL-{uuid.uuid4()}"
        root = self.skill_root / f"{skill_name}-v{version:03d}"
        references = root / "references"
        evals = root / "evals"
        references.mkdir(parents=True)
        evals.mkdir()
        protocol_text = Path(protocol["path"]).read_text(encoding="utf-8")
        description = (
            f"Apply the evidence-derived {scope_key} operating protocol. Use whenever work in this scope "
            "needs its dated steps, known failures, decisions, claim limits, provenance, or handoff discipline."
        )
        skill_markdown = f"""---
name: {skill_name}
description: {description}
compatibility: KCH staged candidate; no automatic host installation
---

# {protocol["title"]}

Read `references/PROTOCOL.md` completely before acting. Read `references/PROVENANCE.json` when a claim, failure, correction, secret reference, or historic case affects the task.

## Operating sequence

1. Identify the active workspace, session and governing objective.
2. Match the case against the dated protocol; do not infer missing steps.
3. Apply the admitted steps in order and check the recorded failure modes before each consequential action.
4. Preserve raw evidence, pre-hashes, post-hashes, adverse results and claim ceilings.
5. Refer to secrets only through `SECRET_REF` handles. Never copy a secret value into outputs, logs or skill files.
6. Return what changed, evidence boundary, unresolved points and next decision-critical action.

## Abstention rule

If the protocol reports `NOT_ESTIMABLE`, conflicting evidence or missing authority, preserve that state and request only the minimum missing input. Do not fill gaps with plausible values.

## Lifecycle

This skill is `STAGED_UNEVALUATED`. Generation does not install, activate, benchmark or promote it. Promotion requires separate evaluation and user authority.
"""
        (root / "SKILL.md").write_text(skill_markdown, encoding="utf-8")
        (references / "PROTOCOL.md").write_text(protocol_text, encoding="utf-8")
        provenance = {
            "schema": "kch.generated-skill-provenance.v0.1.0",
            "skill_id": skill_id,
            "protocol_id": protocol_id,
            "scope_key": scope_key,
            "pre_generation_hash": pre_hash,
            "generated_at": utc_now(),
            "secret_values_included": False,
            "installation_authorized": False,
            "activation_authorized": False,
        }
        (references / "PROVENANCE.json").write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        eval_set = {
            "skill_name": skill_name,
            "evals": [
                {
                    "id": 1,
                    "prompt": f"Aplica el protocolo de {scope_key} a un caso nuevo conservando trazabilidad.",
                    "expected_output": "Pasos aplicados con referencias, límites y próxima acción.",
                    "files": [],
                    "expectations": [
                        "Uses the dated protocol",
                        "Preserves evidence and claim boundaries",
                    ],
                },
                {
                    "id": 2,
                    "prompt": f"Revisa una ejecución de {scope_key} que podría repetir un fallo histórico.",
                    "expected_output": "Identifica el fallo registrado y propone prevención verificable.",
                    "files": [],
                    "expectations": ["Names an evidenced failure", "Does not invent a new failure"],
                },
                {
                    "id": 3,
                    "prompt": f"Falta evidencia para completar un paso de {scope_key}; decide cómo continuar.",
                    "expected_output": "Abstiene o solicita la mínima evidencia sin rellenar huecos.",
                    "files": [],
                    "expectations": [
                        "Returns NOT_ESTIMABLE or a bounded request",
                        "Does not fabricate values",
                    ],
                },
            ],
        }
        (evals / "evals.json").write_text(
            json.dumps(eval_set, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        files = [path for path in root.rglob("*") if path.is_file()]
        manifest = [
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_bytes(path.read_bytes()),
            }
            for path in sorted(files)
        ]
        manifest_hash = sha256_json(manifest)
        (root / "MANIFEST.json").write_text(
            json.dumps({"files": manifest, "manifest_hash": manifest_hash}, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO skills VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    skill_id,
                    protocol_id,
                    skill_name,
                    version,
                    utc_now(),
                    str(root),
                    pre_hash,
                    manifest_hash,
                    "STAGED_UNEVALUATED",
                    0,
                    0,
                ),
            )
            connection.commit()
        self._event(
            "SKILL_STAGED",
            {"skill_id": skill_id, "protocol_id": protocol_id, "manifest_hash": manifest_hash},
        )
        return {
            "skill_id": skill_id,
            "protocol_id": protocol_id,
            "skill_name": skill_name,
            "version": version,
            "path": str(root),
            "pre_generation_hash": pre_hash,
            "manifest_hash": manifest_hash,
            "state": "STAGED_UNEVALUATED",
            "installed": False,
            "activated": False,
            "evaluation_required": True,
        }

    def protocols(self, scope_key: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM protocols"
        values: tuple[Any, ...] = ()
        if scope_key:
            query += " WHERE scope_key=?"
            values = (scope_key,)
        query += " ORDER BY created_at,protocol_id"
        with closing(self.connect()) as connection:
            rows = connection.execute(query, values).fetchall()
        return [
            {**dict(row), "evidence_ids": json.loads(str(row["evidence_ids_json"]))} for row in rows
        ]

    def skills(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM skills ORDER BY created_at,skill_id"
            ).fetchall()
        return [
            {**dict(row), "installed": bool(row["installed"]), "activated": bool(row["activated"])}
            for row in rows
        ]

    def create_group(
        self,
        *,
        title: str,
        group_kind: str,
        parent_group_id: str = "GROUP-ROOT",
        rank: int | None = None,
    ) -> dict[str, Any]:
        if not title.strip():
            raise ValueError("archive group title cannot be empty")
        with self.connect() as connection:
            parent = connection.execute(
                "SELECT group_id FROM archive_groups WHERE group_id=?", (parent_group_id,)
            ).fetchone()
            if parent is None:
                raise KeyError(parent_group_id)
            if rank is None:
                rank = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(rank),0)+1 FROM archive_groups WHERE parent_group_id=?",
                        (parent_group_id,),
                    ).fetchone()[0]
                )
            group_id = f"GROUP-{uuid.uuid4()}"
            connection.execute(
                "INSERT INTO archive_groups VALUES(?,?,?,?,?,?,?)",
                (group_id, parent_group_id, title, group_kind.upper(), rank, utc_now(), 0),
            )
            connection.commit()
        self._event(
            "ARCHIVE_GROUP_CREATED", {"group_id": group_id, "parent_group_id": parent_group_id}
        )
        return {
            "group_id": group_id,
            "parent_group_id": parent_group_id,
            "title": title,
            "group_kind": group_kind.upper(),
            "rank": rank,
        }

    def attach(
        self, *, group_id: str, item_type: str, item_id: str, relation: str = "CONTAINS"
    ) -> dict[str, Any]:
        with self.connect() as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM archive_groups WHERE group_id=?", (group_id,)
                ).fetchone()
                is None
            ):
                raise KeyError(group_id)
            rank = int(
                connection.execute(
                    "SELECT COALESCE(MAX(rank),0)+1 FROM archive_members WHERE group_id=?",
                    (group_id,),
                ).fetchone()[0]
            )
            connection.execute(
                "INSERT OR REPLACE INTO archive_members VALUES(?,?,?,?,?,?)",
                (group_id, item_type.upper(), item_id, relation, rank, utc_now()),
            )
            connection.commit()
        edge = self.connect_nodes(
            source_type="GROUP",
            source_id=group_id,
            target_type=item_type.upper(),
            target_id=item_id,
            relation=relation,
            dimensions={"archive": True},
        )
        return {
            "group_id": group_id,
            "item_type": item_type.upper(),
            "item_id": item_id,
            "rank": rank,
            "edge": edge,
        }

    def connect_nodes(
        self,
        *,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relation: str,
        dimensions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not relation.strip():
            raise ValueError("graph relation cannot be empty")
        edge_id = f"WBEDGE-{uuid.uuid4()}"
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO graph_edges VALUES(?,?,?,?,?,?,?,?)",
                (
                    edge_id,
                    source_type.upper(),
                    source_id,
                    target_type.upper(),
                    target_id,
                    relation,
                    canonical_json(dimensions or {}),
                    utc_now(),
                ),
            )
            connection.commit()
        return {"edge_id": edge_id, "relation": relation, "dimensions": dimensions or {}}

    def archive_tree(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            groups = [
                dict(row)
                for row in connection.execute("SELECT * FROM archive_groups ORDER BY rank,group_id")
            ]
            members = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM archive_members ORDER BY group_id,rank"
                )
            ]
        return {
            "schema": "kch.workbench-archive-tree.v0.1.0",
            "root_group_id": "GROUP-ROOT",
            "groups": groups,
            "members": members,
            "deletion_performed": False,
        }

    def graph(self) -> dict[str, Any]:
        tree = self.archive_tree()
        nodes: list[dict[str, Any]] = [
            {
                "id": group["group_id"],
                "type": "GROUP",
                "label": group["title"],
                "dimensions": {"kind": group["group_kind"], "rank": group["rank"]},
            }
            for group in tree["groups"]
        ]
        edges = [
            {
                "source": group["parent_group_id"],
                "target": group["group_id"],
                "relation": "SUBGROUP_OF",
                "dimensions": {"archive": True},
            }
            for group in tree["groups"]
            if group["parent_group_id"]
        ]
        for member in tree["members"]:
            nodes.append(
                {
                    "id": member["item_id"],
                    "type": member["item_type"],
                    "label": member["item_id"],
                    "dimensions": {"archive_rank": member["rank"]},
                }
            )
            edges.append(
                {
                    "source": member["group_id"],
                    "target": member["item_id"],
                    "relation": member["relation"],
                    "dimensions": {"archive": True},
                }
            )
        with closing(self.connect()) as connection:
            custom = connection.execute(
                "SELECT * FROM graph_edges ORDER BY created_at,edge_id"
            ).fetchall()
            sources = connection.execute(
                "SELECT * FROM sources ORDER BY captured_at,source_id"
            ).fetchall()
            lessons = connection.execute(
                "SELECT * FROM lessons ORDER BY created_at,lesson_id"
            ).fetchall()
            protocols = connection.execute(
                "SELECT * FROM protocols ORDER BY created_at,protocol_id"
            ).fetchall()
            skills = connection.execute(
                "SELECT * FROM skills ORDER BY created_at,skill_id"
            ).fetchall()
        edges.extend(
            {
                "edge_id": row["edge_id"],
                "source": row["source_id"],
                "target": row["target_id"],
                "relation": row["relation"],
                "dimensions": json.loads(str(row["dimensions_json"])),
            }
            for row in custom
        )
        for source in sources:
            nodes.append(
                {
                    "id": source["source_id"],
                    "type": "SOURCE",
                    "label": source["title"],
                    "dimensions": {
                        "source_kind": source["source_kind"],
                        "workspace_id": source["workspace_id"],
                        "session_id": source["session_id"],
                        "provenance": True,
                    },
                }
            )
            for dimension_type, value in (
                ("WORKSPACE", source["workspace_id"]),
                ("SESSION", source["session_id"]),
            ):
                if value:
                    dimension_id = f"{dimension_type}-{value}"
                    nodes.append(
                        {
                            "id": dimension_id,
                            "type": dimension_type,
                            "label": str(value),
                            "dimensions": {dimension_type.casefold(): True},
                        }
                    )
                    edges.append(
                        {
                            "source": dimension_id,
                            "target": source["source_id"],
                            "relation": "CONTAINS_SOURCE",
                            "dimensions": {dimension_type.casefold(): True},
                        }
                    )
        for lesson in lessons:
            nodes.append(
                {
                    "id": lesson["lesson_id"],
                    "type": "LESSON",
                    "label": lesson["statement"],
                    "dimensions": {
                        "domain": lesson["domain"],
                        "kind": lesson["lesson_kind"],
                        "candidate": lesson["status"] == "ACTIVE_CANDIDATE",
                    },
                }
            )
            edges.append(
                {
                    "source": lesson["source_id"],
                    "target": lesson["lesson_id"],
                    "relation": "EVIDENCES_CANDIDATE",
                    "dimensions": {"provenance": True, "domain": lesson["domain"]},
                }
            )
        for protocol in protocols:
            nodes.append(
                {
                    "id": protocol["protocol_id"],
                    "type": "PROTOCOL",
                    "label": protocol["title"],
                    "dimensions": {
                        "scope_key": protocol["scope_key"],
                        "version": protocol["version"],
                    },
                }
            )
            for lesson_id in json.loads(str(protocol["evidence_ids_json"])):
                edges.append(
                    {
                        "source": lesson_id,
                        "target": protocol["protocol_id"],
                        "relation": "SUPPORTS_PROTOCOL",
                        "dimensions": {"evidence": True},
                    }
                )
        for skill in skills:
            nodes.append(
                {
                    "id": skill["skill_id"],
                    "type": "SKILL",
                    "label": skill["skill_name"],
                    "dimensions": {
                        "version": skill["version"],
                        "state": skill["status"],
                        "installed": bool(skill["installed"]),
                        "activated": bool(skill["activated"]),
                    },
                }
            )
            edges.append(
                {
                    "source": skill["protocol_id"],
                    "target": skill["skill_id"],
                    "relation": "GENERATES_STAGED_SKILL",
                    "dimensions": {"artifact": True},
                }
            )
        unique_nodes = {node["id"]: node for node in nodes}
        return {
            "schema": "kch.workbench-multidimensional-graph.v0.1.0",
            "nodes": list(unique_nodes.values()),
            "edges": edges,
            "dimensions": ["archive", "workspace", "session", "domain", "artifact", "provenance"],
            "click_target_contract": "NODE_ID_RESOLVES_THROUGH_RESOLVE_NODE",
        }

    def resolve_node(self, node_id: str) -> dict[str, Any]:
        tables = (
            ("archive_groups", "group_id", "GROUP"),
            ("sources", "source_id", "SOURCE"),
            ("lessons", "lesson_id", "LESSON"),
            ("protocols", "protocol_id", "PROTOCOL"),
            ("skills", "skill_id", "SKILL"),
            ("handoffs", "handoff_id", "HANDOFF"),
        )
        with closing(self.connect()) as connection:
            for table, key, node_type in tables:
                row = connection.execute(
                    f"SELECT * FROM {table} WHERE {key}=?", (node_id,)
                ).fetchone()
                if row is not None:
                    return {
                        "state": "RESOLVED",
                        "node_id": node_id,
                        "node_type": node_type,
                        "record": dict(row),
                    }
        if node_id.startswith("WORKSPACE-") or node_id.startswith("SESSION-"):
            return {
                "state": "RESOLVED_DIMENSION",
                "node_id": node_id,
                "node_type": node_id.split("-", 1)[0],
            }
        return {"state": "NOT_FOUND", "node_id": node_id}

    def set_group_archived(self, group_id: str, archived: bool) -> dict[str, Any]:
        if group_id == "GROUP-ROOT" and archived:
            raise ValueError("the root archive group cannot be archived")
        with self.connect() as connection:
            changed = connection.execute(
                "UPDATE archive_groups SET archived=? WHERE group_id=?",
                (1 if archived else 0, group_id),
            ).rowcount
            connection.commit()
        if changed != 1:
            raise KeyError(group_id)
        self._event("ARCHIVE_GROUP_STATE_CHANGED", {"group_id": group_id, "archived": archived})
        return {"group_id": group_id, "archived": archived, "deletion_performed": False}

    def configure_budget_account(
        self,
        *,
        account_id: str,
        provider: str,
        unit: str,
        weekly_limit: Any | None,
        currency: str | None,
        week_anchor: str,
        telemetry_source: str,
    ) -> dict[str, Any]:
        unit = unit.upper()
        if unit not in self.BUDGET_UNITS:
            raise ValueError(f"unit must be one of {sorted(self.BUDGET_UNITS)}")
        if unit in {"TOKENS", "CURRENCY"} and weekly_limit is None:
            limit = None
        else:
            limit = None if weekly_limit is None else decimal_text(weekly_limit)
        if unit == "CURRENCY" and not currency:
            raise ValueError("currency budget requires an explicit currency")
        body = {
            "account_id": account_id,
            "provider": provider,
            "unit": unit,
            "weekly_limit": limit,
            "currency": currency,
            "week_anchor": week_anchor,
            "telemetry_source": telemetry_source,
            "source_boundary": "DECLARED_CONFIGURATION_NOT_LIVE_ACCOUNT_TELEMETRY",
        }
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO budget_accounts VALUES(?,?,?,?,?,?,?,?,1)",
                (
                    account_id,
                    provider,
                    unit,
                    limit,
                    currency,
                    week_anchor,
                    telemetry_source,
                    utc_now(),
                ),
            )
            connection.commit()
        self._event("BUDGET_ACCOUNT_CONFIGURED", body)
        return body

    def set_budget_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        required = set(DEFAULT_POLICY)
        if set(policy) != required:
            raise ValueError(
                f"budget policy fields mismatch: missing={sorted(required - set(policy))}, extras={sorted(set(policy) - required)}"
            )
        for key in (
            "refresh_at_remaining_percent",
            "checkpoint_at_remaining_percent",
            "handoff_at_remaining_percent",
            "critical_at_remaining_percent",
        ):
            value = float(policy[key])
            if value < 0 or value > 100:
                raise ValueError(f"{key} must be between 0 and 100")
        self._set_setting("budget_policy", policy)
        self._event("BUDGET_POLICY_REPLACED", {"policy_hash": sha256_json(policy)})
        return {"policy": policy, "policy_hash": sha256_json(policy)}

    def record_budget_sample(
        self,
        *,
        account_id: str,
        used_value: Any | None,
        available_percent: Any | None,
        source_receipt: dict[str, Any],
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            account_row = connection.execute(
                "SELECT * FROM budget_accounts WHERE account_id=? AND enabled=1", (account_id,)
            ).fetchone()
        if account_row is None:
            raise KeyError(account_id)
        account = dict(account_row)
        if not source_receipt:
            raise ValueError("budget sample requires a non-empty source receipt")
        used = None if used_value is None else decimal_text(used_value)
        available = None if available_percent is None else float(available_percent)
        if available is not None and not 0 <= available <= 100:
            raise ValueError("available_percent must be between 0 and 100")
        if available is None and used is not None and account["weekly_limit"] is not None:
            limit = float(account["weekly_limit"])
            available = (
                0.0 if limit == 0 else max(0.0, min(100.0, (limit - float(used)) / limit * 100.0))
            )
            derivation = "DERIVED_FROM_DECLARED_WEEKLY_LIMIT_AND_OBSERVED_USED_VALUE"
        elif available is not None:
            derivation = "OBSERVED_AVAILABLE_PERCENT_FROM_SOURCE_RECEIPT"
        else:
            derivation = "NOT_ESTIMABLE_MISSING_LIMIT_OR_AVAILABILITY"
        adjudication = self._budget_adjudication(available, derivation)
        sample_id = f"BUDGET-{uuid.uuid4()}"
        receipt_hash = sha256_json(source_receipt)
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO budget_samples VALUES(?,?,?,?,?,?,?,?)",
                (
                    sample_id,
                    account_id,
                    observed_at or utc_now(),
                    used,
                    None if available is None else decimal_text(available),
                    canonical_json(source_receipt),
                    receipt_hash,
                    canonical_json(adjudication),
                ),
            )
            connection.commit()
        self._event(
            "BUDGET_SAMPLE_RECORDED",
            {"sample_id": sample_id, "account_id": account_id, "adjudication": adjudication},
        )
        maintenance = self.run_maintenance(
            trigger=f"AUTOMATIC_AFTER_BUDGET_SAMPLE:{sample_id}", force=True
        )
        return {
            "sample_id": sample_id,
            "account_id": account_id,
            "used_value": used,
            "available_percent": available,
            "source_receipt_hash": receipt_hash,
            "adjudication": adjudication,
            "automatic_maintenance": maintenance,
        }

    def _budget_adjudication(self, available: float | None, derivation: str) -> dict[str, Any]:
        policy = self._setting("budget_policy")
        if available is None:
            return {
                "state": "NOT_ESTIMABLE",
                "derivation": derivation,
                "cadence_level": "NORMAL",
                "next_interval_minutes": int(policy["interval_minutes"]["NORMAL"]),
                "automatic_handoff": False,
            }
        if available <= float(policy["critical_at_remaining_percent"]):
            level = "CRITICAL"
        elif available <= float(policy["handoff_at_remaining_percent"]):
            level = "HANDOFF"
        elif available <= float(policy["checkpoint_at_remaining_percent"]):
            level = "CHECKPOINT"
        elif available <= float(policy["refresh_at_remaining_percent"]):
            level = "REFRESH"
        else:
            level = "NORMAL"
        return {
            "state": "ADJUDICATED_FROM_EXPLICIT_BUDGET_EVIDENCE",
            "derivation": derivation,
            "available_percent": available,
            "cadence_level": level,
            "next_interval_minutes": int(policy["interval_minutes"][level]),
            "automatic_handoff": level in {"HANDOFF", "CRITICAL"},
            "automatic_checkpoint_request": level in {"CHECKPOINT", "HANDOFF", "CRITICAL"},
        }

    def budget_status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            accounts = [
                dict(row)
                for row in connection.execute("SELECT * FROM budget_accounts WHERE enabled=1")
            ]
            projections = []
            for account in accounts:
                sample = connection.execute(
                    "SELECT * FROM budget_samples WHERE account_id=? ORDER BY observed_at DESC,sample_id DESC LIMIT 1",
                    (account["account_id"],),
                ).fetchone()
                projections.append(
                    {
                        "account": account,
                        "latest_sample": None
                        if sample is None
                        else {
                            **dict(sample),
                            "adjudication": json.loads(str(sample["adjudication_json"])),
                        },
                    }
                )
        estimable = [
            float(item["latest_sample"]["available_percent"])
            for item in projections
            if item["latest_sample"] is not None
            and item["latest_sample"]["available_percent"] is not None
        ]
        minimum = min(estimable) if estimable else None
        aggregate = self._budget_adjudication(
            minimum,
            "MINIMUM_REMAINING_ACROSS_EXPLICIT_ACCOUNT_SAMPLES"
            if estimable
            else "NO_ESTIMABLE_SAMPLES",
        )
        return {
            "schema": "kch.workbench-weekly-budget-status.v0.1.0",
            "accounts": projections,
            "aggregate": aggregate,
            "live_host_telemetry_connected": any(
                item["account"]["telemetry_source"] == "HOST_TELEMETRY"
                and item["latest_sample"] is not None
                for item in projections
            ),
            "prices_inferred": False,
            "policy": self._setting("budget_policy"),
        }

    def _create_handoff(self, trigger: str, budget: dict[str, Any]) -> dict[str, Any]:
        handoff_id = f"HANDOFF-{uuid.uuid4()}"
        created = utc_now()
        protocols = self.protocols()
        skills = self.skills()
        tree = self.archive_tree()
        unresolved = []
        for scope in self._scopes():
            protocol = self._protocol_for_scope(scope)
            if protocol.get("protocol_id") is None:
                unresolved.append({"scope_key": scope, "state": protocol["state"]})
        body = {
            "schema": "kch.workbench-handoff-packet.v0.1.0",
            "handoff_id": handoff_id,
            "created_at": created,
            "trigger": trigger,
            "budget": budget,
            "archive": tree,
            "protocols": protocols,
            "skills": skills,
            "unresolved": unresolved,
            "raw_sources_retained_by_reference": True,
            "secret_values_included": False,
            "external_task_created": False,
            "previous_external_task_archived": False,
            "host_connector_required": True,
        }
        path = self.handoff_root / f"{created[:10]}-{handoff_id}.json"
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        digest = sha256_bytes(path.read_bytes())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO handoffs VALUES(?,?,?,?,?,?,?)",
                (
                    handoff_id,
                    created,
                    trigger,
                    canonical_json(budget),
                    str(path),
                    digest,
                    "READY_FOR_HOST_CONNECTOR",
                ),
            )
            connection.commit()
        self._event("HANDOFF_PACKET_CREATED", {"handoff_id": handoff_id, "manifest_hash": digest})
        return {
            "handoff_id": handoff_id,
            "path": str(path),
            "manifest_hash": digest,
            "state": "READY_FOR_HOST_CONNECTOR",
        }

    def _scopes(self) -> list[str]:
        with closing(self.connect()) as connection:
            return [
                str(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT scope_key FROM lessons ORDER BY scope_key"
                )
            ]

    def run_maintenance(
        self,
        *,
        trigger: str,
        force: bool = False,
        scope_key: str | None = None,
    ) -> dict[str, Any]:
        budget = self.budget_status()
        interval = int(budget["aggregate"]["next_interval_minutes"])
        last = self._setting("last_maintenance_at")
        due = last is None or datetime.fromisoformat(str(last).replace("Z", "+00:00")) + timedelta(
            minutes=interval
        ) <= datetime.now(UTC)
        if not force and not due:
            return {
                "state": "NOT_DUE",
                "last_maintenance_at": last,
                "next_interval_minutes": interval,
                "budget": budget["aggregate"],
            }
        scopes = [scope_key] if scope_key else self._scopes()
        generated = []
        for scope in scopes:
            protocol = self._protocol_for_scope(scope)
            skill = (
                self._skill_for_protocol(protocol)
                if self._setting("budget_policy")["automatic_stage_skills"]
                and protocol.get("protocol_id")
                else {"state": "NOT_GENERATED"}
            )
            generated.append({"scope_key": scope, "protocol": protocol, "skill": skill})
        handoff = None
        if budget["aggregate"].get("automatic_handoff"):
            handoff = self._create_handoff(trigger, budget)
        now = utc_now()
        self._set_setting("last_maintenance_at", now)
        event = self._event(
            "MAINTENANCE_COMPLETED",
            {
                "trigger": trigger,
                "scopes": scopes,
                "handoff_id": None if handoff is None else handoff["handoff_id"],
            },
        )
        return {
            "state": "MAINTENANCE_COMPLETED",
            "trigger": trigger,
            "generated": generated,
            "handoff": handoff,
            "budget": budget,
            "checkpoint_requested": bool(budget["aggregate"].get("automatic_checkpoint_request")),
            "checkpoint_executed": False,
            "event": event,
        }

    def handoffs(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM handoffs ORDER BY created_at,handoff_id"
                )
            ]

    def kwandata_envelope(self, item_type: str, item_id: str) -> dict[str, Any]:
        return {
            "schema": "kch.workbench-kwandata-envelope.v0.1.0",
            "item_type": item_type.upper(),
            "item_id": item_id,
            "graph": self.graph(),
            "authority_inherited": False,
            "ingestion_executed": False,
            "target": "KWANDATA",
        }

    def kwandocs_envelope(self, item_type: str, item_id: str) -> dict[str, Any]:
        return {
            "schema": "kch.workbench-kwandocs-envelope.v0.1.0",
            "item_type": item_type.upper(),
            "item_id": item_id,
            "provenance_required": True,
            "canonicalization_requested": False,
            "authority_inherited": False,
            "ingestion_executed": False,
            "target": "KWANDOCS",
        }

    def verify(self) -> dict[str, Any]:
        errors: list[str] = []
        previous = "0" * 64
        with closing(self.connect()) as connection:
            events = connection.execute("SELECT * FROM events ORDER BY seq").fetchall()
            for row in events:
                body = {
                    "event_id": row["event_id"],
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "payload": json.loads(str(row["payload_json"])),
                }
                expected = sha256_json({**body, "previous_hash": previous})
                if row["previous_hash"] != previous or row["event_hash"] != expected:
                    errors.append(f"event chain mismatch at seq {row['seq']}")
                previous = expected
            sources = connection.execute("SELECT * FROM sources").fetchall()
            for source in sources:
                path = Path(source["stored_path"])
                if not path.is_file():
                    errors.append(f"stored source missing: {source['source_id']}")
                elif (
                    source["storage_state"] == "EXACT_ORIGINAL_BYTES_STORED"
                    and sha256_bytes(path.read_bytes()) != source["original_sha256"]
                ):
                    errors.append(f"exact source hash mismatch: {source['source_id']}")
                if not source["normalized_path"]:
                    errors.append(f"normalized source path absent: {source['source_id']}")
                    continue
                normalized_path = Path(source["normalized_path"])
                if not normalized_path.is_file():
                    errors.append(f"normalized source missing: {source['source_id']}")
                elif sha256_bytes(normalized_path.read_bytes()) != source["normalized_sha256"]:
                    errors.append(f"normalized source hash mismatch: {source['source_id']}")
            protocols = connection.execute("SELECT * FROM protocols").fetchall()
            skills = connection.execute("SELECT * FROM skills").fetchall()
        for protocol in protocols:
            path = Path(protocol["path"])
            if not path.is_file() or sha256_bytes(path.read_bytes()) != protocol["manifest_hash"]:
                errors.append(f"protocol hash mismatch: {protocol['protocol_id']}")
        for skill in skills:
            root = Path(skill["path"])
            manifest_path = root / "MANIFEST.json"
            if not manifest_path.is_file():
                errors.append(f"skill manifest missing: {skill['skill_id']}")
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["manifest_hash"] != skill["manifest_hash"]:
                errors.append(f"skill manifest hash mismatch: {skill['skill_id']}")
            for item in manifest["files"]:
                path = safe_child(root, item["path"])
                if not path.is_file() or sha256_bytes(path.read_bytes()) != item["sha256"]:
                    errors.append(f"skill file hash mismatch: {skill['skill_id']}:{item['path']}")
        return {
            "schema": "kch.workbench-integrity.v0.1.0",
            "gate": "PASS" if not errors else "FAIL",
            "event_count": len(events),
            "source_count": len(sources),
            "protocol_count": len(protocols),
            "skill_count": len(skills),
            "errors": errors,
        }

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            counts = {
                "sources": int(connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]),
                "lessons": int(connection.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]),
                "protocols": int(
                    connection.execute("SELECT COUNT(*) FROM protocols").fetchone()[0]
                ),
                "skills": int(connection.execute("SELECT COUNT(*) FROM skills").fetchone()[0]),
                "archive_groups": int(
                    connection.execute("SELECT COUNT(*) FROM archive_groups").fetchone()[0]
                ),
                "handoffs": int(connection.execute("SELECT COUNT(*) FROM handoffs").fetchone()[0]),
                "secret_references": int(
                    connection.execute("SELECT COUNT(*) FROM secret_references").fetchone()[0]
                ),
            }
        return {
            "schema": "kch.workbench-suite-status.v0.1.0",
            **counts,
            "budget": self.budget_status(),
            "integrity": self.verify(),
            "automatic_learning_detection": True,
            "automatic_protocol_refresh": True,
            "automatic_skill_staging": bool(
                self._setting("budget_policy")["automatic_stage_skills"]
            ),
            "automatic_scheduler_binding": self._setting("scheduler_binding"),
            "automatic_skill_installation": False,
            "automatic_skill_activation": False,
            "raw_chat_txt_supported": True,
            "secret_values_stored": False,
            "external_task_handoff_requires_connector": True,
            "canonical_product_name": "UNDECIDED_USER_NAMING_OPEN",
        }
