from __future__ import annotations

import re
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import canonical_json, sha256_bytes, sha256_json, sqlite_connection
from .recovery import RecoveryVault

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS chats (
    chat_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    native_id TEXT,
    source_uri TEXT,
    title TEXT NOT NULL,
    capture_mode TEXT NOT NULL,
    completeness TEXT NOT NULL,
    next_cursor TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    head_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
    turn_id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES chats(chat_id),
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,
    timestamp TEXT,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    turn_hash TEXT NOT NULL,
    UNIQUE(chat_id,seq)
);
CREATE TABLE IF NOT EXISTS superchats (
    superchat_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    merge_policy TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS superchat_members (
    superchat_id TEXT NOT NULL REFERENCES superchats(superchat_id),
    chat_id TEXT NOT NULL REFERENCES chats(chat_id),
    subsystem_role TEXT NOT NULL,
    rank INTEGER NOT NULL,
    context_independence INTEGER NOT NULL,
    PRIMARY KEY(superchat_id,chat_id)
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class PersistenceHub:
    """KCH/SCO custody. External completeness is claimed only after EOF evidence."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "persistence.sqlite3"
        self.vault = RecoveryVault(self.root / "recovery")
        with self.connect() as connection:
            connection.executescript(DDL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def create_chat(
        self,
        *,
        platform: str,
        title: str = "",
        native_id: str | None = None,
        source_uri: str | None = None,
        capture_mode: str = "KCH_NATIVE_AUTOMATIC",
    ) -> dict[str, Any]:
        if capture_mode not in {
            "KCH_NATIVE_AUTOMATIC",
            "HOST_HOOK_CONNECTED",
            "IMPORT_EXACT",
            "REFERENCE_ONLY",
        }:
            raise ValueError("invalid capture mode")
        chat_id = f"CHAT-{uuid.uuid4()}"
        timestamp = utc_now()
        genesis = sha256_json(
            {
                "chat_id": chat_id,
                "platform": platform,
                "native_id": native_id,
                "created_at": timestamp,
            }
        )
        completeness = "OPEN_STREAM" if capture_mode != "REFERENCE_ONLY" else "NO_PAYLOAD"
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO chats VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    chat_id,
                    platform,
                    native_id,
                    source_uri,
                    title,
                    capture_mode,
                    completeness,
                    None,
                    timestamp,
                    timestamp,
                    genesis,
                ),
            )
            connection.commit()
        return self.get_chat(chat_id)

    def append_turn(
        self, chat_id: str, *, role: str, payload: Any, timestamp: str | None = None
    ) -> dict[str, Any]:
        payload_json = canonical_json(payload)
        payload_hash = sha256_bytes(payload_json.encode("utf-8"))
        turn_id = f"TURN-{uuid.uuid4()}"
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            chat = connection.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
            if chat is None:
                raise KeyError(chat_id)
            if chat["completeness"] == "COMPLETE_EOF_VERIFIED":
                raise ValueError("cannot append after a chat was sealed COMPLETE_EOF_VERIFIED")
            seq = int(
                connection.execute(
                    "SELECT COUNT(*)+1 FROM turns WHERE chat_id=?", (chat_id,)
                ).fetchone()[0]
            )
            previous = str(chat["head_hash"])
            turn_hash = sha256_json(
                {
                    "chat_id": chat_id,
                    "seq": seq,
                    "role": role,
                    "timestamp": timestamp,
                    "payload_hash": payload_hash,
                    "previous_hash": previous,
                }
            )
            connection.execute(
                "INSERT INTO turns VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    turn_id,
                    chat_id,
                    seq,
                    role,
                    timestamp,
                    payload_json,
                    payload_hash,
                    previous,
                    turn_hash,
                ),
            )
            connection.execute(
                "UPDATE chats SET updated_at=?,head_hash=? WHERE chat_id=?",
                (utc_now(), turn_hash, chat_id),
            )
            connection.commit()
        custody = self.vault.save(
            f"chats/{chat_id}/turns/{seq:09d}.json",
            payload_json,
            kind="CHAT_TURN_EXACT_JSON",
            actor="KCH_SYSTEM",
            operation="APPEND_TURN",
            media_type="application/json",
        )
        return {
            "turn_id": turn_id,
            "chat_id": chat_id,
            "seq": seq,
            "turn_hash": turn_hash,
            "custody": custody,
        }

    def mark_page(
        self, chat_id: str, next_cursor: str | None, *, source_receipt: dict[str, Any]
    ) -> dict[str, Any]:
        """Record pagination evidence without promoting caller assertions to verified EOF.

        ``next_cursor is None`` is only a transport declaration.  This public
        boundary cannot authenticate a native host connector, so it must never
        manufacture ``COMPLETE_EOF_VERIFIED``.  A future trusted connector may
        add a separate sealing boundary after validating native provenance.
        """
        if not isinstance(source_receipt, dict):
            raise TypeError("source_receipt must be an object")
        required = {"source_system", "source_uri", "page_ordinal", "payload_sha256", "eof_attested"}
        missing = required - set(source_receipt)
        if missing:
            raise ValueError(f"source_receipt missing fields: {sorted(missing)}")
        if (
            not isinstance(source_receipt["source_system"], str)
            or not source_receipt["source_system"].strip()
        ):
            raise ValueError("source_system must be a non-empty string")
        if (
            not isinstance(source_receipt["source_uri"], str)
            or not source_receipt["source_uri"].strip()
        ):
            raise ValueError("source_uri must be a non-empty string")
        if (
            not isinstance(source_receipt["page_ordinal"], int)
            or isinstance(source_receipt["page_ordinal"], bool)
            or source_receipt["page_ordinal"] < 1
        ):
            raise ValueError("page_ordinal must be a positive integer")
        if not re.fullmatch(r"[0-9a-f]{64}", str(source_receipt["payload_sha256"])):
            raise ValueError("payload_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(source_receipt["eof_attested"], bool):
            raise ValueError("eof_attested must be boolean")
        if source_receipt["eof_attested"] != (next_cursor is None):
            raise ValueError("eof_attested must agree with next_cursor")

        completeness = (
            "EOF_ATTESTED_UNVERIFIED" if next_cursor is None else "PARTIAL_MORE_AVAILABLE"
        )
        receipt = {
            **source_receipt,
            "recorded_next_cursor": next_cursor,
            "kch_adjudication": completeness,
            "native_connector_authenticated": False,
            "transport_completeness_verified": False,
            "claim_ceiling": "CALLER_ATTESTATION_ONLY",
        }
        with self.connect() as connection:
            result = connection.execute(
                "UPDATE chats SET next_cursor=?,completeness=?,updated_at=? WHERE chat_id=?",
                (next_cursor, completeness, utc_now(), chat_id),
            )
            if result.rowcount != 1:
                raise KeyError(chat_id)
            connection.commit()
        self.vault.save_json(
            f"chats/{chat_id}/page-receipts/{uuid.uuid4()}.json",
            receipt,
            kind="CHAT_PAGE_RECEIPT",
            actor="KCH_SYSTEM",
            operation="MARK_PAGE_CURSOR",
        )
        return {**self.get_chat(chat_id), "page_adjudication": receipt}

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            chat = connection.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
            if chat is None:
                raise KeyError(chat_id)
            value = dict(chat)
            value["turn_count"] = int(
                connection.execute(
                    "SELECT COUNT(*) FROM turns WHERE chat_id=?", (chat_id,)
                ).fetchone()[0]
            )
            return value

    def create_superchat(self, *, title: str, members: list[dict[str, Any]]) -> dict[str, Any]:
        superchat_id = f"SCO-{uuid.uuid4()}"
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO superchats VALUES(?,?,?,?,?)",
                (superchat_id, title, timestamp, timestamp, "ORCHESTRATE_WITHOUT_MERGING"),
            )
            for index, member in enumerate(members, start=1):
                connection.execute(
                    "INSERT INTO superchat_members VALUES(?,?,?,?,?)",
                    (
                        superchat_id,
                        member["chat_id"],
                        member["subsystem_role"],
                        int(member.get("rank", index)),
                        1,
                    ),
                )
            connection.commit()
        state = self.get_superchat(superchat_id)
        self.vault.save_json(
            f"superchats/{superchat_id}.json",
            state,
            kind="SCO_ORCHESTRATION_MANIFEST",
            actor="USER",
            operation="CREATE_WITHOUT_MERGING",
        )
        return state

    def get_superchat(self, superchat_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM superchats WHERE superchat_id=?", (superchat_id,)
            ).fetchone()
            if row is None:
                raise KeyError(superchat_id)
            members = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM superchat_members WHERE superchat_id=? ORDER BY rank,chat_id",
                    (superchat_id,),
                )
            ]
            return {
                **dict(row),
                "members": members,
                "context_fusion": False,
                "member_independence_preserved": True,
            }

    def coverage(self) -> dict[str, Any]:
        return {
            "schema": "kch.persistence-coverage.v0.1.0",
            "KCH_NATIVE": "AUTOMATIC_EXACT_TURN_CUSTODY",
            "SCO": "ORCHESTRATION_MANIFEST_PLUS_MEMBER_REFERENCES_NO_MERGE",
            "Codex": "REQUIRES_NATIVE_THREAD_CONNECTOR_OR_EXACT_IMPORT",
            "Cline": "REQUIRES_HOST_HOOK_OR_EXACT_EXPORT_IMPORT",
            "OpenCode": "REQUIRES_HOST_HOOK_OR_EXACT_EXPORT_IMPORT",
            "Cowork": "REQUIRES_HOST_HOOK_OR_EXACT_EXPORT_IMPORT",
            "other_hosts": "NO_COMPLETENESS_CLAIM_WITHOUT_TRANSPORT_AND_EOF_EVIDENCE",
            "public_page_receipt_ceiling": "EOF_ATTESTED_UNVERIFIED",
            "verified_eof_requires": "AUTHENTICATED_NATIVE_CONNECTOR_BOUNDARY_NOT_YET_IMPLEMENTED",
        }

    def verify_chat(self, chat_id: str) -> dict[str, Any]:
        errors: list[str] = []
        with closing(self.connect()) as connection:
            chat = connection.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
            if chat is None:
                raise KeyError(chat_id)
            genesis = sha256_json(
                {
                    "chat_id": chat_id,
                    "platform": chat["platform"],
                    "native_id": chat["native_id"],
                    "created_at": chat["created_at"],
                }
            )
            previous = genesis
            rows = connection.execute(
                "SELECT * FROM turns WHERE chat_id=? ORDER BY seq", (chat_id,)
            ).fetchall()
            for expected_seq, row in enumerate(rows, start=1):
                payload_hash = sha256_bytes(str(row["payload_json"]).encode("utf-8"))
                expected = sha256_json(
                    {
                        "chat_id": chat_id,
                        "seq": expected_seq,
                        "role": row["role"],
                        "timestamp": row["timestamp"],
                        "payload_hash": payload_hash,
                        "previous_hash": previous,
                    }
                )
                if int(row["seq"]) != expected_seq or payload_hash != row["payload_hash"]:
                    errors.append(f"turn {expected_seq} sequence or payload mismatch")
                if row["previous_hash"] != previous or row["turn_hash"] != expected:
                    errors.append(f"turn {expected_seq} chain mismatch")
                previous = expected
            if previous != chat["head_hash"]:
                errors.append("chat head hash mismatch")
        return {"passed": not errors, "chat_id": chat_id, "turn_count": len(rows), "errors": errors}
