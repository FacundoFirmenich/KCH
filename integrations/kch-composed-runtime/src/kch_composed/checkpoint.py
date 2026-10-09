"""Bounded, scope-specific evidence transport. Never restores active authority."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile

from .memory import MemoryStore, Scope, _canonical_json, _seal
from .journal import SessionJournal, JournalIntegrityError

SCHEMA = "kch.composed.evidence-checkpoint.v1"
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 20000
TABLES = ("memory_revisions", "memory_heads", "memory_folds", "memory_views",
          "memory_dependencies", "memory_invalidations")
SESSION_TABLES = ("session_configuration", "session_events", "session_calls", "session_heads")


class CheckpointError(ValueError):
    pass


def _json(value):
    return _canonical_json(value).encode("utf-8")


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _load(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CheckpointError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(CheckpointError("nonfinite JSON")))


def _snapshot(runtime):
    memory, journal = runtime.memory, runtime.journal
    key = memory._key(runtime.scope)
    payloads = {}
    # Writer locks make both scoped projections quiescent at their common held point.
    with memory._tx(write=True), journal._tx(write=True):
        journal._verify()
        memory._verify_heads(key)
        size = memory._db.execute("SELECT COALESCE(SUM(length(content)+length(manifest)),0) "
                                  "FROM memory_revisions WHERE scope_key=?", (key,)).fetchone()[0]
        size += journal._db.execute("SELECT COALESCE(SUM(length(payload)),0) "
                                    "FROM session_events WHERE scope_key=?", (key,)).fetchone()[0]
        if size > MAX_TOTAL_BYTES:
            raise CheckpointError("source scope exceeds checkpoint size limit")
        snapshot = {"scope": asdict(runtime.scope), "memory": {}, "session": {}, "import_audit": []}
        if memory._db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkpoint_import_outbox'").fetchone():
            snapshot["import_audit"] = [dict(row) for row in memory._db.execute(
                "SELECT * FROM checkpoint_import_outbox WHERE scope_key=? ORDER BY receipt_id", (key,))]
        for table in TABLES:
            rows = [dict(r) for r in memory._db.execute(
                f"SELECT * FROM {table} WHERE scope_key=? ORDER BY rowid", (key,))]
            for row in rows:
                if table == "memory_revisions":
                    content = bytes(row.pop("content"))
                    name = "blobs/" + _sha(content)
                    payloads[name] = content
                    row["content_entry"] = name
            snapshot["memory"][table] = rows
        for table in SESSION_TABLES:
            snapshot["session"][table] = [dict(r) for r in journal._db.execute(
                f"SELECT * FROM {table} WHERE scope_key=? ORDER BY rowid", (journal._key,))]
    payloads["snapshot.json"] = _json(snapshot)
    _validate_snapshot(snapshot, payloads)
    return snapshot, payloads


def export_checkpoint(runtime, path):
    """Export only runtime.scope. This function never exports native state databases."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    with runtime.lock():
        snapshot, payloads = _snapshot(runtime)
        if len(payloads) + 1 > MAX_ENTRIES or sum(map(len, payloads.values())) > MAX_TOTAL_BYTES:
            raise CheckpointError("checkpoint exceeds entry/total limit")
        if any(len(raw) > MAX_ENTRY_BYTES for raw in payloads.values()):
            raise CheckpointError("checkpoint entry exceeds limit")
        manifest = {"schema": SCHEMA, "mode": "EVIDENCE_ONLY", "scope": snapshot["scope"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "authority_transferred": False, "automatic_replay": False,
                    "entries": [{"path": name, "bytes": len(raw), "sha256": _sha(raw)}
                                for name, raw in sorted(payloads.items())]}
        payloads["manifest.json"] = _json(manifest)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".kch-checkpoint-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for name, raw in sorted(payloads.items()):
                        archive.writestr(name, raw)
                handle.flush()
                os.fsync(handle.fileno())
            if Path(temporary).stat().st_size > MAX_ARCHIVE_BYTES:
                raise CheckpointError("archive exceeds size limit")
            # Atomic and refuses overwrite, including a raced symlink destination.
            os.link(temporary, path)
            # The link is a separate durability boundary from the file contents.
            # Failure leaves the created archive for inspection, without issuing
            # a success receipt or silently retrying/overwriting the destination.
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return {"manifest": manifest, "path": str(path.resolve()),
                "archive_sha256": _sha(path.read_bytes())}


def _read_archive(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_ARCHIVE_BYTES + 1)
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise CheckpointError("archive exceeds size limit")
    payloads = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTRIES or sum(x.file_size for x in infos) > MAX_TOTAL_BYTES:
                raise CheckpointError("archive expansion exceeds limit")
            for info in infos:
                name = info.filename
                parts = PurePosixPath(name).parts
                mode = info.external_attr >> 16
                if (not parts or name.startswith("/") or "\\" in name or ":" in name
                        or ".." in parts or "." in parts or name != "/".join(parts)
                        or name in payloads or info.is_dir() or stat.S_ISLNK(mode)
                        or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                        or info.flag_bits & 1 or info.file_size > MAX_ENTRY_BYTES):
                    raise CheckpointError("unsafe/duplicate/oversized archive entry")
                with archive.open(info) as entry:
                    content = entry.read(MAX_ENTRY_BYTES + 1)
                if len(content) != info.file_size or len(content) > MAX_ENTRY_BYTES:
                    raise CheckpointError("entry length mismatch")
                payloads[name] = content
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise CheckpointError("invalid or unsupported ZIP") from exc
    manifest = _load(payloads.pop("manifest.json", b"{}"))
    if (manifest.get("schema") != SCHEMA or manifest.get("mode") != "EVIDENCE_ONLY"
            or manifest.get("authority_transferred") is not False
            or manifest.get("automatic_replay") is not False):
        raise CheckpointError("unsupported checkpoint contract")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != len(payloads):
        raise CheckpointError("manifest entry mismatch")
    listed = set()
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise CheckpointError("malformed manifest entry")
        name = item["path"]
        if (name in listed or name not in payloads or type(item["bytes"]) is not int
                or len(payloads[name]) != item["bytes"] or _sha(payloads[name]) != item["sha256"]):
            raise CheckpointError("entry integrity failed")
        listed.add(name)
    snapshot = _load(payloads.get("snapshot.json", b"{}"))
    if snapshot.get("scope") != manifest.get("scope"):
        raise CheckpointError("source scope mismatch")
    _validate_snapshot(snapshot, payloads)
    return raw, manifest, snapshot, payloads


def _insert_rows(db, table, rows):
    columns = [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
    for row in rows:
        if set(row) != set(columns):
            raise CheckpointError("unexpected snapshot row schema")
        db.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                   [row[c] for c in columns])


def _validate_snapshot(snapshot, payloads):
    """Validate original invariants in isolated databases before destination mutation."""
    try:
        scope = Scope(**snapshot["scope"])
        key = MemoryStore._key(scope)
        if set(snapshot) != {"scope", "memory", "session", "import_audit"} or set(snapshot["memory"]) != set(TABLES):
            raise CheckpointError("snapshot schema mismatch")
        if set(snapshot["session"]) != set(SESSION_TABLES):
            raise CheckpointError("session schema mismatch")
        rows = {table: [dict(row) for row in snapshot["memory"][table]] for table in TABLES}
        referenced = {"snapshot.json"}
        for row in rows["memory_revisions"]:
            name = row.pop("content_entry")
            content = payloads[name]
            if name != "blobs/" + _sha(content):
                raise CheckpointError("blob identity mismatch")
            row["content"] = content
            referenced.add(name)
        if referenced != set(payloads):
            raise CheckpointError("unreferenced or missing payload")
        with MemoryStore(":memory:", enable_fts=False) as memory:
            for table in TABLES:
                if any(row["scope_key"] != key for row in rows[table]):
                    raise CheckpointError("cross-scope row")
                _insert_rows(memory._db, table, rows[table])
            memory._verify_heads(key)
            objects = set()
            expected_dependencies = set()
            for row in rows["memory_revisions"]:
                record = memory._revision(key, row["revision_id"], allow_invalidated=True)
                objects.add(row["revision_id"])
                predecessor = record["predecessor_revision_id"]
                if predecessor:
                    old = memory._revision(key, predecessor, allow_invalidated=True)
                    if (old["source_id"] != record["source_id"] or old["version"] + 1 != record["version"]
                            or not memory._invalid(key, predecessor)):
                        raise CheckpointError("invalid correction lineage")
                elif record["version"] != 1:
                    raise CheckpointError("missing correction predecessor")
            for row in rows["memory_folds"]:
                fold = memory._fold(key, row["fold_id"], allow_invalidated=True)["manifest"]
                memory._unfold(key, row["fold_id"], allow_invalidated=True)
                objects.add(row["fold_id"])
                children = {r["revision_id"] for r in fold["leaves"]}
                children.update(m["fold_id"] for m in fold["members"] if m["kind"] == "fold")
                expected_dependencies.update((row["fold_id"], child) for child in children)
            for row in rows["memory_views"]:
                view = memory.read_view(scope, row["view_id"], allow_invalidated=True)
                objects.add(row["view_id"])
                expected_dependencies.update((row["view_id"], r["revision_id"]) for r in view["references"])
                expected_dependencies.update((row["view_id"], f["fold_id"]) for f in view["folds"])
            if {(r["parent_id"], r["child_id"]) for r in rows["memory_dependencies"]} != expected_dependencies:
                raise CheckpointError("derived dependency projection differs")
            invalid = {r["object_id"] for r in rows["memory_invalidations"]}
            if not invalid <= objects or any(r["caused_by"] not in objects for r in rows["memory_invalidations"]):
                raise CheckpointError("invalidation references unavailable object")
            if any(child in invalid and parent not in invalid for parent, child in expected_dependencies):
                raise CheckpointError("derived invalidation omitted")
        for audit in snapshot["import_audit"]:
            if (set(audit) != {"receipt_id", "scope_key", "receipt", "delivered", "receipt_sha256"}
                    or audit["scope_key"] != key or audit["delivered"] not in (0, 1)
                    or _sha(audit["receipt"].encode("utf-8")) != audit["receipt_sha256"]):
                raise CheckpointError("invalid imported audit record")
            receipt = _load(audit["receipt"])
            identity = _seal({"archive_sha256": receipt["archive_sha256"],
                              "destination_scope": receipt["destination_scope"],
                              "selected": sorted(receipt["selected_sources"])})
            if (identity != audit["receipt_id"] or receipt["receipt_id"] != identity
                    or receipt["destination_scope"] != snapshot["scope"]
                    or receipt["mode"] != "EVIDENCE_ONLY"
                    or receipt["authority_transferred"] is not False
                    or receipt["automatic_replay"] is not False):
                raise CheckpointError("imported audit record integrity differs")
        configs = snapshot["session"]["session_configuration"]
        if len(configs) != 1:
            raise CheckpointError("exactly one source session required")
        config = _load(configs[0]["configuration"])
        with SessionJournal(":memory:", **snapshot["scope"], configuration=config) as journal:
            for table in reversed(SESSION_TABLES):
                journal._db.execute(f"DELETE FROM {table}")
            for table in SESSION_TABLES:
                data = snapshot["session"][table]
                if any(row["scope_key"] != key for row in data):
                    raise CheckpointError("cross-scope session row")
                _insert_rows(journal._db, table, data)
            journal.verify()
    except CheckpointError:
        raise
    except Exception as exc:
        raise CheckpointError("snapshot invariant validation failed") from exc


def _audit(runtime, receipt):
    """Idempotent outbox delivery; imported events are not active runtime events."""
    identity = receipt["receipt_id"]
    matches = [event for event in runtime.journal.events()
               if event["kind"] == "checkpoint.imported" and event["payload"].get("receipt_id") == identity]
    if len(matches) > 1 or (matches and matches[0]["payload"] != receipt):
        raise CheckpointError("journal import receipt differs from immutable outbox")
    if not matches:
        runtime.journal.append("checkpoint.imported", receipt)
    with runtime.memory._tx(write=True):
        runtime.memory._db.execute("UPDATE checkpoint_import_outbox SET delivered=1 WHERE receipt_id=?", (identity,))



def _materialized_mapping(runtime, raw, digest, snapshot, payloads, source_ids):
    """Verify persisted evidence against the input, including obsolete revisions."""
    memory = runtime.memory
    key = memory._key(runtime.scope)
    memory._verify_heads(key)
    prefix = "checkpoint:" + digest + ":"
    origin = {"mode": "EVIDENCE_ONLY", "source_scope": snapshot["scope"], "archive_sha256": digest,
              "authority_transferred": False}
    archive = memory._revision(key, memory._head(key, prefix + "archive"))
    if (archive["content"] != raw or archive["provenance"] != origin
            or archive["version"] != 1 or archive["media_type"] != "application/zip"):
        raise CheckpointError("persisted archive evidence differs")
    invalidations = {row["object_id"]: row for row in snapshot["memory"]["memory_invalidations"]}
    mapping = {}
    for source in source_ids:
        originals = sorted((row for row in snapshot["memory"]["memory_revisions"] if row["source_id"] == source),
                           key=lambda row: row["version"])
        target = prefix + "source:" + source
        destination = memory._db.execute("SELECT revision_id FROM memory_revisions WHERE scope_key=? AND source_id=? ORDER BY version",
                                         (key, target)).fetchall()
        if len(destination) != len(originals):
            raise CheckpointError("persisted selected source revision count differs")
        predecessor = None
        for original_row, target_row in zip(originals, destination):
            original = _load(original_row["manifest"])
            record = memory._revision(key, target_row["revision_id"], allow_invalidated=True)
            provenance = {**origin, "source_manifest": original, "source_record_sha256": original_row["record_sha256"]}
            if (record["content"] != payloads[original_row["content_entry"]]
                    or record["provenance"] != provenance or record["version"] != original_row["version"]
                    or record["media_type"] != original["media_type"]
                    or record["predecessor_revision_id"] != predecessor):
                raise CheckpointError("persisted selected source differs from input")
            expected_invalid = invalidations.get(original_row["revision_id"])
            actual_invalid = memory._db.execute("SELECT reason FROM memory_invalidations WHERE scope_key=? AND object_id=?",
                                               (key, record["revision_id"])).fetchone()
            if (bool(expected_invalid) != bool(actual_invalid) or
                    (expected_invalid and actual_invalid["reason"] != "Imported source invalidation: " + expected_invalid["reason"])):
                raise CheckpointError("persisted selected source invalidation differs")
            mapping[original_row["revision_id"]] = record["revision_id"]
            predecessor = record["revision_id"]
    return mapping


def _validate_import_receipt(runtime, receipt, raw, digest, snapshot, payloads, source_ids, identity, matches):
    mapping = _materialized_mapping(runtime, raw, digest, snapshot, payloads, source_ids)
    prefix = "checkpoint:" + digest + ":"
    expected = {"schema": "kch.composed.checkpoint-import-receipt.v1", "receipt_id": identity,
                "mode": "EVIDENCE_ONLY", "source_scope": snapshot["scope"],
                "destination_scope": asdict(runtime.scope), "archive_sha256": digest,
                "archive_source_id": prefix + "archive",
                "selected_sources": {source: prefix + "source:" + source for source in source_ids},
                "revision_mapping": mapping, "authority_transferred": False,
                "automatic_replay": False, "provider_binding_activated": False,
                "folds_and_sessions": "PRESERVED_IN_ARCHIVE_NOT_ACTIVATED",
                "imported_at": receipt.get("imported_at")}
    if receipt != expected or not isinstance(receipt.get("imported_at"), str):
        raise CheckpointError("persisted import receipt differs from input contract")
    try:
        timestamp = datetime.fromisoformat(receipt["imported_at"])
        if timestamp.tzinfo is None:
            raise ValueError("unbound timestamp")
    except ValueError as exc:
        raise CheckpointError("invalid import receipt timestamp") from exc
    if len(matches) > 1 or (matches and matches[0]["payload"] != receipt):
        raise CheckpointError("journal import receipt differs from immutable outbox")


def import_checkpoint_evidence(runtime, path, source_ids=None):
    """Archive all evidence; only explicitly selected sources enter destination memory.

    Historical provider messages remain bytes inside the evidence archive. They are
    never appended as live messages, bindings, call receipts, grants, or leases.
    """
    if source_ids is None:
        source_ids = []
    if not isinstance(source_ids, list) or any(not isinstance(x, str) or not x for x in source_ids):
        raise CheckpointError("source_ids must be a list of explicit source names")
    if len(set(source_ids)) != len(source_ids):
        raise CheckpointError("duplicate source selection")
    raw, manifest, snapshot, payloads = _read_archive(path)
    digest = _sha(raw)
    source_ids = sorted(source_ids)
    revisions = snapshot["memory"]["memory_revisions"]
    available = {row["source_id"] for row in revisions}
    if not set(source_ids) <= available:
        raise CheckpointError("selected source unavailable")
    prefix = "checkpoint:" + digest + ":"
    archive_source = prefix + "archive"
    identity = _seal({"archive_sha256": digest, "destination_scope": asdict(runtime.scope), "selected": source_ids})
    memory = runtime.memory
    with runtime.lock():
        matches = [event for event in runtime.journal.events()
                   if event["kind"] == "checkpoint.imported" and event["payload"].get("receipt_id") == identity]
        with memory._tx(write=True):
            memory._db.execute("CREATE TABLE IF NOT EXISTS checkpoint_import_outbox "
                               "(receipt_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, receipt TEXT NOT NULL, "
                               "delivered INTEGER NOT NULL, receipt_sha256 TEXT NOT NULL)")
            columns = {row[1] for row in memory._db.execute("PRAGMA table_info(checkpoint_import_outbox)")}
            if "receipt_sha256" not in columns:
                raise CheckpointError("legacy unsealed import outbox requires explicit migration")
            existing = memory._db.execute("SELECT * FROM checkpoint_import_outbox WHERE receipt_id=?", (identity,)).fetchone()
            if existing:
                if (existing["scope_key"] != memory._key(runtime.scope) or existing["delivered"] not in (0, 1)
                        or _sha(existing["receipt"].encode("utf-8")) != existing["receipt_sha256"]):
                    raise CheckpointError("immutable import outbox receipt integrity failed")
                receipt = _load(existing["receipt"])
                _validate_import_receipt(runtime, receipt, raw, digest, snapshot, payloads, source_ids, identity, matches)
                if existing["delivered"] and not matches:
                    raise CheckpointError("delivered import audit event is missing")
            else:
                if matches:
                    raise CheckpointError("journal import receipt exists without its immutable outbox")
                key = memory._key(runtime.scope)
                memory._verify_heads(key)
                source_map, revision_map = {}, {}
                ordinal = memory._db.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM memory_revisions WHERE scope_key=?", (key,)).fetchone()[0]
                origin = {"mode": "EVIDENCE_ONLY", "source_scope": snapshot["scope"], "archive_sha256": digest,
                          "authority_transferred": False}
                old_archive = memory._db.execute("SELECT revision_id FROM memory_heads WHERE scope_key=? AND source_id=?", (key, archive_source)).fetchone()
                if old_archive:
                    if memory._revision(key, old_archive[0])["content"] != raw:
                        raise CheckpointError("archive source collision")
                else:
                    memory._insert(runtime.scope, archive_source, raw, "application/zip", origin,
                                   ordinal=ordinal, version=1, predecessor=None, reason="evidence checkpoint import")
                    ordinal += 1
                for source in source_ids:
                    target = prefix + "source:" + source
                    source_map[source] = target
                    # An earlier selected-source import is reused only through its intact provenance.
                    old_head = memory._db.execute("SELECT revision_id FROM memory_heads WHERE scope_key=? AND source_id=?", (key, target)).fetchone()
                    source_rows = sorted((r for r in revisions if r["source_id"] == source), key=lambda r: r["version"])
                    if old_head:
                        current = memory._revision(key, old_head[0], allow_invalidated=True)
                        latest_original = _load(source_rows[-1]["manifest"])
                        if (current["provenance"].get("archive_sha256") != digest
                                or current["provenance"].get("source_manifest") != latest_original
                                or current["sha256"] != latest_original["sha256"]
                                or current["version"] != source_rows[-1]["version"]):
                            raise CheckpointError("imported source collision")
                        continue
                    previous = None
                    for row in source_rows:
                        original = _load(row["manifest"])
                        record = memory._insert(runtime.scope, target, payloads[row["content_entry"]], original["media_type"],
                            {**origin, "source_manifest": original, "source_record_sha256": row["record_sha256"]},
                            ordinal=ordinal, version=row["version"], predecessor=previous, reason="evidence checkpoint import")
                        previous = record["revision_id"]
                        revision_map[row["revision_id"]] = previous
                    ordinal += 1
                for invalidation in snapshot["memory"]["memory_invalidations"]:
                    mapped = revision_map.get(invalidation["object_id"])
                    if mapped:
                        memory._invalidate(key, mapped, "Imported source invalidation: " + invalidation["reason"])
                revision_map = _materialized_mapping(runtime, raw, digest, snapshot, payloads, source_ids)
                receipt = {"schema": "kch.composed.checkpoint-import-receipt.v1", "receipt_id": identity,
                           "mode": "EVIDENCE_ONLY", "source_scope": snapshot["scope"],
                           "destination_scope": asdict(runtime.scope), "archive_sha256": digest,
                           "archive_source_id": archive_source, "selected_sources": source_map,
                           "revision_mapping": revision_map, "authority_transferred": False,
                           "automatic_replay": False, "provider_binding_activated": False,
                           "folds_and_sessions": "PRESERVED_IN_ARCHIVE_NOT_ACTIVATED",
                           "imported_at": datetime.now(timezone.utc).isoformat()}
                memory._db.execute("INSERT INTO checkpoint_import_outbox VALUES (?,?,?,0,?)",
                                   (identity, key, _canonical_json(receipt), _seal(receipt)))
        try:
            _audit(runtime, receipt)
        except (CheckpointError, JournalIntegrityError):
            raise
        except Exception:
            # The memory transaction and audit intent survive. A repeat of this
            # exact import retries only audit delivery, never source materialization.
            return {**receipt, "audit_delivery": "PENDING_RETRY_IMPORT"}
        return {**receipt, "audit_delivery": "DELIVERED"}
