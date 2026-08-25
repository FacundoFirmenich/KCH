from __future__ import annotations

import fnmatch
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constitutional import Actor, ConstitutionalAuthorityError
from .contracts import canonical_json, sha256_json, sqlite_connection
from .recovery import RecoveryVault

DDL = """
CREATE TABLE IF NOT EXISTS permission_rules (
    rule_id TEXT PRIMARY KEY,
    actor_pattern TEXT NOT NULL,
    resource_pattern TEXT NOT NULL,
    operation_pattern TEXT NOT NULL,
    effect TEXT NOT NULL,
    priority INTEGER NOT NULL,
    scope TEXT NOT NULL,
    session_id TEXT,
    expires_at TEXT,
    enabled INTEGER NOT NULL,
    rationale TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    rule_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS permission_decisions (
    decision_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    resource TEXT NOT NULL,
    operation TEXT NOT NULL,
    session_id TEXT,
    decision TEXT NOT NULL,
    governing_rule_id TEXT,
    evidence_json TEXT NOT NULL,
    decision_hash TEXT NOT NULL
);
"""

OPERATIONS = {
    "READ",
    "LIST",
    "CREATE",
    "WRITE",
    "MODIFY",
    "DELETE",
    "EXECUTE",
    "PROGRAM",
    "NETWORK_ACCESS",
    "CLIPBOARD_READ",
    "CLIPBOARD_WRITE",
    "SCREEN_CAPTURE",
    "SCHEDULE",
    "AUDIO_RECORD",
    "SPEAK",
    "INSTALL",
    "ENABLE",
    "PUBLISH",
    "GRANT_PERMISSION",
    "REVOKE_PERMISSION",
}

DEFAULT_RULES = [
    ("USER", "*", "*", "ALLOW", 100000, "GLOBAL", "User is sovereign over KCH policy."),
    (
        "MODEL",
        "constitution://*",
        "READ",
        "ALLOW",
        9000,
        "GLOBAL",
        "Models may read the effective constitution.",
    ),
    (
        "MODEL",
        "constitution://*",
        "*",
        "DENY",
        8999,
        "GLOBAL",
        "Models cannot mutate constitutional authority.",
    ),
    (
        "KCH_SYSTEM",
        "runtime://*",
        "*",
        "ALLOW",
        8000,
        "GLOBAL",
        "KCH may maintain its isolated runtime.",
    ),
    (
        "KCH_SYSTEM",
        "clipboard://local/*",
        "CLIPBOARD_READ",
        "ALLOW",
        7990,
        "GLOBAL",
        "The local clipboard monitor may read without exporting content.",
    ),
    (
        "PROACTIVE_LAUNCHER",
        "voice://local/alerts",
        "SPEAK",
        "ALLOW",
        7100,
        "GLOBAL",
        "The user-programmable launcher may voice local alerts.",
    ),
    (
        "PROACTIVE_LAUNCHER",
        "tool://internal/*",
        "EXECUTE",
        "ALLOW",
        7000,
        "GLOBAL",
        "The user-programmable launcher may invoke registered internal tools.",
    ),
    (
        "*",
        "file://external/*",
        "DELETE",
        "DENY",
        1000,
        "GLOBAL",
        "External deletion needs a user-authored rule.",
    ),
    (
        "*",
        "terminal://*",
        "EXECUTE",
        "DENY",
        100,
        "GLOBAL",
        "Terminal execution is not implicitly granted.",
    ),
    (
        "*",
        "network://*",
        "NETWORK_ACCESS",
        "DENY",
        100,
        "GLOBAL",
        "Network access is not implicitly granted.",
    ),
    ("*", "*", "*", "DENY", -100000, "GLOBAL", "Default deny when no explicit authority exists."),
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class PermissionGovernor:
    """Explicit authority matrix for files, terminal, code, disk, network, and KCH tools."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "permissions.sqlite3"
        self.vault = RecoveryVault(self.root / "recovery")
        with self.connect() as connection:
            connection.executescript(DDL)
            if connection.execute("SELECT COUNT(*) FROM permission_rules").fetchone()[0] == 0:
                for actor, resource, operation, effect, priority, scope, rationale in DEFAULT_RULES:
                    self._insert_rule(
                        connection,
                        actor=actor,
                        resource=resource,
                        operation=operation,
                        effect=effect,
                        priority=priority,
                        scope=scope,
                        session_id=None,
                        expires_at=None,
                        rationale=rationale,
                        created_by="KCH_SYSTEM",
                    )
                connection.commit()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _insert_rule(
        self,
        connection: sqlite3.Connection,
        *,
        actor: str,
        resource: str,
        operation: str,
        effect: str,
        priority: int,
        scope: str,
        session_id: str | None,
        expires_at: str | None,
        rationale: str,
        created_by: str,
    ) -> dict[str, Any]:
        if effect not in {"ALLOW", "DENY", "WARN"}:
            raise ValueError("effect must be ALLOW, DENY, or WARN")
        if operation != "*" and operation not in OPERATIONS:
            raise ValueError(f"unknown operation: {operation}")
        if scope not in {"GLOBAL", "PROJECT", "SESSION", "ONE_SHOT"}:
            raise ValueError("invalid permission scope")
        if scope in {"SESSION", "ONE_SHOT"} and not session_id:
            raise ValueError("session_id required for scoped rule")
        rule_id = f"PERM-{uuid.uuid4()}"
        timestamp = utc_now()
        body = {
            "rule_id": rule_id,
            "actor_pattern": actor,
            "resource_pattern": resource,
            "operation_pattern": operation,
            "effect": effect,
            "priority": priority,
            "scope": scope,
            "session_id": session_id,
            "expires_at": expires_at,
            "rationale": rationale,
            "created_by": created_by,
            "created_at": timestamp,
        }
        digest = sha256_json(body)
        connection.execute(
            "INSERT INTO permission_rules VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rule_id,
                actor,
                resource,
                operation,
                effect,
                priority,
                scope,
                session_id,
                expires_at,
                1,
                rationale,
                created_by,
                timestamp,
                digest,
            ),
        )
        return {**body, "rule_hash": digest}

    def grant(
        self,
        *,
        actor_pattern: str,
        resource_pattern: str,
        operation_pattern: str,
        effect: str,
        priority: int,
        scope: str = "GLOBAL",
        session_id: str | None = None,
        expires_at: str | None = None,
        rationale: str,
        enacting_actor: Actor,
    ) -> dict[str, Any]:
        if enacting_actor is not Actor.USER:
            raise ConstitutionalAuthorityError("only USER may grant or alter KCH permissions")
        with self.connect() as connection:
            rule = self._insert_rule(
                connection,
                actor=actor_pattern,
                resource=resource_pattern,
                operation=operation_pattern,
                effect=effect,
                priority=priority,
                scope=scope,
                session_id=session_id,
                expires_at=expires_at,
                rationale=rationale,
                created_by=enacting_actor.value,
            )
            connection.commit()
        custody = self.vault.save_json(
            f"rules/{rule['rule_id']}.json",
            rule,
            kind="PERMISSION_RULE",
            actor="USER",
            operation="GRANT_PERMISSION",
        )
        return {**rule, "custody": custody}

    def revoke(self, rule_id: str, *, enacting_actor: Actor) -> dict[str, Any]:
        if enacting_actor is not Actor.USER:
            raise ConstitutionalAuthorityError("only USER may revoke KCH permissions")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM permission_rules WHERE rule_id=?", (rule_id,)
            ).fetchone()
            if row is None:
                raise KeyError(rule_id)
            connection.execute("UPDATE permission_rules SET enabled=0 WHERE rule_id=?", (rule_id,))
            connection.commit()
        receipt = {
            "rule_id": rule_id,
            "state": "REVOKED",
            "revoked_at": utc_now(),
            "previous_rule": dict(row),
        }
        self.vault.save_json(
            f"revocations/{rule_id}.json",
            receipt,
            kind="PERMISSION_REVOCATION",
            actor="USER",
            operation="REVOKE_PERMISSION",
        )
        return receipt

    def decide(
        self, *, actor: str, resource: str, operation: str, session_id: str | None = None
    ) -> dict[str, Any]:
        if operation not in OPERATIONS:
            raise ValueError(f"unknown operation: {operation}")
        now = datetime.now(UTC)
        applicable = []
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM permission_rules WHERE enabled=1 ORDER BY priority DESC,created_at,rule_id"
            ).fetchall()
            for row in rows:
                expires = parse_time(row["expires_at"])
                if expires is not None and expires <= now:
                    continue
                if row["session_id"] is not None and row["session_id"] != session_id:
                    continue
                if not fnmatch.fnmatchcase(actor, row["actor_pattern"]):
                    continue
                if not fnmatch.fnmatchcase(resource, row["resource_pattern"]):
                    continue
                if not fnmatch.fnmatchcase(operation, row["operation_pattern"]):
                    continue
                applicable.append(dict(row))
            governing = applicable[0] if applicable else None
            decision = "DENY" if governing is None else str(governing["effect"])
            decision_id = f"PDEC-{uuid.uuid4()}"
            timestamp = utc_now()
            evidence = {
                "applicable_rule_ids": [item["rule_id"] for item in applicable],
                "precedence": "HIGHEST_PRIORITY_THEN_OLDEST_STABLE_RULE",
                "user_can_reconfigure": True,
            }
            body = {
                "decision_id": decision_id,
                "timestamp": timestamp,
                "actor": actor,
                "resource": resource,
                "operation": operation,
                "session_id": session_id,
                "decision": decision,
                "governing_rule_id": None if governing is None else governing["rule_id"],
                "evidence": evidence,
            }
            digest = sha256_json(body)
            connection.execute(
                "INSERT INTO permission_decisions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    decision_id,
                    timestamp,
                    actor,
                    resource,
                    operation,
                    session_id,
                    decision,
                    body["governing_rule_id"],
                    canonical_json(evidence),
                    digest,
                ),
            )
            if governing and governing["scope"] == "ONE_SHOT":
                connection.execute(
                    "UPDATE permission_rules SET enabled=0 WHERE rule_id=?", (governing["rule_id"],)
                )
            connection.commit()
        return {
            **body,
            "decision_hash": digest,
            "authorized": decision == "ALLOW",
            "warning_only": decision == "WARN",
        }

    def require(self, **request: Any) -> dict[str, Any]:
        receipt = self.decide(**request)
        if not receipt["authorized"]:
            raise PermissionError(canonical_json(receipt))
        return receipt

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            active = connection.execute(
                "SELECT COUNT(*) FROM permission_rules WHERE enabled=1"
            ).fetchone()[0]
            decisions = connection.execute("SELECT COUNT(*) FROM permission_decisions").fetchone()[
                0
            ]
        return {
            "schema": "kch.permission-governor-status.v0.1.0",
            "active_rules": active,
            "decision_receipts": decisions,
            "domains": [
                "files",
                "terminal",
                "programming",
                "local_disk",
                "network",
                "clipboard",
                "screen",
                "scheduler",
                "tools",
                "installation",
            ],
            "model_can_modify_policy": False,
            "user_can_modify_policy": True,
        }
