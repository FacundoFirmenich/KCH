from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import uuid4

from .contracts import canonical_json, sha256_json, validate_reviewable_decision


class IntegrationError(RuntimeError):
    pass


class ConflictError(IntegrationError):
    pass


class RequestCollisionError(IntegrationError):
    pass


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class EffectiveIntegrationService:
    """Single-writer control plane over the existing KCH personal-learning schema."""

    def __init__(self, state_path: str | Path):
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, factory=_ClosingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _write_connection(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            yield connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    record_json TEXT NOT NULL,
                    record_hash TEXT NOT NULL,
                    registered_event_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    initiator TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    state TEXT NOT NULL,
                    exclusive INTEGER NOT NULL,
                    decision_id TEXT,
                    started_at TEXT NOT NULL,
                    closed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS training_packets (
                    packet_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    packet_json TEXT NOT NULL,
                    packet_hash TEXT NOT NULL,
                    activation_state TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS integration_requests (
                    request_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    client_instance_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    receipt_sha256 TEXT NOT NULL,
                    resulting_head_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mutability_catalog (
                    service_id TEXT NOT NULL,
                    method TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    PRIMARY KEY(service_id, method)
                );
                CREATE TABLE IF NOT EXISTS emitter_inventory (
                    component_id TEXT PRIMARY KEY,
                    registry_name TEXT NOT NULL,
                    inventory_state TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _head(connection: sqlite3.Connection) -> str:
        row = connection.execute("SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        return row[0] if row else "GENESIS"

    def head(self) -> str:
        with self._connect() as connection:
            return self._head(connection)

    @staticmethod
    def _append_event(connection: sqlite3.Connection, event_type: str, payload: dict[str, Any]) -> str:
        previous_hash = EffectiveIntegrationService._head(connection)
        body = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "occurred_at": _utc_now(),
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event_hash = sha256_json(body)
        connection.execute(
            "INSERT INTO events(event_id,event_type,occurred_at,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?)",
            (body["event_id"], event_type, body["occurred_at"], canonical_json(payload), previous_hash, event_hash),
        )
        return event_hash

    @staticmethod
    def _request_identity(client: dict[str, str], request_id: str, operation: str, payload: dict[str, Any]) -> tuple[str, str, str, str, str]:
        required = ("client_id", "client_instance_id")
        if any(not isinstance(client.get(field), str) or not client[field].strip() for field in required):
            raise IntegrationError("client_id and client_instance_id are required")
        if not isinstance(request_id, str) or not request_id.strip():
            raise IntegrationError("request_id is required")
        return client["client_id"], client["client_instance_id"], request_id, operation, sha256_json(payload)

    def _mutate(
        self,
        *,
        client: dict[str, str],
        request_id: str,
        expected_head_hash: str,
        operation: str,
        payload: dict[str, Any],
        handler: Callable[[sqlite3.Connection], dict[str, Any]],
    ) -> dict[str, Any]:
        client_id, client_instance_id, request_id, operation, payload_hash = self._request_identity(client, request_id, operation, payload)
        with self._lock, self._write_connection() as connection:
            existing = connection.execute("SELECT * FROM integration_requests WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if (
                    existing["client_id"] != client_id
                    or existing["client_instance_id"] != client_instance_id
                    or existing["operation"] != operation
                    or existing["payload_sha256"] != payload_hash
                ):
                    raise RequestCollisionError("request_id collision with different identity or payload")
                receipt = json.loads(existing["receipt_json"])
                receipt["idempotent_replay"] = True
                return receipt
            observed_head = self._head(connection)
            if expected_head_hash != observed_head:
                raise ConflictError(f"STALE_EXPECTED_HEAD expected={expected_head_hash} observed={observed_head}")
            result = handler(connection)
            resulting_head = self._head(connection)
            receipt = {
                "schema": "kch.integration-write-receipt.v0.2.0",
                "request_id": request_id,
                "client_id": client_id,
                "client_instance_id": client_instance_id,
                "operation": operation,
                "payload_sha256": payload_hash,
                "previous_head_hash": observed_head,
                "resulting_head_hash": resulting_head,
                "result": result,
                "idempotent_replay": False,
            }
            receipt_json = canonical_json(receipt)
            connection.execute(
                "INSERT INTO integration_requests(request_id,client_id,client_instance_id,operation,payload_sha256,receipt_json,receipt_sha256,resulting_head_hash) VALUES(?,?,?,?,?,?,?,?)",
                (request_id, client_id, client_instance_id, operation, payload_hash, receipt_json, _sha_text(receipt_json), resulting_head),
            )
            return receipt

    def register_decision(
        self,
        record: dict[str, Any],
        *,
        client: dict[str, str],
        request_id: str,
        expected_head_hash: str,
    ) -> dict[str, Any]:
        validated = validate_reviewable_decision(record)

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            decision_id = validated["record"]["decision_id"]
            existing = connection.execute("SELECT record_hash FROM decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if existing:
                if existing[0] != validated["record_sha256"]:
                    raise ConflictError("decision_id collision with different content")
                return {
                    "decision_id": decision_id,
                    "record_sha256": validated["record_sha256"],
                    "decision_idempotent": True,
                    "contract_state": validated["contract_state"],
                    "unavailable_fields": validated["unavailable_fields"],
                }
            event_hash = self._append_event(
                connection,
                "DECISION_REGISTERED",
                {
                    "decision_id": decision_id,
                    "record_hash": validated["record_sha256"],
                    "contract_state": validated["contract_state"],
                },
            )
            connection.execute(
                "INSERT INTO decisions(decision_id,record_json,record_hash,registered_event_hash) VALUES(?,?,?,?)",
                (decision_id, canonical_json(validated["record"]), validated["record_sha256"], event_hash),
            )
            return {
                "decision_id": decision_id,
                "record_sha256": validated["record_sha256"],
                "decision_idempotent": False,
                "contract_state": validated["contract_state"],
                "unavailable_fields": validated["unavailable_fields"],
            }

        return self._mutate(
            client=client,
            request_id=request_id,
            expected_head_hash=expected_head_hash,
            operation="REGISTER_REVIEWABLE_DECISION",
            payload=record,
            handler=handler,
        )

    def start_phl(self, *, client: dict[str, str], request_id: str, expected_head_hash: str, trigger: str) -> dict[str, Any]:
        payload = {"trigger": trigger}

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            active = connection.execute("SELECT session_id FROM sessions WHERE channel='PHL' AND state='ACTIVE' LIMIT 1").fetchone()
            if active:
                raise ConflictError(f"PHL_ALREADY_ACTIVE:{active[0]}")
            session_id = str(uuid4())
            started_at = _utc_now()
            event_hash = self._append_event(
                connection,
                "LEARNING_SESSION_STARTED",
                {
                    "session_id": session_id,
                    "channel": "PHL",
                    "initiator": client["client_id"],
                    "trigger": trigger,
                    "exclusive": True,
                    "decision_id": None,
                },
            )
            connection.execute(
                "INSERT INTO sessions(session_id,channel,initiator,trigger,state,exclusive,decision_id,started_at) VALUES(?,?,?,?,?,?,?,?)",
                (session_id, "PHL", client["client_id"], trigger, "ACTIVE", 1, None, started_at),
            )
            return {"session_id": session_id, "state": "ACTIVE", "exclusive": True, "event_hash": event_hash}

        return self._mutate(client=client, request_id=request_id, expected_head_hash=expected_head_hash, operation="START_PHL", payload=payload, handler=handler)

    def close_phl(
        self,
        session_id: str,
        *,
        client: dict[str, str],
        request_id: str,
        expected_head_hash: str,
    ) -> dict[str, Any]:
        payload = {"session_id": session_id}

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            row = connection.execute("SELECT channel,state FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if not row or row["channel"] != "PHL":
                raise IntegrationError("unknown PHL session")
            if row["state"] == "CLOSED":
                return {"session_id": session_id, "state": "CLOSED", "session_idempotent": True}
            event_hash = self._append_event(connection, "LEARNING_SESSION_CLOSED", {"session_id": session_id})
            connection.execute("UPDATE sessions SET state='CLOSED',closed_at=? WHERE session_id=?", (_utc_now(), session_id))
            return {"session_id": session_id, "state": "CLOSED", "session_idempotent": False, "event_hash": event_hash}

        return self._mutate(client=client, request_id=request_id, expected_head_hash=expected_head_hash, operation="CLOSE_PHL", payload=payload, handler=handler)

    def register_mutability(
        self,
        record: dict[str, str],
        *,
        client: dict[str, str],
        request_id: str,
        expected_head_hash: str,
    ) -> dict[str, Any]:
        required = {"service_id", "method", "classification", "evidence_ref"}
        if set(record) != required or record["classification"] not in {"READ_ONLY", "MUTATING"}:
            raise IntegrationError("invalid mutability record")

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            record_json = canonical_json(record)
            record_hash = _sha_text(record_json)
            existing = connection.execute("SELECT record_sha256 FROM mutability_catalog WHERE service_id=? AND method=?", (record["service_id"], record["method"])).fetchone()
            if existing:
                if existing[0] != record_hash:
                    raise ConflictError("mutability classification collision")
                return {**record, "record_sha256": record_hash, "catalog_idempotent": True}
            event_hash = self._append_event(connection, "MUTABILITY_METHOD_CLASSIFIED", {**record, "record_sha256": record_hash})
            connection.execute(
                "INSERT INTO mutability_catalog(service_id,method,classification,evidence_ref,record_json,record_sha256,event_hash) VALUES(?,?,?,?,?,?,?)",
                (record["service_id"], record["method"], record["classification"], record["evidence_ref"], record_json, record_hash, event_hash),
            )
            return {**record, "record_sha256": record_hash, "catalog_idempotent": False}

        return self._mutate(client=client, request_id=request_id, expected_head_hash=expected_head_hash, operation="REGISTER_MUTABILITY", payload=record, handler=handler)

    def register_emitter(
        self,
        record: dict[str, str],
        *,
        client: dict[str, str],
        request_id: str,
        expected_head_hash: str,
    ) -> dict[str, Any]:
        required = {"component_id", "registry_name", "inventory_state", "evidence_ref"}
        states = {"DECISION_EMITTER", "NON_DECISION_SERVICE", "UNAVAILABLE_CONTRACT"}
        if set(record) != required or record["inventory_state"] not in states:
            raise IntegrationError("invalid emitter inventory record")

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            record_json = canonical_json(record)
            record_hash = _sha_text(record_json)
            existing = connection.execute("SELECT record_sha256 FROM emitter_inventory WHERE component_id=?", (record["component_id"],)).fetchone()
            if existing:
                if existing[0] != record_hash:
                    raise ConflictError("emitter inventory collision")
                return {**record, "record_sha256": record_hash, "inventory_idempotent": True}
            event_hash = self._append_event(connection, "EMITTER_INVENTORY_ADJUDICATED", {**record, "record_sha256": record_hash})
            connection.execute(
                "INSERT INTO emitter_inventory(component_id,registry_name,inventory_state,evidence_ref,record_json,record_sha256,event_hash) VALUES(?,?,?,?,?,?,?)",
                (record["component_id"], record["registry_name"], record["inventory_state"], record["evidence_ref"], record_json, record_hash, event_hash),
            )
            return {**record, "record_sha256": record_hash, "inventory_idempotent": False}

        return self._mutate(client=client, request_id=request_id, expected_head_hash=expected_head_hash, operation="REGISTER_EMITTER", payload=record, handler=handler)

    def dispatch(
        self,
        service_id: str,
        method: str,
        payload: dict[str, Any],
        executor: Callable[[], Any],
        *,
        client: dict[str, str],
        request_id: str,
        expected_head_hash: str,
    ) -> dict[str, Any]:
        request_payload = {"service_id": service_id, "method": method, "payload_sha256": sha256_json(payload)}

        def handler(connection: sqlite3.Connection) -> dict[str, Any]:
            catalog = connection.execute("SELECT classification FROM mutability_catalog WHERE service_id=? AND method=?", (service_id, method)).fetchone()
            if not catalog:
                event_hash = self._append_event(connection, "ROUTE_BLOCKED_UNCLASSIFIED", request_payload)
                return {"allowed": False, "executed": False, "reason": "UNCLASSIFIED_METHOD_FAIL_CLOSED", "event_hash": event_hash}
            classification = catalog[0]
            active = connection.execute("SELECT session_id FROM sessions WHERE channel='PHL' AND state='ACTIVE' LIMIT 1").fetchone()
            if classification == "MUTATING" and active:
                event_hash = self._append_event(connection, "ROUTE_BLOCKED_PHL", {**request_payload, "active_phl_session_id": active[0]})
                return {"allowed": False, "executed": False, "reason": "PHL_EXCLUSIVE_LOCK", "event_hash": event_hash}
            result = executor()
            event_hash = self._append_event(connection, "ROUTE_EXECUTED", {**request_payload, "classification": classification})
            return {"allowed": True, "executed": True, "classification": classification, "executor_result": result, "event_hash": event_hash}

        return self._mutate(client=client, request_id=request_id, expected_head_hash=expected_head_hash, operation=f"DISPATCH:{service_id}.{method}", payload=request_payload, handler=handler)

    def projection(self) -> dict[str, Any]:
        with self._connect() as connection:
            count = lambda table: connection.execute(f"SELECT COUNT(1) FROM {table}").fetchone()[0]
            active = connection.execute("SELECT session_id FROM sessions WHERE channel='PHL' AND state='ACTIVE' LIMIT 1").fetchone()
            emitter_counts = {row[0]: row[1] for row in connection.execute("SELECT inventory_state,COUNT(1) FROM emitter_inventory GROUP BY inventory_state")}
            return {
                "head_hash": self._head(connection),
                "events": count("events"),
                "decisions": count("decisions"),
                "feedback": count("feedback"),
                "requests": count("integration_requests"),
                "mutability_methods": count("mutability_catalog"),
                "emitters": count("emitter_inventory"),
                "emitter_states": emitter_counts,
                "active_phl_session_id": active[0] if active else None,
            }

    def compare_peer_head(self, peer_head_hash: str) -> dict[str, Any]:
        local = self.head()
        return {"local_head_hash": local, "peer_head_hash": peer_head_hash, "exact": local == peer_head_hash, "state": "IN_SYNC" if local == peer_head_hash else "DIVERGENT_LEDGER_COPY_DETECTED"}

    def gate_state(self, expected_admitted_rows: int = 16) -> dict[str, Any]:
        projection = self.projection()
        states = projection["emitter_states"]
        inventoried = projection["emitters"]
        unavailable = states.get("UNAVAILABLE_CONTRACT", 0)
        if inventoried < expected_admitted_rows:
            state = "NOT_ESTIMABLE_EMITTER_INVENTORY_INCOMPLETE"
        elif unavailable:
            state = "PASS_EFFECTIVE_KCH_PHL_INTEGRATION_BOUNDED"
        else:
            state = "PASS_EFFECTIVE_KCH_PHL_INTEGRATION_FULL"
        return {"state": state, "expected_admitted_rows": expected_admitted_rows, **projection}

    def verify(self) -> dict[str, Any]:
        defects: list[str] = []
        previous = "GENESIS"
        with self._connect() as connection:
            events = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
            decisions = connection.execute("SELECT * FROM decisions ORDER BY decision_id").fetchall()
            feedback = connection.execute("SELECT * FROM feedback ORDER BY rowid").fetchall()
            requests = connection.execute("SELECT * FROM integration_requests ORDER BY rowid").fetchall()
            catalogs = connection.execute("SELECT * FROM mutability_catalog ORDER BY service_id,method").fetchall()
            emitters = connection.execute("SELECT * FROM emitter_inventory ORDER BY component_id").fetchall()
            event_hashes = {row["event_hash"] for row in events}
        for row in events:
            body = {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "occurred_at": row["occurred_at"],
                "payload": json.loads(row["payload_json"]),
                "previous_hash": row["previous_hash"],
            }
            if row["previous_hash"] != previous or sha256_json(body) != row["event_hash"]:
                defects.append(f"EVENT_CHAIN:{row['sequence']}")
            previous = row["event_hash"]
        for row in decisions:
            if _sha_text(row["record_json"]) != row["record_hash"] or row["registered_event_hash"] not in event_hashes:
                defects.append(f"DECISION_PROJECTION:{row['decision_id']}")
        for row in feedback:
            if _sha_text(row["record_json"]) != row["record_hash"] or row["event_hash"] not in event_hashes:
                defects.append(f"FEEDBACK_PROJECTION:{row['feedback_id']}")
        for row in requests:
            if _sha_text(row["receipt_json"]) != row["receipt_sha256"] or row["resulting_head_hash"] not in event_hashes:
                defects.append(f"REQUEST_PROJECTION:{row['request_id']}")
        for label, rows in (("MUTABILITY", catalogs), ("EMITTER", emitters)):
            for row in rows:
                key = row["method"] if label == "MUTABILITY" else row["component_id"]
                if _sha_text(row["record_json"]) != row["record_sha256"] or row["event_hash"] not in event_hashes:
                    defects.append(f"{label}_PROJECTION:{key}")
        return {
            "gate": "PASS" if not defects else "FAIL",
            "defects": defects,
            "head_hash": previous,
            "event_count": len(events),
            "decision_count": len(decisions),
            "feedback_count": len(feedback),
            "request_count": len(requests),
            "mutability_count": len(catalogs),
            "emitter_count": len(emitters),
        }

