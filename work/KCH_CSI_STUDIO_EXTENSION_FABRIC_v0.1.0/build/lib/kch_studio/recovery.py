from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import canonical_json, safe_child, sha256_bytes, sha256_json, sqlite_connection

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    logical_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    current_seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    seq INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    operation TEXT NOT NULL,
    actor TEXT NOT NULL,
    media_type TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    content_sha256 TEXT NOT NULL,
    content BLOB NOT NULL,
    warning_json TEXT NOT NULL,
    previous_revision_hash TEXT NOT NULL,
    revision_hash TEXT NOT NULL,
    UNIQUE(asset_id, seq)
);
CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    target TEXT NOT NULL,
    proposed_operation TEXT NOT NULL,
    overridden INTEGER NOT NULL,
    recovery_snapshot TEXT,
    evidence_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    label TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class RecoveryVault:
    """Append-only byte custody for every KCH-editable logical asset."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "recovery.sqlite3"
        with self.connect() as connection:
            connection.executescript(DDL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _revision_hash(
        *,
        asset_id: str,
        seq: int,
        timestamp: str,
        operation: str,
        actor: str,
        media_type: str,
        content_sha256: str,
        warnings: list[dict[str, Any]],
        previous: str,
    ) -> str:
        return sha256_json(
            {
                "asset_id": asset_id,
                "seq": seq,
                "timestamp": timestamp,
                "operation": operation,
                "actor": actor,
                "media_type": media_type,
                "content_sha256": content_sha256,
                "warnings": warnings,
                "previous_revision_hash": previous,
            }
        )

    def save(
        self,
        logical_key: str,
        content: bytes | str,
        *,
        kind: str,
        actor: str,
        operation: str = "SAVE",
        media_type: str = "text/plain; charset=utf-8",
        warnings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not logical_key.strip() or "\x00" in logical_key:
            raise ValueError("logical_key must be non-empty and contain no NUL")
        raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        warnings = list(warnings or [])
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            asset = connection.execute(
                "SELECT * FROM assets WHERE logical_key=?", (logical_key,)
            ).fetchone()
            if asset is None:
                asset_id = f"ASSET-{uuid.uuid4()}"
                seq = 1
                previous = "0" * 64
                connection.execute(
                    "INSERT INTO assets(asset_id,logical_key,kind,created_at,updated_at,current_seq) VALUES(?,?,?,?,?,?)",
                    (asset_id, logical_key, kind, timestamp, timestamp, seq),
                )
            else:
                asset_id = str(asset["asset_id"])
                seq = int(asset["current_seq"]) + 1
                previous_row = connection.execute(
                    "SELECT revision_hash FROM revisions WHERE asset_id=? AND seq=?",
                    (asset_id, seq - 1),
                ).fetchone()
                if previous_row is None:
                    raise ValueError("recovery chain is incomplete")
                previous = str(previous_row["revision_hash"])
                connection.execute(
                    "UPDATE assets SET kind=?,updated_at=?,current_seq=? WHERE asset_id=?",
                    (kind, timestamp, seq, asset_id),
                )
            digest = sha256_bytes(raw)
            revision_hash = self._revision_hash(
                asset_id=asset_id,
                seq=seq,
                timestamp=timestamp,
                operation=operation,
                actor=actor,
                media_type=media_type,
                content_sha256=digest,
                warnings=warnings,
                previous=previous,
            )
            connection.execute(
                """INSERT INTO revisions(
                    asset_id,seq,timestamp,operation,actor,media_type,byte_count,content_sha256,
                    content,warning_json,previous_revision_hash,revision_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    asset_id,
                    seq,
                    timestamp,
                    operation,
                    actor,
                    media_type,
                    len(raw),
                    digest,
                    raw,
                    canonical_json(warnings),
                    previous,
                    revision_hash,
                ),
            )
            connection.commit()
        return {
            "asset_id": asset_id,
            "logical_key": logical_key,
            "kind": kind,
            "seq": seq,
            "bytes": len(raw),
            "content_sha256": digest,
            "revision_hash": revision_hash,
            "previous_revision_hash": previous,
            "warning_count": len(warnings),
            "recoverable": True,
        }

    def save_json(
        self, logical_key: str, value: Any, *, kind: str, actor: str, operation: str = "SAVE"
    ) -> dict[str, Any]:
        return self.save(
            logical_key,
            canonical_json(value),
            kind=kind,
            actor=actor,
            operation=operation,
            media_type="application/json",
        )

    def latest(self, logical_key: str, *, decode: bool = False) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """SELECT a.logical_key,a.kind,r.* FROM assets a
                JOIN revisions r ON r.asset_id=a.asset_id AND r.seq=a.current_seq
                WHERE a.logical_key=?""",
                (logical_key,),
            ).fetchone()
            if row is None:
                raise KeyError(logical_key)
            value = dict(row)
            raw = bytes(value.pop("content"))
            value["content"] = raw.decode("utf-8") if decode else raw
            value["warnings"] = json.loads(str(value.pop("warning_json")))
            return value

    def revision(self, logical_key: str, seq: int, *, decode: bool = False) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """SELECT a.logical_key,a.kind,r.* FROM assets a JOIN revisions r USING(asset_id)
                WHERE a.logical_key=? AND r.seq=?""",
                (logical_key, seq),
            ).fetchone()
            if row is None:
                raise KeyError((logical_key, seq))
            value = dict(row)
            raw = bytes(value.pop("content"))
            value["content"] = raw.decode("utf-8") if decode else raw
            value["warnings"] = json.loads(str(value.pop("warning_json")))
            return value

    def restore(self, logical_key: str, seq: int, *, actor: str) -> dict[str, Any]:
        source = self.revision(logical_key, seq)
        return self.save(
            logical_key,
            source["content"],
            kind=str(source["kind"]),
            actor=actor,
            operation=f"RESTORE_FROM_REVISION_{seq}",
            media_type=str(source["media_type"]),
        )

    def record_alert(
        self,
        *,
        severity: str,
        code: str,
        message: str,
        target: str,
        proposed_operation: str,
        overridden: bool,
        recovery_snapshot: str | None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        alert_id = f"ALERT-{uuid.uuid4()}"
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    alert_id,
                    timestamp,
                    severity,
                    code,
                    message,
                    target,
                    proposed_operation,
                    int(overridden),
                    recovery_snapshot,
                    canonical_json(evidence or {}),
                ),
            )
            connection.commit()
        return {
            "alert_id": alert_id,
            "timestamp": timestamp,
            "severity": severity,
            "code": code,
            "target": target,
            "overridden": overridden,
            "recovery_snapshot": recovery_snapshot,
        }

    def snapshot(self, label: str) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT a.logical_key,a.kind,a.current_seq,r.content_sha256,r.revision_hash,r.byte_count
                FROM assets a JOIN revisions r ON r.asset_id=a.asset_id AND r.seq=a.current_seq
                ORDER BY a.logical_key"""
            ).fetchall()
            manifest = [dict(row) for row in rows]
            snapshot_id = f"SNAP-{uuid.uuid4()}"
            timestamp = utc_now()
            digest = sha256_json(manifest)
            connection.execute(
                "INSERT INTO snapshots VALUES(?,?,?,?,?)",
                (snapshot_id, timestamp, label, canonical_json(manifest), digest),
            )
            connection.commit()
        return {
            "snapshot_id": snapshot_id,
            "timestamp": timestamp,
            "label": label,
            "asset_count": len(manifest),
            "manifest_hash": digest,
            "manifest": manifest,
        }

    def verify(self) -> dict[str, Any]:
        errors: list[str] = []
        chains = 0
        with closing(self.connect()) as connection:
            assets = connection.execute("SELECT * FROM assets ORDER BY logical_key").fetchall()
            for asset in assets:
                previous = "0" * 64
                rows = connection.execute(
                    "SELECT * FROM revisions WHERE asset_id=? ORDER BY seq", (asset["asset_id"],)
                ).fetchall()
                for expected_seq, row in enumerate(rows, start=1):
                    warnings = json.loads(str(row["warning_json"]))
                    observed_content_hash = sha256_bytes(bytes(row["content"]))
                    expected_hash = self._revision_hash(
                        asset_id=str(row["asset_id"]),
                        seq=int(row["seq"]),
                        timestamp=str(row["timestamp"]),
                        operation=str(row["operation"]),
                        actor=str(row["actor"]),
                        media_type=str(row["media_type"]),
                        content_sha256=str(row["content_sha256"]),
                        warnings=warnings,
                        previous=previous,
                    )
                    if int(row["seq"]) != expected_seq:
                        errors.append(f"{asset['logical_key']}: non-contiguous revision sequence")
                    if observed_content_hash != str(row["content_sha256"]):
                        errors.append(f"{asset['logical_key']}:{row['seq']}: content hash mismatch")
                    if (
                        str(row["previous_revision_hash"]) != previous
                        or str(row["revision_hash"]) != expected_hash
                    ):
                        errors.append(
                            f"{asset['logical_key']}:{row['seq']}: revision chain mismatch"
                        )
                    previous = expected_hash
                if len(rows) != int(asset["current_seq"]):
                    errors.append(f"{asset['logical_key']}: current sequence mismatch")
                chains += 1
        return {"passed": not errors, "asset_chains": chains, "errors": errors}

    def export_latest(
        self, logical_key: str, export_root: str | Path, relative_path: str | Path
    ) -> dict[str, Any]:
        value = self.latest(logical_key)
        root = Path(export_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = safe_child(root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(value["content"])
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {
            "path": str(target),
            "bytes": target.stat().st_size,
            "sha256": sha256_bytes(target.read_bytes()),
        }
