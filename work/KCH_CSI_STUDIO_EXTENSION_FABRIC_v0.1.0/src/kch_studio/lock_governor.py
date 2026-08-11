from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constitutional import Actor, ConstitutionalAuthorityError
from .contracts import canonical_json, sha256_json, sqlite_connection

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS locks (
    lock_id TEXT PRIMARY KEY,
    resource_pattern TEXT NOT NULL,
    match_mode TEXT NOT NULL,
    operations_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    active INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    baseline_json TEXT NOT NULL,
    lock_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    resource TEXT NOT NULL,
    operation TEXT NOT NULL,
    current_sha256 TEXT,
    proposed_sha256 TEXT,
    payload_sha256 TEXT NOT NULL,
    explanation_json TEXT NOT NULL,
    matched_locks_json TEXT NOT NULL,
    proposal_hash TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authorizations (
    authorization_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE REFERENCES proposals(proposal_id),
    proposal_hash TEXT NOT NULL,
    lock_set_hash TEXT NOT NULL,
    trusted_channel TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT,
    consumed_at TEXT,
    consumption_hash TEXT
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
"""

MATCH_MODES = frozenset({"EXACT", "PREFIX", "GLOB"})
MUTATION_OPERATIONS = frozenset(
    {
        "CREATE",
        "WRITE",
        "MODIFY",
        "DELETE",
        "RENAME",
        "MOVE",
        "REGENERATE",
        "PROMOTE",
        "INSTALL",
        "CONFIGURE",
        "EXECUTE",
        "*",
    }
)
TRUSTED_USER_CHANNELS = frozenset(
    {"KCH_LOCAL_UI", "KCH_LOCAL_CLI", "HOST_ATTESTED_USER_GESTURE"}
)
RESOURCE_RE = re.compile(r"^[a-z][a-z0-9+.-]*://.+$", flags=re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resource_for_path(path: str | Path) -> str:
    return "file://" + Path(path).resolve().as_posix()


def _comparison(value: str) -> str:
    return value.casefold() if os.name == "nt" else value


class LockGovernor:
    """Optional fail-closed constitutional locks over KCH-governed mutations."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "locks.sqlite3"
        with self.connect() as connection:
            connection.executescript(DDL)
            connection.execute(
                "INSERT OR IGNORE INTO settings VALUES(?,?,?)",
                ("enabled", canonical_json(False), utc_now()),
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _require_user(actor: Actor) -> None:
        if actor is not Actor.USER:
            raise ConstitutionalAuthorityError(
                "lock enactment and authorization require a trusted USER gesture"
            )

    @staticmethod
    def _normalize_resource(resource: str) -> str:
        value = resource.strip().replace("\\", "/")
        if not RESOURCE_RE.fullmatch(value):
            raise ValueError("resource must be a non-empty scheme:// identifier")
        return value

    @staticmethod
    def _normalize_operations(operations: list[str]) -> list[str]:
        values = sorted({str(item).upper() for item in operations})
        if not values or any(item not in MUTATION_OPERATIONS for item in values):
            raise ValueError(f"operations must use {sorted(MUTATION_OPERATIONS)}")
        return values

    @staticmethod
    def _event(
        connection: sqlite3.Connection, event_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        row = connection.execute(
            "SELECT seq,event_hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        previous = "0" * 64 if row is None else str(row["event_hash"])
        timestamp = utc_now()
        body = {
            "timestamp": timestamp,
            "event_type": event_type,
            "payload": payload,
            "previous_hash": previous,
        }
        digest = sha256_json(body)
        cursor = connection.execute(
            "INSERT INTO events(timestamp,event_type,payload_json,previous_hash,event_hash) "
            "VALUES(?,?,?,?,?)",
            (timestamp, event_type, canonical_json(payload), previous, digest),
        )
        return {
            "seq": int(cursor.lastrowid),
            **body,
            "event_hash": digest,
        }

    def enabled(self) -> bool:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT value_json FROM settings WHERE key='enabled'"
            ).fetchone()
        return bool(json.loads(str(row[0]))) if row is not None else False

    def set_enabled(self, enabled: bool, *, actor: Actor) -> dict[str, Any]:
        self._require_user(actor)
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO settings VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET "
                "value_json=excluded.value_json,updated_at=excluded.updated_at",
                ("enabled", canonical_json(bool(enabled)), timestamp),
            )
            event = self._event(
                connection,
                "LOCK_GOVERNOR_ENABLED" if enabled else "LOCK_GOVERNOR_DISABLED",
                {"actor": actor.value, "enabled": bool(enabled)},
            )
            connection.commit()
        return {
            "schema": "kch.lock-governor-mode.v0.1.0",
            "enabled": bool(enabled),
            "default_enabled": False,
            "actor": actor.value,
            "event": event,
        }

    @staticmethod
    def _capture_baseline(resource: str, match_mode: str) -> dict[str, Any]:
        if not resource.lower().startswith("file://") or match_mode != "EXACT":
            return {"captured": False, "reason": "NON_EXACT_FILE_RESOURCE"}
        path = Path(resource[7:])
        exists = path.is_file()
        return {
            "captured": True,
            "kind": "FILE",
            "path": str(path.resolve()),
            "exists": exists,
            "bytes": path.stat().st_size if exists else None,
            "sha256": file_sha256(path) if exists else None,
        }

    def create_lock(
        self,
        *,
        resource_pattern: str,
        match_mode: str,
        operations: list[str],
        reason: str,
        actor: Actor,
        expires_at: str | None = None,
        capture_baseline: bool = True,
    ) -> dict[str, Any]:
        self._require_user(actor)
        resource = self._normalize_resource(resource_pattern)
        mode = match_mode.upper()
        if mode not in MATCH_MODES:
            raise ValueError(f"match_mode must be one of {sorted(MATCH_MODES)}")
        operation_values = self._normalize_operations(operations)
        if not reason.strip():
            raise ValueError("lock reason cannot be empty")
        expiry = parse_time(expires_at)
        if expiry is not None and expiry <= datetime.now(UTC):
            raise ValueError("lock expiry must be in the future")
        baseline = (
            self._capture_baseline(resource, mode)
            if capture_baseline
            else {"captured": False, "reason": "USER_DISABLED_BASELINE_CAPTURE"}
        )
        lock_id = f"LOCK-{uuid.uuid4()}"
        body = {
            "lock_id": lock_id,
            "resource_pattern": resource,
            "match_mode": mode,
            "operations": operation_values,
            "reason": reason.strip(),
            "active": True,
            "created_at": utc_now(),
            "expires_at": expires_at,
            "baseline": baseline,
        }
        digest = sha256_json({key: value for key, value in body.items() if key != "active"})
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO locks VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    lock_id,
                    resource,
                    mode,
                    canonical_json(operation_values),
                    reason.strip(),
                    1,
                    body["created_at"],
                    expires_at,
                    canonical_json(baseline),
                    digest,
                ),
            )
            event = self._event(
                connection,
                "LOCK_ENACTED",
                {"actor": actor.value, "lock_id": lock_id, "lock_hash": digest},
            )
            connection.commit()
        return {**body, "lock_hash": digest, "event": event}

    def deactivate_lock(self, lock_id: str, *, actor: Actor) -> dict[str, Any]:
        self._require_user(actor)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM locks WHERE lock_id=?", (lock_id,)
            ).fetchone()
            if row is None:
                raise KeyError(lock_id)
            if not bool(row["active"]):
                raise ValueError("lock is already inactive")
            connection.execute("UPDATE locks SET active=0 WHERE lock_id=?", (lock_id,))
            event = self._event(
                connection,
                "LOCK_DEACTIVATED",
                {"actor": actor.value, "lock_id": lock_id},
            )
            connection.commit()
        return {
            "lock_id": lock_id,
            "state": "INACTIVE",
            "deactivated_by": actor.value,
            "event": event,
        }

    @staticmethod
    def _row_lock(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "lock_id": str(row["lock_id"]),
            "resource_pattern": str(row["resource_pattern"]),
            "match_mode": str(row["match_mode"]),
            "operations": json.loads(str(row["operations_json"])),
            "reason": str(row["reason"]),
            "active": bool(row["active"]),
            "created_at": str(row["created_at"]),
            "expires_at": row["expires_at"],
            "baseline": json.loads(str(row["baseline_json"])),
            "lock_hash": str(row["lock_hash"]),
        }

    def locks(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM locks"
        if not include_inactive:
            query += " WHERE active=1"
        query += " ORDER BY created_at,lock_id"
        with closing(self.connect()) as connection:
            rows = connection.execute(query).fetchall()
        return [self._row_lock(row) for row in rows]

    @staticmethod
    def _matches(lock: dict[str, Any], resource: str, operation: str) -> bool:
        if "*" not in lock["operations"] and operation not in lock["operations"]:
            return False
        expiry = parse_time(lock["expires_at"])
        if expiry is not None and expiry <= datetime.now(UTC):
            return False
        pattern = _comparison(str(lock["resource_pattern"]))
        candidate = _comparison(resource)
        if lock["match_mode"] == "EXACT":
            return candidate == pattern
        if lock["match_mode"] == "PREFIX":
            prefix = pattern.rstrip("/")
            return candidate == prefix or candidate.startswith(prefix + "/")
        return fnmatch.fnmatchcase(candidate, pattern)

    def matching_locks(self, resource: str, operation: str) -> list[dict[str, Any]]:
        normalized = self._normalize_resource(resource)
        operation_value = operation.upper()
        if operation_value not in MUTATION_OPERATIONS:
            raise ValueError(f"unknown mutation operation: {operation}")
        return [
            lock
            for lock in self.locks()
            if self._matches(lock, normalized, operation_value)
        ]

    @staticmethod
    def _binding(
        *,
        resource: str,
        operation: str,
        current_sha256: str | None,
        proposed_sha256: str | None,
        payload_sha256: str,
    ) -> dict[str, Any]:
        return {
            "resource": resource,
            "operation": operation,
            "current_sha256": current_sha256,
            "proposed_sha256": proposed_sha256,
            "payload_sha256": payload_sha256,
        }

    def preflight(
        self,
        *,
        resource: str,
        operation: str,
        current_sha256: str | None,
        proposed_sha256: str | None,
        payload_sha256: str,
        authorization_id: str | None = None,
    ) -> dict[str, Any]:
        normalized = self._normalize_resource(resource)
        operation_value = operation.upper()
        binding = self._binding(
            resource=normalized,
            operation=operation_value,
            current_sha256=current_sha256,
            proposed_sha256=proposed_sha256,
            payload_sha256=payload_sha256,
        )
        if not self.enabled():
            return {
                "schema": "kch.lock-preflight.v0.1.0",
                "gate": "ALLOW_GOVERNOR_DISABLED",
                "authorized": True,
                "binding": binding,
                "matched_locks": [],
            }
        matched = self.matching_locks(normalized, operation_value)
        if not matched:
            return {
                "schema": "kch.lock-preflight.v0.1.0",
                "gate": "ALLOW_NO_MATCHING_LOCK",
                "authorized": True,
                "binding": binding,
                "matched_locks": [],
            }
        if authorization_id is None:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                event = self._event(
                    connection,
                    "LOCKED_MUTATION_BLOCKED",
                    {
                        "binding": binding,
                        "matched_lock_ids": [item["lock_id"] for item in matched],
                    },
                )
                connection.commit()
            return {
                "schema": "kch.lock-preflight.v0.1.0",
                "gate": "BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED",
                "authorized": False,
                "binding": binding,
                "matched_locks": matched,
                "required_explanation_fields": [
                    "rationale",
                    "impact",
                    "dependencies",
                    "recovery_plan",
                ],
                "session_wide_consent_accepted": False,
                "event": event,
            }
        return self._consume(authorization_id, binding=binding, matched=matched)

    def propose(
        self,
        *,
        resource: str,
        operation: str,
        current_sha256: str | None,
        proposed_sha256: str | None,
        payload_sha256: str,
        rationale: str,
        impact: str,
        dependencies: list[str],
        recovery_plan: str,
    ) -> dict[str, Any]:
        if not self.enabled():
            raise ValueError("lock governor is disabled")
        explanation = {
            "rationale": rationale.strip(),
            "impact": impact.strip(),
            "dependencies": [str(item).strip() for item in dependencies if str(item).strip()],
            "recovery_plan": recovery_plan.strip(),
        }
        if not explanation["rationale"] or not explanation["impact"] or not explanation[
            "recovery_plan"
        ]:
            raise ValueError("rationale, impact and recovery_plan cannot be empty")
        normalized = self._normalize_resource(resource)
        operation_value = operation.upper()
        matched = self.matching_locks(normalized, operation_value)
        if not matched:
            raise ValueError("no active lock governs the proposed mutation")
        binding = self._binding(
            resource=normalized,
            operation=operation_value,
            current_sha256=current_sha256,
            proposed_sha256=proposed_sha256,
            payload_sha256=payload_sha256,
        )
        matched_receipts = [
            {"lock_id": item["lock_id"], "lock_hash": item["lock_hash"]}
            for item in matched
        ]
        proposal_id = f"LPROP-{uuid.uuid4()}"
        body = {
            "proposal_id": proposal_id,
            **binding,
            "explanation": explanation,
            "matched_locks": matched_receipts,
            "state": "AWAITING_TRUSTED_USER_AUTHORIZATION",
            "created_at": utc_now(),
        }
        digest = sha256_json({key: value for key, value in body.items() if key != "state"})
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal_id,
                    normalized,
                    operation_value,
                    current_sha256,
                    proposed_sha256,
                    payload_sha256,
                    canonical_json(explanation),
                    canonical_json(matched_receipts),
                    digest,
                    body["state"],
                    body["created_at"],
                ),
            )
            event = self._event(
                connection,
                "LOCK_CHANGE_PROPOSED",
                {"proposal_id": proposal_id, "proposal_hash": digest},
            )
            connection.commit()
        return {
            **body,
            "proposal_hash": digest,
            "challenge": digest,
            "model_can_authorize": False,
            "trusted_user_gesture_required": True,
            "event": event,
        }

    @staticmethod
    def _proposal(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "proposal_id": str(row["proposal_id"]),
            "resource": str(row["resource"]),
            "operation": str(row["operation"]),
            "current_sha256": row["current_sha256"],
            "proposed_sha256": row["proposed_sha256"],
            "payload_sha256": str(row["payload_sha256"]),
            "explanation": json.loads(str(row["explanation_json"])),
            "matched_locks": json.loads(str(row["matched_locks_json"])),
            "proposal_hash": str(row["proposal_hash"]),
            "state": str(row["state"]),
            "created_at": str(row["created_at"]),
        }

    def pending_proposals(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM proposals WHERE state='AWAITING_TRUSTED_USER_AUTHORIZATION' "
                "ORDER BY created_at,proposal_id"
            ).fetchall()
        return [self._proposal(row) for row in rows]

    def trusted_authorize(
        self,
        proposal_id: str,
        *,
        actor: Actor,
        trusted_channel: str,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        self._require_user(actor)
        if trusted_channel not in TRUSTED_USER_CHANNELS:
            raise ConstitutionalAuthorityError("untrusted authorization channel")
        expiry = parse_time(expires_at)
        if expiry is not None and expiry <= datetime.now(UTC):
            raise ValueError("authorization expiry must be in the future")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            proposal = self._proposal(row)
            if proposal["state"] != "AWAITING_TRUSTED_USER_AUTHORIZATION":
                raise ValueError("proposal is not awaiting authorization")
            current_matches = self.matching_locks(
                proposal["resource"], proposal["operation"]
            )
            current_receipts = [
                {"lock_id": item["lock_id"], "lock_hash": item["lock_hash"]}
                for item in current_matches
            ]
            if current_receipts != proposal["matched_locks"]:
                raise ValueError("governing lock set changed; create a new proposal")
            authorization_id = f"LAUTH-{uuid.uuid4()}"
            lock_set_hash = sha256_json(current_receipts)
            issued_at = utc_now()
            connection.execute(
                "INSERT INTO authorizations VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    authorization_id,
                    proposal_id,
                    proposal["proposal_hash"],
                    lock_set_hash,
                    trusted_channel,
                    issued_at,
                    expires_at,
                    None,
                    None,
                ),
            )
            connection.execute(
                "UPDATE proposals SET state='AUTHORIZED_EXACT_ONE_SHOT' WHERE proposal_id=?",
                (proposal_id,),
            )
            event = self._event(
                connection,
                "LOCK_CHANGE_AUTHORIZED",
                {
                    "proposal_id": proposal_id,
                    "authorization_id": authorization_id,
                    "trusted_channel": trusted_channel,
                    "scope": "EXACT_ONE_SHOT",
                },
            )
            connection.commit()
        return {
            "schema": "kch.lock-exact-authorization.v0.1.0",
            "authorization_id": authorization_id,
            "proposal_id": proposal_id,
            "proposal_hash": proposal["proposal_hash"],
            "lock_set_hash": lock_set_hash,
            "trusted_channel": trusted_channel,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "scope": "EXACT_ONE_SHOT",
            "session_wide_authority_created": False,
            "event": event,
        }

    def authorization_status(self, proposal_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            proposal_row = connection.execute(
                "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if proposal_row is None:
                raise KeyError(proposal_id)
            authorization = connection.execute(
                "SELECT * FROM authorizations WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
        proposal = self._proposal(proposal_row)
        return {
            "schema": "kch.lock-authorization-status.v0.1.0",
            "proposal": proposal,
            "authorization": None
            if authorization is None
            else {
                "authorization_id": str(authorization["authorization_id"]),
                "trusted_channel": str(authorization["trusted_channel"]),
                "issued_at": str(authorization["issued_at"]),
                "expires_at": authorization["expires_at"],
                "consumed_at": authorization["consumed_at"],
                "consumed": authorization["consumed_at"] is not None,
            },
        }

    def _consume(
        self,
        authorization_id: str,
        *,
        binding: dict[str, Any],
        matched: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT a.*,p.* FROM authorizations a JOIN proposals p USING(proposal_id) "
                "WHERE a.authorization_id=?",
                (authorization_id,),
            ).fetchone()
            if row is None:
                raise PermissionError("unknown lock authorization")
            if row["consumed_at"] is not None:
                raise PermissionError("lock authorization is already consumed")
            expiry = parse_time(row["expires_at"])
            if expiry is not None and expiry <= datetime.now(UTC):
                raise PermissionError("lock authorization expired")
            proposal_binding = self._binding(
                resource=str(row["resource"]),
                operation=str(row["operation"]),
                current_sha256=row["current_sha256"],
                proposed_sha256=row["proposed_sha256"],
                payload_sha256=str(row["payload_sha256"]),
            )
            if proposal_binding != binding:
                raise PermissionError("mutation differs from the exact authorized proposal")
            matched_receipts = [
                {"lock_id": item["lock_id"], "lock_hash": item["lock_hash"]}
                for item in matched
            ]
            if sha256_json(matched_receipts) != str(row["lock_set_hash"]):
                raise PermissionError("governing lock set differs from authorization")
            consumed_at = utc_now()
            consumption_hash = sha256_json(
                {
                    "authorization_id": authorization_id,
                    "proposal_hash": str(row["proposal_hash"]),
                    "binding": binding,
                    "consumed_at": consumed_at,
                }
            )
            connection.execute(
                "UPDATE authorizations SET consumed_at=?,consumption_hash=? "
                "WHERE authorization_id=?",
                (consumed_at, consumption_hash, authorization_id),
            )
            connection.execute(
                "UPDATE proposals SET state='AUTHORIZED_AND_CONSUMED' WHERE proposal_id=?",
                (str(row["proposal_id"]),),
            )
            event = self._event(
                connection,
                "LOCK_AUTHORIZATION_CONSUMED",
                {
                    "authorization_id": authorization_id,
                    "proposal_id": str(row["proposal_id"]),
                    "consumption_hash": consumption_hash,
                },
            )
            connection.commit()
        return {
            "schema": "kch.lock-preflight.v0.1.0",
            "gate": "ALLOW_EXACT_ONE_SHOT_AUTHORIZATION_CONSUMED",
            "authorized": True,
            "binding": binding,
            "matched_locks": matched,
            "authorization_id": authorization_id,
            "consumed_at": consumed_at,
            "consumption_hash": consumption_hash,
            "event": event,
        }

    def verify_drift(self) -> dict[str, Any]:
        checks = []
        for lock in self.locks():
            baseline = lock["baseline"]
            if not baseline.get("captured") or baseline.get("kind") != "FILE":
                continue
            path = Path(str(baseline["path"]))
            exists = path.is_file()
            observed = {
                "exists": exists,
                "bytes": path.stat().st_size if exists else None,
                "sha256": file_sha256(path) if exists else None,
            }
            expected = {
                "exists": bool(baseline["exists"]),
                "bytes": baseline["bytes"],
                "sha256": baseline["sha256"],
            }
            checks.append(
                {
                    "lock_id": lock["lock_id"],
                    "resource": lock["resource_pattern"],
                    "expected": expected,
                    "observed": observed,
                    "match": expected == observed,
                }
            )
        return {
            "schema": "kch.lock-drift-verification.v0.1.0",
            "gate": "PASS_NO_DRIFT" if all(item["match"] for item in checks) else "FAIL_DRIFT_DETECTED",
            "checks": checks,
            "checked": len(checks),
            "external_change_prevention_claimed": False,
            "external_change_detection_supported": True,
        }

    def verify(self) -> dict[str, Any]:
        errors = []
        previous = "0" * 64
        event_count = 0
        with closing(self.connect()) as connection:
            for row in connection.execute("SELECT * FROM events ORDER BY seq"):
                payload = json.loads(str(row["payload_json"]))
                expected = sha256_json(
                    {
                        "timestamp": str(row["timestamp"]),
                        "event_type": str(row["event_type"]),
                        "payload": payload,
                        "previous_hash": previous,
                    }
                )
                if str(row["previous_hash"]) != previous or str(row["event_hash"]) != expected:
                    errors.append(f"event {row['seq']} hash-chain mismatch")
                previous = expected
                event_count += 1
            for row in connection.execute("SELECT * FROM locks ORDER BY created_at,lock_id"):
                lock = self._row_lock(row)
                body = {
                    key: value
                    for key, value in lock.items()
                    if key not in {"lock_hash", "active"}
                }
                if sha256_json(body) != lock["lock_hash"]:
                    errors.append(f"lock {lock['lock_id']} seal mismatch")
            for row in connection.execute("SELECT * FROM proposals ORDER BY created_at,proposal_id"):
                proposal = self._proposal(row)
                body = {
                    key: value
                    for key, value in proposal.items()
                    if key not in {"proposal_hash", "state"}
                }
                if sha256_json(body) != proposal["proposal_hash"]:
                    errors.append(f"proposal {proposal['proposal_id']} seal mismatch")
        return {
            "schema": "kch.lock-governor-integrity.v0.1.0",
            "gate": "PASS" if not errors else "FAIL",
            "event_count": event_count,
            "head_hash": previous,
            "errors": errors,
        }

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            counts = {
                "locks_active": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM locks WHERE active=1"
                    ).fetchone()[0]
                ),
                "locks_total": int(
                    connection.execute("SELECT COUNT(*) FROM locks").fetchone()[0]
                ),
                "proposals_pending": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM proposals WHERE "
                        "state='AWAITING_TRUSTED_USER_AUTHORIZATION'"
                    ).fetchone()[0]
                ),
                "authorizations_unconsumed": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM authorizations WHERE consumed_at IS NULL"
                    ).fetchone()[0]
                ),
            }
        return {
            "schema": "kch.lock-governor-status.v0.1.0",
            "enabled": self.enabled(),
            "default_enabled": False,
            **counts,
            "match_modes": sorted(MATCH_MODES),
            "trusted_user_channels": sorted(TRUSTED_USER_CHANNELS),
            "session_wide_unlock_supported": False,
            "model_can_enact_lock": False,
            "model_can_authorize_change": False,
            "exact_one_shot_authorization": True,
            "governed_surfaces": [
                "MCP_MUTATING_TOOLS",
                "PROACTIVE_LAUNCHER_MUTATING_TOOLS",
                "CONSTRUCT_CANDIDATE_FILES",
                "KCH_LOCAL_UI_ROUTED_MUTATIONS",
            ],
            "external_unmediated_writes_prevented": False,
            "external_exact_file_drift_detected": True,
            "integrity": self.verify(),
        }
