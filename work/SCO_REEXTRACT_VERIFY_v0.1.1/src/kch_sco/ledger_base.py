from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import uuid4

from .models import (
    ContractError,
    canonical_json,
    sha256_json,
    validate_conflict,
    validate_edge,
    validate_node,
    validate_receipt,
    validate_superchat,
    validate_work_order,
)


class SCOError(RuntimeError):
    pass


class SCOConflictError(SCOError):
    pass


class _Connection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SCOService:
    """Append-only orchestration plane; native chat content and memory stay outside."""

    def __init__(self, state_path: str | Path):
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, factory=_Connection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
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
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS commands (
                    command_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    receipt_sha256 TEXT NOT NULL,
                    resulting_head_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS superchats (
                    sco_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    sco_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    native_uri TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    UNIQUE(sco_id, native_uri),
                    FOREIGN KEY(sco_id) REFERENCES superchats(sco_id)
                );
                CREATE TABLE IF NOT EXISTS edges (
                    edge_id TEXT PRIMARY KEY,
                    sco_id TEXT NOT NULL,
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    FOREIGN KEY(sco_id) REFERENCES superchats(sco_id)
                );
                CREATE TABLE IF NOT EXISTS work_orders (
                    order_id TEXT PRIMARY KEY,
                    sco_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    FOREIGN KEY(sco_id) REFERENCES superchats(sco_id)
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL UNIQUE,
                    node_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES work_orders(order_id)
                );
                CREATE TABLE IF NOT EXISTS conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    sco_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    FOREIGN KEY(sco_id) REFERENCES superchats(sco_id)
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
    def _event(connection: sqlite3.Connection, event_type: str, actor: str, payload: dict[str, Any]) -> str:
        previous = SCOService._head(connection)
        body = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "occurred_at": _now(),
            "actor": actor,
            "payload": payload,
            "previous_hash": previous,
        }
        event_hash = sha256_json(body)
        connection.execute(
            "INSERT INTO events(event_id,event_type,occurred_at,actor,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)",
            (body["event_id"], event_type, body["occurred_at"], actor, canonical_json(payload), previous, event_hash),
        )
        return event_hash

    def _mutate(
        self,
        *,
        actor: str,
        command_id: str,
        expected_head_hash: str,
        operation: str,
        payload: dict[str, Any],
        handler: Callable[[sqlite3.Connection], dict[str, Any]],
    ) -> dict[str, Any]:
        if not actor.strip() or not command_id.strip():
            raise SCOError("actor and command_id are required")
        payload_hash = sha256_json(payload)
        with self._lock, self._transaction() as connection:
            existing = connection.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()
            if existing:
                if existing["actor"] != actor or existing["operation"] != operation or existing["payload_sha256"] != payload_hash:
                    raise SCOConflictError("command_id collision")
                receipt = json.loads(existing["receipt_json"])
                receipt["idempotent_replay"] = True
                return receipt
            observed = self._head(connection)
            if expected_head_hash != observed:
                raise SCOConflictError(f"STALE_EXPECTED_HEAD expected={expected_head_hash} observed={observed}")
            result = handler(connection)
            resulting = self._head(connection)
            receipt = {
                "schema": "kch.sco.command-receipt.v0.1.0",
                "command_id": command_id,
                "actor": actor,
                "operation": operation,
                "payload_sha256": payload_hash,
                "previous_head_hash": observed,
                "resulting_head_hash": resulting,
                "result": result,
                "idempotent_replay": False,
            }
            receipt_json = canonical_json(receipt)
            connection.execute(
                "INSERT INTO commands(command_id,actor,operation,payload_sha256,receipt_json,receipt_sha256,resulting_head_hash) VALUES(?,?,?,?,?,?,?)",
                (command_id, actor, operation, payload_hash, receipt_json, _sha_text(receipt_json), resulting),
            )
            return receipt

    @staticmethod
    def _projection_insert(connection, table: str, identity: str, record: dict[str, Any], event_hash: str, extra: tuple[Any, ...], columns: str) -> None:
        record_json = canonical_json(record)
        record_hash = _sha_text(record_json)
        placeholders = ",".join("?" for _ in range(5 + len(extra)))
        connection.execute(
            f"INSERT INTO {table}({columns},record_json,record_sha256,event_hash) VALUES({placeholders})",
            (identity, *extra, record_json, record_hash, event_hash),
        )

    @staticmethod
    def _require_sco(connection: sqlite3.Connection, sco_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM superchats WHERE sco_id=?", (sco_id,)).fetchone()
        if not row:
            raise SCOError("unknown sco_id")
        return row

    @staticmethod
    def _node(connection: sqlite3.Connection, node_id: str, sco_id: str | None = None) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM nodes WHERE node_id=?", (node_id,)).fetchone()
        if not row or (sco_id is not None and row["sco_id"] != sco_id):
            raise SCOError("unknown node or cross-SCO reference")
        return row

    def create_superchat(self, record: dict[str, Any], *, actor: str, command_id: str, expected_head_hash: str) -> dict[str, Any]:
        value = validate_superchat(record)

        def handler(connection):
            if connection.execute("SELECT 1 FROM superchats WHERE sco_id=?", (value["sco_id"],)).fetchone():
                raise SCOConflictError("sco_id already exists")
            event_hash = self._event(connection, "SUPERCHAT_CREATED", actor, {"sco_id": value["sco_id"], "record_sha256": sha256_json(value)})
            self._projection_insert(connection, "superchats", value["sco_id"], value, event_hash, ("ACTIVE",), "sco_id,state")
            return {"sco_id": value["sco_id"], "state": "ACTIVE", "event_hash": event_hash}

        return self._mutate(actor=actor, command_id=command_id, expected_head_hash=expected_head_hash, operation="CREATE_SUPERCHAT", payload=value, handler=handler)

    def add_node(self, record: dict[str, Any], *, actor: str, command_id: str, expected_head_hash: str) -> dict[str, Any]:
        value = validate_node(record)

        def handler(connection):
            self._require_sco(connection, value["sco_id"])
            if connection.execute("SELECT 1 FROM nodes WHERE node_id=?", (value["node_id"],)).fetchone():
                raise SCOConflictError("node_id already exists")
            if connection.execute("SELECT 1 FROM nodes WHERE sco_id=? AND native_uri=?", (value["sco_id"], value["native_uri"])).fetchone():
                raise SCOConflictError("native chat is already selected in this SCO")
            event_hash = self._event(connection, "SOVEREIGN_NODE_SELECTED", actor, {"sco_id": value["sco_id"], "node_id": value["node_id"], "provider": value["provider"], "native_uri": value["native_uri"], "record_sha256": sha256_json(value)})
            self._projection_insert(connection, "nodes", value["node_id"], value, event_hash, (value["sco_id"], value["provider"], value["native_uri"], value["role"], "ACTIVE"), "node_id,sco_id,provider,native_uri,role,status")
            return {"node_id": value["node_id"], "native_uri": value["native_uri"], "status": "ACTIVE", "event_hash": event_hash}

        return self._mutate(actor=actor, command_id=command_id, expected_head_hash=expected_head_hash, operation="ADD_NODE", payload=value, handler=handler)

    def retire_node(self, sco_id: str, node_id: str, *, actor: str, command_id: str, expected_head_hash: str) -> dict[str, Any]:
        payload = {"sco_id": sco_id, "node_id": node_id}

        def handler(connection):
            node = self._node(connection, node_id, sco_id)
            if node["status"] == "RETIRED_PRESERVED":
                return {"node_id": node_id, "status": "RETIRED_PRESERVED", "node_idempotent": True}
            active_orders = connection.execute("SELECT COUNT(*) FROM work_orders WHERE target_node_id=? AND state IN ('READY','WAITING_DEPENDENCY')", (node_id,)).fetchone()[0]
            if active_orders:
                raise SCOConflictError("node has unresolved work orders")
            event_hash = self._event(connection, "NODE_RETIRED_PRESERVED", actor, payload)
            connection.execute("UPDATE nodes SET status='RETIRED_PRESERVED' WHERE node_id=?", (node_id,))
            return {"node_id": node_id, "status": "RETIRED_PRESERVED", "event_hash": event_hash}

        return self._mutate(actor=actor, command_id=command_id, expected_head_hash=expected_head_hash, operation="RETIRE_NODE", payload=payload, handler=handler)

    def add_edge(self, record: dict[str, Any], *, actor: str, command_id: str, expected_head_hash: str) -> dict[str, Any]:
        value = validate_edge(record)

        def handler(connection):
            self._require_sco(connection, value["sco_id"])
            self._node(connection, value["source_node_id"], value["sco_id"])
            self._node(connection, value["target_node_id"], value["sco_id"])
            if connection.execute("SELECT 1 FROM edges WHERE edge_id=?", (value["edge_id"],)).fetchone():
                raise SCOConflictError("edge_id already exists")
            event_hash = self._event(connection, "ORCHESTRATION_EDGE_ADDED", actor, {"sco_id": value["sco_id"], "edge_id": value["edge_id"], "relation": value["relation"], "record_sha256": sha256_json(value)})
            self._projection_insert(connection, "edges", value["edge_id"], value, event_hash, (value["sco_id"], value["source_node_id"], value["target_node_id"], value["relation"], "ACTIVE"), "edge_id,sco_id,source_node_id,target_node_id,relation,status")
            return {"edge_id": value["edge_id"], "status": "ACTIVE", "event_hash": event_hash}

        return self._mutate(actor=actor, command_id=command_id, expected_head_hash=expected_head_hash, operation="ADD_EDGE", payload=value, handler=handler)

    @staticmethod
    def _dependency_state(connection: sqlite3.Connection, dependencies: list[str], sco_id: str) -> str:
        if not dependencies:
            return "READY"
        states = []
        for order_id in dependencies:
            row = connection.execute("SELECT sco_id,state FROM work_orders WHERE order_id=?", (order_id,)).fetchone()
            if not row or row["sco_id"] != sco_id:
                raise SCOError("unknown dependency or cross-SCO dependency")
            states.append(row["state"])
        if any(state in {"FAILED_PRESERVED", "BLOCKED_PRESERVED", "ABSTAINED_PRESERVED", "BLOCKED_DEPENDENCY_ADVERSE"} for state in states):
            return "BLOCKED_DEPENDENCY_ADVERSE"
        return "READY" if all(state == "COMPLETED" for state in states) else "WAITING_DEPENDENCY"

    def issue_work_order(self, record: dict[str, Any], *, actor: str, command_id: str, expected_head_hash: str) -> dict[str, Any]:
        value = validate_work_order(record)

        def handler(connection):
            self._require_sco(connection, value["sco_id"])
            node = self._node(connection, value["target_node_id"], value["sco_id"])
            if node["status"] != "ACTIVE":
                raise SCOConflictError("target node is not active")
            node_record = json.loads(node["record_json"])
            if not set(value["authority_granted"]).issubset(node_record["authority_granted"]):
                raise SCOConflictError("work order exceeds node authority")
            for fragment in value["disclosed_fragments"]:
                self._node(connection, fragment["source_node_id"], value["sco_id"])
            if connection.execute("SELECT 1 FROM work_orders WHERE order_id=?", (value["order_id"],)).fetchone():
                raise SCOConflictError("order_id already exists")
            state = self._dependency_state(connection, value["depends_on"], value["sco_id"])
            event_hash = self._event(connection, "WORK_ORDER_ISSUED", actor, {"sco_id": value["sco_id"], "order_id": value["order_id"], "target_node_id": value["target_node_id"], "state": state, "record_sha256": sha256_json(value)})
            self._projection_insert(connection, "work_orders", value["order_id"], value, event_hash, (value["sco_id"], value["target_node_id"], state), "order_id,sco_id,target_node_id,state")
            return {"order_id": value["order_id"], "state": state, "event_hash": event_hash}

        return self._mutate(actor=actor, command_id=command_id, expected_head_hash=expected_head_hash, operation="ISSUE_WORK_ORDER", payload=value, handler=handler)

    @staticmethod
    def _refresh_waiting(connection: sqlite3.Connection) -> None:
        rows = connection.execute("SELECT order_id,sco_id,record_json,state FROM work_orders WHERE state IN ('WAITING_DEPENDENCY','BLOCKED_DEPENDENCY_ADVERSE')").fetchall()
        for row in rows:
            record = json.loads(row["record_json"])
            state = SCOService._dependency_state(connection, record["depends_on"], row["sco_id"])
            connection.execute("UPDATE work_orders SET state=? WHERE order_id=?", (state, row["order_id"]))

    def ingest_receipt(self, record: dict[str, Any], *, actor: str, command_id: str, expected_head_hash: str) -> dict[str, Any]:
        value = validate_receipt(record)

        def handler(connection):
            order = connection.execute("SELECT * FROM work_orders WHERE order_id=?", (value["order_id"],)).fetchone()
            if not order:
                raise SCOError("unknown order_id")
            if order["target_node_id"] != value["node_id"]:
                raise SCOConflictError("receipt node is not the work-order target")
            order_record = json.loads(order["record_json"])
            if not set(value["authority_exercised"]).issubset(order_record["authority_granted"]):
                raise SCOConflictError("receipt reports authority escalation")
            if connection.execute("SELECT 1 FROM receipts WHERE order_id=?", (value["order_id"],)).fetchone():
                raise SCOConflictError("work order already has a receipt")
            states = {
                "SUCCEEDED": "COMPLETED",
                "FAILED": "FAILED_PRESERVED",
                "BLOCKED": "BLOCKED_PRESERVED",
                "ABSTAINED": "ABSTAINED_PRESERVED",
            }
            order_state = states[value["outcome"]]
            event_hash = self._event(connection, "WORK_RECEIPT_INGESTED", actor, {"receipt_id": value["receipt_id"], "order_id": value["order_id"], "outcome": value["outcome"], "record_sha256": sha256_json(value)})
            self._projection_insert(connection, "receipts", value["receipt_id"], value, event_hash, (value["order_id"], value["node_id"], value["outcome"]), "receipt_id,order_id,node_id,outcome")
            connection.execute("UPDATE work_orders SET state=? WHERE order_id=?", (order_state, value["order_id"]))
            self._refresh_waiting(connection)
            return {"receipt_id": value["receipt_id"], "order_id": value["order_id"], "order_state": order_state, "adverse_preserved": value["outcome"] != "SUCCEEDED", "event_hash": event_hash}

        return self._mutate(actor=actor, command_id=command_id, expected_head_hash=expected_head_hash, operation="INGEST_RECEIPT", payload=value, handler=handler)

    def declare_conflict(self, record: dict[str, Any], *, actor: str, command_id: str, expected_head_hash: str) -> dict[str, Any]:
        value = validate_conflict(record)

        def handler(connection):
            self._require_sco(connection, value["sco_id"])
            for receipt_id in value["receipt_ids"]:
                row = connection.execute("SELECT w.sco_id FROM receipts r JOIN work_orders w ON w.order_id=r.order_id WHERE r.receipt_id=?", (receipt_id,)).fetchone()
                if not row or row["sco_id"] != value["sco_id"]:
                    raise SCOError("unknown receipt or cross-SCO conflict")
            if value["adjudicator_node_id"] != "UNASSIGNED":
                adjudicator = self._node(connection, value["adjudicator_node_id"], value["sco_id"])
                authority = json.loads(adjudicator["record_json"])["authority_granted"]
                if "ADJUDICATE_CONFLICT" not in authority:
                    raise SCOConflictError("designated node lacks ADJUDICATE_CONFLICT authority")
            if connection.execute("SELECT 1 FROM conflicts WHERE conflict_id=?", (value["conflict_id"],)).fetchone():
                raise SCOConflictError("conflict_id already exists")
            event_hash = self._event(connection, "CONFLICT_PRESERVED", actor, {"sco_id": value["sco_id"], "conflict_id": value["conflict_id"], "state": value["state"], "record_sha256": sha256_json(value)})
            self._projection_insert(connection, "conflicts", value["conflict_id"], value, event_hash, (value["sco_id"], value["state"]), "conflict_id,sco_id,state")
            return {"conflict_id": value["conflict_id"], "state": value["state"], "divergence_preserved": True, "event_hash": event_hash}

        return self._mutate(actor=actor, command_id=command_id, expected_head_hash=expected_head_hash, operation="DECLARE_CONFLICT", payload=value, handler=handler)

    def schedule(self, sco_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            self._require_sco(connection, sco_id)
            rows = connection.execute("SELECT order_id,target_node_id,state,record_json FROM work_orders WHERE sco_id=? ORDER BY rowid", (sco_id,)).fetchall()
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            buckets.setdefault(row["state"], []).append({"order_id": row["order_id"], "target_node_id": row["target_node_id"], "objective": json.loads(row["record_json"])["objective"]})
        return {"schema": "kch.sco.schedule.v0.1.0", "sco_id": sco_id, "states": buckets, "ready_count": len(buckets.get("READY", []))}

    def graph_diagnostics(self, sco_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            self._require_sco(connection, sco_id)
            nodes = [row[0] for row in connection.execute("SELECT node_id FROM nodes WHERE sco_id=? AND status='ACTIVE'", (sco_id,))]
            edges = [(row[0], row[1], row[2]) for row in connection.execute("SELECT source_node_id,target_node_id,relation FROM edges WHERE sco_id=? AND status='ACTIVE'", (sco_id,))]
        adjacency = {node: [] for node in nodes}
        for source, target, _ in edges:
            adjacency.setdefault(source, []).append(target)
        visiting: set[str] = set()
        visited: set[str] = set()
        cycles: set[tuple[str, ...]] = set()

        def walk(node: str, path: list[str]) -> None:
            if node in visiting:
                start = path.index(node)
                cycles.add(tuple(path[start:] + [node]))
                return
            if node in visited:
                return
            visiting.add(node)
            for target in adjacency.get(node, []):
                walk(target, path + [target])
            visiting.remove(node)
            visited.add(node)

        for node in nodes:
            walk(node, [node])
        return {"schema": "kch.sco.graph-diagnostics.v0.1.0", "sco_id": sco_id, "active_nodes": len(nodes), "active_edges": len(edges), "cycles": [list(item) for item in sorted(cycles)], "cycle_policy": "PRESERVED_AND_VISIBLE_NOT_SILENTLY_FLATTENED"}

    def projection(self, sco_id: str | None = None) -> dict[str, Any]:
        where = " WHERE sco_id=?" if sco_id else ""
        args = (sco_id,) if sco_id else ()
        with self._connect() as connection:
            if sco_id:
                self._require_sco(connection, sco_id)
            counts = {
                "superchats": connection.execute("SELECT COUNT(*) FROM superchats" + (" WHERE sco_id=?" if sco_id else ""), args).fetchone()[0],
                "nodes": connection.execute("SELECT COUNT(*) FROM nodes" + where, args).fetchone()[0],
                "edges": connection.execute("SELECT COUNT(*) FROM edges" + where, args).fetchone()[0],
                "work_orders": connection.execute("SELECT COUNT(*) FROM work_orders" + where, args).fetchone()[0],
                "conflicts": connection.execute("SELECT COUNT(*) FROM conflicts" + where, args).fetchone()[0],
            }
            if sco_id:
                receipts = connection.execute("SELECT COUNT(*) FROM receipts r JOIN work_orders w ON w.order_id=r.order_id WHERE w.sco_id=?", args).fetchone()[0]
            else:
                receipts = connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
            provider_states = {row[0]: row[1] for row in connection.execute("SELECT provider,COUNT(*) FROM nodes" + where + " GROUP BY provider", args)}
            order_states = {row[0]: row[1] for row in connection.execute("SELECT state,COUNT(*) FROM work_orders" + where + " GROUP BY state", args)}
            event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            command_count = connection.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
            head = self._head(connection)
        return {"schema": "kch.sco.projection.v0.1.0", "sco_id": sco_id or "ALL", **counts, "receipts": receipts, "provider_counts": provider_states, "order_states": order_states, "events": event_count, "commands": command_count, "head_hash": head, "native_contexts_merged": False}

    def export_bundle(self, sco_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            sco = self._require_sco(connection, sco_id)
            def records(table: str) -> list[dict[str, Any]]:
                return [json.loads(row[0]) for row in connection.execute(f"SELECT record_json FROM {table} WHERE sco_id=? ORDER BY rowid", (sco_id,))]
            nodes = records("nodes")
            edges = records("edges")
            orders = records("work_orders")
            receipts = [json.loads(row[0]) for row in connection.execute("SELECT r.record_json FROM receipts r JOIN work_orders w ON w.order_id=r.order_id WHERE w.sco_id=? ORDER BY r.rowid", (sco_id,))]
            conflicts = records("conflicts")
            head = self._head(connection)
        body = {
            "schema": "kch.sco.portable-orchestration-bundle.v0.1.0",
            "superchat": json.loads(sco["record_json"]),
            "nodes": nodes,
            "edges": edges,
            "work_orders": orders,
            "receipts": receipts,
            "conflicts": conflicts,
            "ledger_head_hash": head,
            "native_chat_content_included": False,
            "native_memory_included": False,
            "authority_created": False,
        }
        body["bundle_sha256"] = sha256_json(body)
        return body

    def dispatch_envelopes(self, sco_id: str) -> list[dict[str, Any]]:
        schedule = self.schedule(sco_id)
        ready_ids = [item["order_id"] for item in schedule["states"].get("READY", [])]
        envelopes = []
        with self._connect() as connection:
            for order_id in ready_ids:
                row = connection.execute("SELECT w.record_json,n.provider,n.native_uri,n.record_json AS node_json FROM work_orders w JOIN nodes n ON n.node_id=w.target_node_id WHERE w.order_id=?", (order_id,)).fetchone()
                node = json.loads(row["node_json"])
                envelopes.append({
                    "schema": "kch.sco.dispatch-envelope.v0.1.0",
                    "provider": row["provider"],
                    "native_uri": row["native_uri"],
                    "connector_state": node["connector_state"],
                    "work_order": json.loads(row["record_json"]),
                    "automatic_dispatch_performed": False,
                    "dispatch_blocker": "HOST_BRIDGE_REQUIRED" if node["connector_state"] != "LIVE_READ_WRITE_VERIFIED" else "NONE",
                })
        return envelopes

    def verify(self) -> dict[str, Any]:
        defects: list[str] = []
        with self._connect() as connection:
            events = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
            event_hashes = {row["event_hash"] for row in events}
            commands = connection.execute("SELECT * FROM commands ORDER BY rowid").fetchall()
            tables = {name: connection.execute(f"SELECT * FROM {name} ORDER BY rowid").fetchall() for name in ("superchats", "nodes", "edges", "work_orders", "receipts", "conflicts")}
        previous = "GENESIS"
        for row in events:
            body = {"event_id": row["event_id"], "event_type": row["event_type"], "occurred_at": row["occurred_at"], "actor": row["actor"], "payload": json.loads(row["payload_json"]), "previous_hash": row["previous_hash"]}
            if row["previous_hash"] != previous or sha256_json(body) != row["event_hash"]:
                defects.append(f"EVENT_CHAIN:{row['sequence']}")
            previous = row["event_hash"]
        for row in commands:
            if _sha_text(row["receipt_json"]) != row["receipt_sha256"] or (row["resulting_head_hash"] not in event_hashes and row["resulting_head_hash"] != "GENESIS"):
                defects.append(f"COMMAND:{row['command_id']}")
        for table, rows in tables.items():
            for row in rows:
                identity_column = {"superchats": "sco_id", "nodes": "node_id", "edges": "edge_id", "work_orders": "order_id", "receipts": "receipt_id", "conflicts": "conflict_id"}[table]
                if _sha_text(row["record_json"]) != row["record_sha256"] or row["event_hash"] not in event_hashes:
                    defects.append(f"{table.upper()}:{row[identity_column]}")
        return {"schema": "kch.sco.integrity-result.v0.1.0", "gate": "PASS" if not defects else "FAIL", "defects": defects, "event_count": len(events), "command_count": len(commands), "head_hash": previous}
