from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .credal import ConditionedCredalSet
from .models import Instruction, LifecycleState


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS events(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS instructions(
    instruction_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    record_json TEXT NOT NULL,
    record_sha256 TEXT NOT NULL,
    current INTEGER NOT NULL,
    event_hash TEXT NOT NULL,
    PRIMARY KEY(instruction_id,revision)
);
CREATE UNIQUE INDEX IF NOT EXISTS instructions_one_current
ON instructions(instruction_id) WHERE current=1;
CREATE TABLE IF NOT EXISTS credal_profiles(
    profile_id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    profile_sha256 TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS commands(
    command_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    result_json TEXT NOT NULL,
    result_sha256 TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class InstructionEventStore:
    """One-database transactional event store and projections.

    Hashes make unauthorized edits detectable by ``verify``.  SQLite alone is
    not an immutable medium, so this class never claims physical append-only
    custody or external anchoring.
    """

    SCHEMA = "kch.ige.transactional-store.v0.3.0"

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.executescript(DDL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _head(connection: sqlite3.Connection) -> tuple[int, str]:
        row = connection.execute(
            "SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return (0, "GENESIS") if row is None else (int(row["sequence"]), str(row["event_hash"]))

    def _append_event(
        self, connection: sqlite3.Connection, event_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        previous_sequence, previous_hash = self._head(connection)
        body = {
            "sequence": previous_sequence + 1,
            "event_id": f"IGE-EVENT-{uuid.uuid4()}",
            "event_type": event_type,
            "occurred_at": utc_now(),
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event_hash = sha256_json(body)
        cursor = connection.execute(
            "INSERT INTO events(event_id,event_type,occurred_at,payload_json,previous_hash,event_hash) "
            "VALUES(?,?,?,?,?,?)",
            (
                body["event_id"],
                event_type,
                body["occurred_at"],
                canonical_json(payload),
                previous_hash,
                event_hash,
            ),
        )
        if int(cursor.lastrowid) != body["sequence"]:
            raise RuntimeError("event sequence diverged inside the immediate transaction")
        return {**body, "event_hash": event_hash}

    @staticmethod
    def _prior_command(connection: sqlite3.Connection, command_id: str) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT result_json,result_sha256 FROM commands WHERE command_id=?", (command_id,)
        ).fetchone()
        if row is None:
            return None
        result = json.loads(str(row["result_json"]))
        if sha256_json(result) != str(row["result_sha256"]):
            raise RuntimeError("stored idempotent command result failed integrity verification")
        return {**result, "idempotent_replay": True}

    @staticmethod
    def _record_command(
        connection: sqlite3.Connection,
        *,
        command_id: str,
        operation: str,
        result: dict[str, Any],
        event_hash: str,
    ) -> None:
        connection.execute(
            "INSERT INTO commands VALUES(?,?,?,?,?,?)",
            (
                command_id,
                operation,
                canonical_json(result),
                sha256_json(result),
                event_hash,
                utc_now(),
            ),
        )

    def commit_instruction(self, command_id: str, specification: dict[str, Any]) -> dict[str, Any]:
        if not command_id.strip():
            raise ValueError("command_id cannot be empty")
        with self.transaction() as connection:
            prior = self._prior_command(connection, command_id)
            if prior is not None:
                return prior
            instruction_id = str(specification.get("instruction_id", "")).strip()
            row = connection.execute(
                "SELECT COALESCE(MAX(revision),0) AS revision FROM instructions WHERE instruction_id=?",
                (instruction_id,),
            ).fetchone()
            value = dict(specification)
            value["revision"] = int(row["revision"]) + 1
            value.setdefault("created_at", utc_now())
            instruction = Instruction.from_dict(value)
            record = instruction.to_dict()
            record_hash = sha256_json(record)
            connection.execute(
                "UPDATE instructions SET current=0 WHERE instruction_id=? AND current=1",
                (instruction.instruction_id,),
            )
            event = self._append_event(
                connection,
                "INSTRUCTION_VERSION_COMMITTED",
                {"record": record, "record_sha256": record_hash},
            )
            connection.execute(
                "INSERT INTO instructions VALUES(?,?,?,?,?,?)",
                (
                    instruction.instruction_id,
                    instruction.revision,
                    canonical_json(record),
                    record_hash,
                    1,
                    event["event_hash"],
                ),
            )
            result = {
                "schema": "kch.ige.instruction-commit-receipt.v0.3.0",
                "state": "COMMITTED",
                "instruction": record,
                "record_sha256": record_hash,
                "event_hash": event["event_hash"],
                "idempotent_replay": False,
            }
            self._record_command(
                connection,
                command_id=command_id,
                operation="INSTRUCTION_COMMIT",
                result=result,
                event_hash=event["event_hash"],
            )
            return result

    def revoke_instruction(
        self,
        command_id: str,
        instruction_id: str,
        *,
        reason: str,
        authority_receipt_sha256: str,
    ) -> dict[str, Any]:
        if not reason.strip() or len(authority_receipt_sha256) != 64:
            raise ValueError("revocation requires a reason and authority receipt SHA-256")
        with self.transaction() as connection:
            prior = self._prior_command(connection, command_id)
            if prior is not None:
                return prior
            row = connection.execute(
                "SELECT * FROM instructions WHERE instruction_id=? AND current=1",
                (instruction_id,),
            ).fetchone()
            if row is None:
                raise KeyError(instruction_id)
            current = Instruction.from_dict(json.loads(str(row["record_json"])))
            if current.lifecycle is LifecycleState.REVOKED:
                raise ValueError("instruction is already revoked")
            value = current.to_dict()
            value["revision"] = current.revision + 1
            value["lifecycle"] = LifecycleState.REVOKED.value
            value["created_at"] = utc_now()
            value["provenance"] = {
                **current.provenance,
                "revocation_reason": reason.strip(),
                "revocation_authority_receipt_sha256": authority_receipt_sha256,
            }
            revoked = Instruction.from_dict(value)
            record = revoked.to_dict()
            record_hash = sha256_json(record)
            connection.execute(
                "UPDATE instructions SET current=0 WHERE instruction_id=? AND current=1",
                (instruction_id,),
            )
            event = self._append_event(
                connection,
                "INSTRUCTION_REVOKED",
                {"record": record, "record_sha256": record_hash},
            )
            connection.execute(
                "INSERT INTO instructions VALUES(?,?,?,?,?,?)",
                (
                    instruction_id,
                    revoked.revision,
                    canonical_json(record),
                    record_hash,
                    1,
                    event["event_hash"],
                ),
            )
            result = {
                "schema": "kch.ige.instruction-revocation-receipt.v0.3.0",
                "state": "REVOKED",
                "instruction": record,
                "record_sha256": record_hash,
                "event_hash": event["event_hash"],
                "idempotent_replay": False,
            }
            self._record_command(
                connection,
                command_id=command_id,
                operation="INSTRUCTION_REVOKE",
                result=result,
                event_hash=event["event_hash"],
            )
            return result

    def commit_profile(
        self,
        command_id: str,
        profile_id: str,
        profile: ConditionedCredalSet,
        evidence_refs: list[str],
    ) -> dict[str, Any]:
        if not profile_id.strip() or any(not str(item).strip() for item in evidence_refs):
            raise ValueError("profile_id and evidence_refs must be non-empty strings")
        if len(evidence_refs) != len(set(evidence_refs)):
            raise ValueError("evidence_refs must be unique")
        profile_value = profile.to_dict()
        profile_hash = sha256_json(profile_value)
        with self.transaction() as connection:
            prior = self._prior_command(connection, command_id)
            if prior is not None:
                return prior
            payload = {
                "profile_id": profile_id,
                "profile": profile_value,
                "profile_sha256": profile_hash,
                "evidence_refs": sorted(evidence_refs),
            }
            event = self._append_event(connection, "CREDAL_PROFILE_COMMITTED", payload)
            connection.execute(
                "INSERT INTO credal_profiles VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(profile_id) DO UPDATE SET profile_json=excluded.profile_json,"
                "profile_sha256=excluded.profile_sha256,evidence_refs_json=excluded.evidence_refs_json,"
                "event_hash=excluded.event_hash,updated_at=excluded.updated_at",
                (
                    profile_id,
                    canonical_json(profile_value),
                    profile_hash,
                    canonical_json(sorted(evidence_refs)),
                    event["event_hash"],
                    utc_now(),
                ),
            )
            result = {
                "schema": "kch.ige.credal-profile-receipt.v0.3.0",
                "state": "COMMITTED",
                "profile_id": profile_id,
                "profile_sha256": profile_hash,
                "evidence_refs": sorted(evidence_refs),
                "event_hash": event["event_hash"],
                "idempotent_replay": False,
            }
            self._record_command(
                connection,
                command_id=command_id,
                operation="CREDAL_PROFILE_COMMIT",
                result=result,
                event_hash=event["event_hash"],
            )
            return result

    def current_instructions(self, *, include_inactive: bool = True) -> list[Instruction]:
        query = "SELECT record_json FROM instructions WHERE current=1"
        with self.read() as connection:
            rows = connection.execute(query + " ORDER BY instruction_id").fetchall()
        values = [Instruction.from_dict(json.loads(str(row["record_json"]))) for row in rows]
        return values if include_inactive else [item for item in values if item.active]

    def get_instruction(self, instruction_id: str) -> Instruction:
        with self.read() as connection:
            row = connection.execute(
                "SELECT record_json FROM instructions WHERE instruction_id=? AND current=1",
                (instruction_id,),
            ).fetchone()
        if row is None:
            raise KeyError(instruction_id)
        return Instruction.from_dict(json.loads(str(row["record_json"])))

    def get_profile(self, profile_id: str) -> ConditionedCredalSet:
        with self.read() as connection:
            row = connection.execute(
                "SELECT profile_json,profile_sha256 FROM credal_profiles WHERE profile_id=?",
                (profile_id,),
            ).fetchone()
        if row is None:
            raise KeyError(profile_id)
        value = json.loads(str(row["profile_json"]))
        if sha256_json(value) != str(row["profile_sha256"]):
            raise RuntimeError("credal profile projection failed integrity verification")
        return ConditionedCredalSet.from_dict(value)

    def verify(self) -> dict[str, Any]:
        errors: list[str] = []
        expected_instructions: dict[str, tuple[dict[str, Any], str]] = {}
        expected_profiles: dict[str, tuple[dict[str, Any], str]] = {}
        previous = "GENESIS"
        event_count = 0
        with self.read() as connection:
            events = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
            for row in events:
                payload = json.loads(str(row["payload_json"]))
                body = {
                    "sequence": int(row["sequence"]),
                    "event_id": str(row["event_id"]),
                    "event_type": str(row["event_type"]),
                    "occurred_at": str(row["occurred_at"]),
                    "payload": payload,
                    "previous_hash": str(row["previous_hash"]),
                }
                if body["previous_hash"] != previous or sha256_json(body) != str(row["event_hash"]):
                    errors.append(f"EVENT_CHAIN:{row['sequence']}")
                previous = str(row["event_hash"])
                event_count += 1
                if body["event_type"] in {"INSTRUCTION_VERSION_COMMITTED", "INSTRUCTION_REVOKED"}:
                    record = payload["record"]
                    if sha256_json(record) != payload.get("record_sha256"):
                        errors.append(f"EVENT_INSTRUCTION_SEAL:{row['sequence']}")
                    expected_instructions[str(record["instruction_id"])] = (
                        record,
                        str(row["event_hash"]),
                    )
                elif body["event_type"] == "CREDAL_PROFILE_COMMITTED":
                    profile = payload["profile"]
                    if sha256_json(profile) != payload.get("profile_sha256"):
                        errors.append(f"EVENT_PROFILE_SEAL:{row['sequence']}")
                    expected_profiles[str(payload["profile_id"])] = (
                        profile,
                        str(row["event_hash"]),
                    )

            current_rows = connection.execute(
                "SELECT * FROM instructions WHERE current=1 ORDER BY instruction_id"
            ).fetchall()
            actual_ids = {str(row["instruction_id"]) for row in current_rows}
            if actual_ids != set(expected_instructions):
                errors.append("INSTRUCTION_PROJECTION_ID_SET")
            for row in current_rows:
                instruction_id = str(row["instruction_id"])
                record = json.loads(str(row["record_json"]))
                expected = expected_instructions.get(instruction_id)
                if (
                    sha256_json(record) != str(row["record_sha256"])
                    or expected is None
                    or record != expected[0]
                    or str(row["event_hash"]) != expected[1]
                ):
                    errors.append(f"INSTRUCTION_PROJECTION:{instruction_id}")

            profile_rows = connection.execute(
                "SELECT * FROM credal_profiles ORDER BY profile_id"
            ).fetchall()
            actual_profiles = {str(row["profile_id"]) for row in profile_rows}
            if actual_profiles != set(expected_profiles):
                errors.append("PROFILE_PROJECTION_ID_SET")
            for row in profile_rows:
                profile_id = str(row["profile_id"])
                profile = json.loads(str(row["profile_json"]))
                expected = expected_profiles.get(profile_id)
                if (
                    sha256_json(profile) != str(row["profile_sha256"])
                    or expected is None
                    or profile != expected[0]
                    or str(row["event_hash"]) != expected[1]
                ):
                    errors.append(f"PROFILE_PROJECTION:{profile_id}")

            event_hashes = {str(row["event_hash"]) for row in events}
            for row in connection.execute("SELECT * FROM commands ORDER BY command_id"):
                command_id = str(row["command_id"])
                result = json.loads(str(row["result_json"]))
                if sha256_json(result) != str(row["result_sha256"]):
                    errors.append(f"COMMAND_RESULT_SEAL:{command_id}")
                if str(row["event_hash"]) not in event_hashes:
                    errors.append(f"COMMAND_EVENT_ORPHAN:{command_id}")

        return {
            "schema": "kch.ige.store-integrity.v0.3.0",
            "gate": "PASS" if not errors else "FAIL",
            "errors": sorted(set(errors)),
            "event_count": event_count,
            "head_hash": previous,
            "instruction_count": len(expected_instructions),
            "profile_count": len(expected_profiles),
            "tamper_evident_locally": True,
            "physical_append_only_established": False,
            "external_anchor_established": False,
        }

    def snapshot(self) -> dict[str, Any]:
        integrity = self.verify()
        instructions = [item.to_dict() for item in self.current_instructions()]
        with self.read() as connection:
            profiles = [
                {
                    "profile_id": str(row["profile_id"]),
                    "profile": json.loads(str(row["profile_json"])),
                    "profile_sha256": str(row["profile_sha256"]),
                    "evidence_refs": json.loads(str(row["evidence_refs_json"])),
                }
                for row in connection.execute(
                    "SELECT * FROM credal_profiles ORDER BY profile_id"
                )
            ]
        core = {
            "schema": "kch.ige.snapshot.v0.3.0",
            "instructions": instructions,
            "credal_profiles": profiles,
            "integrity": integrity,
        }
        return {**core, "snapshot_sha256": sha256_json(core)}
