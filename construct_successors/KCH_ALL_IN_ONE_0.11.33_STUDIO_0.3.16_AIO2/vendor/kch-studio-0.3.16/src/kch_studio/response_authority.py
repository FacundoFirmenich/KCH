from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ResponseAuthorityGovernor:
    """Fail-closed response preflight against user-authorized semantic contracts.

    The governor does not infer emotion, intent or medical state.  It evaluates
    only explicit constraints, structured response assertions and registered
    execution commitments.  A PASS is a local contract check, never proof that
    the prose is scientifically correct or that a host actually intercepted it.
    """

    SCHEMA = "kch.response-authority-governor.v0.1.0"
    OPERATORS = {"EQ", "IN", "NOT_IN", "ABSENT_TEXT", "PRESENT_TEXT"}
    DIMENSIONS = {
        "MISSION",
        "TERMINOLOGY",
        "PROVENANCE",
        "JURISDICTION",
        "EXPERIMENT_BOUNDARY",
        "REJECTED_FRAME",
        "RESPONSE_CONDUCT",
    }

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "response_authority.sqlite3"
        with self.connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS constraints(
                    constraint_id TEXT PRIMARY KEY,
                    dimension TEXT NOT NULL,
                    key TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    expected_json TEXT NOT NULL,
                    authority_source TEXT NOT NULL,
                    mandatory INTEGER NOT NULL,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                """
            )

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db, timeout=20)
        con.row_factory = sqlite3.Row
        return con

    def _append(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = f"RAG-{uuid.uuid4()}"
        occurred_at = _now()
        with self.connect() as con:
            row = con.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            previous_hash = "GENESIS" if row is None else str(row[0])
            body = {
                "schema": self.SCHEMA,
                "event_id": event_id,
                "kind": kind,
                "occurred_at": occurred_at,
                "payload": payload,
                "previous_hash": previous_hash,
            }
            event_hash = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
            con.execute(
                "INSERT INTO events(event_id,kind,occurred_at,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?)",
                (event_id, kind, occurred_at, _canonical(payload), previous_hash, event_hash),
            )
        return {**body, "event_hash": event_hash}

    def register(self, constraint: dict[str, Any]) -> dict[str, Any]:
        dimension = str(constraint.get("dimension", "")).upper()
        operator = str(constraint.get("operator", "")).upper()
        key = str(constraint.get("key", "")).strip()
        source = str(constraint.get("authority_source", "")).strip()
        if dimension not in self.DIMENSIONS:
            raise ValueError(f"unsupported dimension: {dimension}")
        if operator not in self.OPERATORS:
            raise ValueError(f"unsupported operator: {operator}")
        if not key or not source or "expected" not in constraint:
            raise ValueError("key, expected and authority_source are required")
        constraint_id = str(constraint.get("constraint_id") or f"CONSTRAINT-{uuid.uuid4()}")
        record = {
            "constraint_id": constraint_id,
            "dimension": dimension,
            "key": key,
            "operator": operator,
            "expected": constraint["expected"],
            "authority_source": source,
            "mandatory": constraint.get("mandatory", True) is True,
            "active": True,
            "created_at": _now(),
        }
        with self.connect() as con:
            con.execute(
                "INSERT INTO constraints VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    constraint_id,
                    dimension,
                    key,
                    operator,
                    _canonical(record["expected"]),
                    source,
                    int(record["mandatory"]),
                    1,
                    record["created_at"],
                ),
            )
        event = self._append("CONSTRAINT_REGISTERED", record)
        return {"constraint": record, "custody_event": event}

    def active_constraints(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM constraints WHERE active=1 ORDER BY created_at,constraint_id"
            ).fetchall()
        return [
            {
                "constraint_id": row["constraint_id"],
                "dimension": row["dimension"],
                "key": row["key"],
                "operator": row["operator"],
                "expected": json.loads(row["expected_json"]),
                "authority_source": row["authority_source"],
                "mandatory": bool(row["mandatory"]),
            }
            for row in rows
        ]

    @staticmethod
    def _assertion_index(candidate: dict[str, Any]) -> dict[tuple[str, str], list[Any]]:
        index: dict[tuple[str, str], list[Any]] = {}
        for assertion in candidate.get("assertions", []):
            dimension = str(assertion.get("dimension", "")).upper()
            key = str(assertion.get("key", ""))
            index.setdefault((dimension, key), []).append(assertion.get("value"))
        return index

    def adjudicate(
        self,
        candidate: dict[str, Any],
        *,
        active_commitment_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        text = str(candidate.get("text", ""))
        folded = text.casefold()
        assertions = self._assertion_index(candidate)
        failures: list[str] = []
        checks: dict[str, bool] = {}
        for constraint in self.active_constraints():
            cid = constraint["constraint_id"]
            operator = constraint["operator"]
            expected = constraint["expected"]
            observed = assertions.get((constraint["dimension"], constraint["key"]), [])
            passed = False
            if operator == "ABSENT_TEXT":
                phrases = expected if isinstance(expected, list) else [expected]
                passed = all(str(phrase).casefold() not in folded for phrase in phrases)
            elif operator == "PRESENT_TEXT":
                phrases = expected if isinstance(expected, list) else [expected]
                passed = all(str(phrase).casefold() in folded for phrase in phrases)
            elif observed:
                if operator == "EQ":
                    passed = all(value == expected for value in observed)
                elif operator == "IN":
                    passed = all(value in expected for value in observed)
                elif operator == "NOT_IN":
                    passed = all(value not in expected for value in observed)
            elif not constraint["mandatory"]:
                passed = True
            checks[cid] = passed
            if not passed:
                failures.append(f"CONSTRAINT_FAILED:{cid}")

        for claim in candidate.get("claims", []):
            if claim.get("combines_experiments") is True and claim.get("separation_declared") is not True:
                failures.append("EXPERIMENT_BOUNDARIES_CONFLATED")
            if claim.get("scope_promoted") is True and claim.get("explicit_scope_authority") is not True:
                failures.append("JURISDICTION_PROMOTED_WITHOUT_AUTHORITY")
            if claim.get("provenance_declared") is not True:
                failures.append("CLAIM_PROVENANCE_UNDECLARED")

        if candidate.get("off_mission_classification") is True and candidate.get("explicit_mission_relevance") is not True:
            failures.append("OFF_MISSION_CLASSIFICATION_DERAILMENT")

        active = set(active_commitment_ids or [])
        for promise in candidate.get("promises", []):
            if str(promise.get("kind", "")).upper() == "MONITOR_PROCESS":
                commitment_id = str(promise.get("commitment_id", ""))
                if not commitment_id or commitment_id not in active:
                    failures.append("MONITORING_PROMISE_WITHOUT_ACTIVE_COMMITMENT")

        result = {
            "schema": "kch.response-authority-adjudication.v0.1.0",
            "gate": "PASS" if not failures else "BLOCK",
            "release_authorized": not failures,
            "failures": sorted(set(failures)),
            "constraint_checks": checks,
            "active_constraint_count": len(checks),
            "candidate": candidate,
            "active_commitment_ids": sorted(active),
            "claim_ceiling": "STRUCTURED_LOCAL_RESPONSE_PREFLIGHT_ONLY_NOT_SEMANTIC_TRUTH_NOT_HOST_INTERPOSITION",
        }
        event = self._append("RESPONSE_ADJUDICATED", result)
        return {**result, "custody_event": event}

    def verify(self) -> dict[str, Any]:
        previous = "GENESIS"
        count = 0
        with self.connect() as con:
            rows = con.execute("SELECT * FROM events ORDER BY seq").fetchall()
        for row in rows:
            body = {
                "schema": self.SCHEMA,
                "event_id": row["event_id"],
                "kind": row["kind"],
                "occurred_at": row["occurred_at"],
                "payload": json.loads(row["payload_json"]),
                "previous_hash": previous,
            }
            digest = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous or digest != row["event_hash"]:
                return {"gate": "FAIL", "verified_events": count, "failed_event_id": row["event_id"]}
            previous = row["event_hash"]
            count += 1
        return {"gate": "PASS", "verified_events": count, "head_hash": previous}

    def status(self) -> dict[str, Any]:
        constraints = self.active_constraints()
        return {
            "schema": self.SCHEMA,
            "active_constraint_count": len(constraints),
            "active_constraints": constraints,
            "integrity": self.verify(),
            "automatic_host_interposition_established": False,
            "claim_ceiling": "LOCAL_EXECUTABLE_STRUCTURED_GATE_ONLY",
        }
