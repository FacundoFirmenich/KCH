"""Lossless, scoped memory with reproducible projections; no summarizing model.

Folding changes an index, never source bytes. SQLite stores original bytes and
immutable revisions, fold manifests and views. Invalidations are append-only
events propagated through explicit dependencies. Scope is a namespace boundary,
not an authentication service: callers must obtain it from their trusted session.
SHA-256 detects corruption; it does not authenticate a malicious database owner.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any
import uuid

try:
    from kch_mu_transmuter_scpp.canonical import canonical_json as _canonical_json
    CANONICAL_BACKEND = "kch_mu_transmuter_scpp.canonical"
except ImportError:
    CANONICAL_BACKEND = "stdlib-json-compatible"

    def _canonical_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)


class MemoryIntegrityError(RuntimeError):
    """Stored bytes, metadata, or dependency manifests failed verification."""


class MemoryInvalidatedError(ValueError):
    """A revision or projection no longer represents current source state."""


@dataclass(frozen=True, slots=True)
class Scope:
    principal: str
    workspace: str
    session: str

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"scope {name} must be a nonempty string")


def _scope(value: Scope | Mapping[str, str]) -> Scope:
    if isinstance(value, Scope):
        return value
    if isinstance(value, Mapping) and set(value) == {"principal", "workspace", "session"}:
        return Scope(**value)
    raise TypeError("scope must be Scope or exactly principal/workspace/session")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seal(value: Any) -> str:
    return _digest(_canonical_json(value).encode("utf-8"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class MemoryStore:
    """Thread-safe local persistence with transactions across concurrent stores.

    A source_id denotes a logical source within one scope. ``ingest`` is
    idempotent for identical content/type/provenance; corrections require
    ``supersede`` and retain the preceding revision. Recall across scopes is
    denied with the same KeyError as an absent identifier (no existence leak).
    """

    def __init__(self, path: str | Path, *, enable_fts: bool = True) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, timeout=30, isolation_level=None,
                                   check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=30000")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS memory_revisions (
          revision_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL,
          source_id TEXT NOT NULL, ordinal INTEGER NOT NULL, version INTEGER NOT NULL,
          content BLOB NOT NULL, manifest TEXT NOT NULL, record_sha256 TEXT NOT NULL,
          UNIQUE(scope_key,source_id,version)
        );
        CREATE TABLE IF NOT EXISTS memory_heads (
          scope_key TEXT NOT NULL, source_id TEXT NOT NULL,
          revision_id TEXT NOT NULL REFERENCES memory_revisions(revision_id),
          PRIMARY KEY(scope_key,source_id)
        );
        CREATE TABLE IF NOT EXISTS memory_folds (
          fold_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL,
          manifest TEXT NOT NULL, sha256 TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory_views (
          view_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL,
          manifest TEXT NOT NULL, text TEXT NOT NULL, sha256 TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory_dependencies (
          scope_key TEXT NOT NULL, parent_id TEXT NOT NULL, child_id TEXT NOT NULL,
          PRIMARY KEY(scope_key,parent_id,child_id)
        );
        CREATE INDEX IF NOT EXISTS memory_dependency_child
          ON memory_dependencies(scope_key,child_id);
        CREATE TABLE IF NOT EXISTS memory_invalidations (
          event_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, object_id TEXT NOT NULL,
          reason TEXT NOT NULL, caused_by TEXT NOT NULL, occurred_at TEXT NOT NULL,
          UNIQUE(scope_key,object_id)
        );
        CREATE INDEX IF NOT EXISTS memory_scope_order
          ON memory_revisions(scope_key,ordinal,version);
        """)
        self.fts_enabled = False
        if enable_fts:
            try:
                self._db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING "
                                 "fts5(scope_key UNINDEXED,revision_id UNINDEXED,"
                                 "source_id UNINDEXED,text)")
                self.fts_enabled = True
            except sqlite3.OperationalError as exc:
                if "no such module: fts5" not in str(exc).lower():
                    raise
        # An existing index can have been created with FTS disabled on a previous
        # writer; rebuilding at open is deterministic and repairs that projection.
        if self.fts_enabled:
            self.rebuild_index()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> MemoryStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @contextmanager
    def _tx(self, *, write: bool = False):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    @staticmethod
    def _key(scope: Scope) -> str:
        return _seal(asdict(scope))

    def _invalid(self, key: str, object_id: str) -> bool:
        return self._db.execute("SELECT 1 FROM memory_invalidations WHERE scope_key=? "
                                "AND object_id=?", (key, object_id)).fetchone() is not None

    def _revision(self, key: str, revision_id: str, *, allow_invalidated: bool = False) -> dict:
        row = self._db.execute("SELECT * FROM memory_revisions WHERE scope_key=? "
                               "AND revision_id=?", (key, revision_id)).fetchone()
        if row is None:
            raise KeyError("source unavailable in this scope")
        manifest = json.loads(row["manifest"])
        content = bytes(row["content"])
        if (_seal(manifest) != row["record_sha256"]
                or self._key(Scope(**manifest["scope"])) != key
                or manifest["revision_id"] != revision_id
                or manifest["source_id"] != row["source_id"]
                or manifest["sequence"] != row["ordinal"]
                or manifest["version"] != row["version"]
                or len(content) != manifest["byte_length"]
                or _digest(content) != manifest["sha256"]):
            raise MemoryIntegrityError(f"revision integrity failed: {revision_id}")
        invalid = self._invalid(key, revision_id)
        if invalid and not allow_invalidated:
            raise MemoryInvalidatedError(revision_id)
        return {**manifest, "record_sha256": row["record_sha256"], "content": content,
                "status": "INVALIDATED" if invalid else "CURRENT"}

    def _head(self, key: str, source_id: str) -> str:
        self._verify_heads(key)
        row = self._db.execute("SELECT revision_id FROM memory_heads WHERE scope_key=? "
                               "AND source_id=?", (key, source_id)).fetchone()
        if row is None:
            raise KeyError("source unavailable in this scope")
        return row[0]

    def _verify_heads(self, key: str) -> None:
        """A mutable index cannot silently hide or roll back immutable sources."""
        latest = self._db.execute(
            "SELECT r.source_id,r.revision_id FROM memory_revisions r "
            "WHERE r.scope_key=? AND r.version=(SELECT MAX(p.version) FROM memory_revisions p "
            "WHERE p.scope_key=r.scope_key AND p.source_id=r.source_id)", (key,)).fetchall()
        expected = {row["source_id"]: row["revision_id"] for row in latest}
        actual = {row["source_id"]: row["revision_id"] for row in self._db.execute(
            "SELECT source_id,revision_id FROM memory_heads WHERE scope_key=?", (key,))}
        if actual != expected:
            raise MemoryIntegrityError("source head projection differs from immutable revisions")

    def _current(self, key: str) -> list[dict]:
        self._verify_heads(key)
        rows = self._db.execute("SELECT r.revision_id FROM memory_heads h "
                               "JOIN memory_revisions r ON r.revision_id=h.revision_id "
                               "WHERE h.scope_key=? ORDER BY r.ordinal", (key,)).fetchall()
        return [self._revision(key, row[0]) for row in rows if not self._invalid(key, row[0])]

    def _insert(self, scope: Scope, source_id: str, content: bytes, media_type: str,
                provenance: Mapping | None, *, ordinal: int, version: int,
                predecessor: str | None, reason: str) -> dict:
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id must be nonempty")
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes; encoding must be chosen by the caller")
        if not isinstance(media_type, str) or not media_type.strip():
            raise ValueError("media_type must be explicit")
        if provenance is not None and not isinstance(provenance, Mapping):
            raise TypeError("provenance must be a mapping")
        key = self._key(scope)
        manifest = {"revision_id": _new_id("mrev"), "scope": asdict(scope),
                    "source_id": source_id, "sequence": ordinal, "version": version,
                    "sha256": _digest(content), "byte_length": len(content),
                    "media_type": media_type, "provenance": dict(provenance or {}),
                    "predecessor_revision_id": predecessor, "reason": reason,
                    "created_at": _now()}
        encoded = _canonical_json(manifest)
        self._db.execute("INSERT INTO memory_revisions VALUES (?,?,?,?,?,?,?,?)",
                         (manifest["revision_id"], key, source_id, ordinal, version,
                          content, encoded, _seal(manifest)))
        self._db.execute("INSERT INTO memory_heads VALUES (?,?,?) ON CONFLICT(scope_key,source_id) "
                         "DO UPDATE SET revision_id=excluded.revision_id",
                         (key, source_id, manifest["revision_id"]))
        self._index(key, manifest["revision_id"], source_id, content)
        return {**manifest, "record_sha256": _seal(manifest), "status": "CURRENT"}

    def _index(self, key: str, revision_id: str, source_id: str, content: bytes) -> None:
        # A lexical-reading connection must still maintain an index created by
        # another writer; otherwise simultaneous FTS readers could miss sources.
        index_exists = self.fts_enabled or self._db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='memory_fts' AND type='table'").fetchone()
        if index_exists:
            try:
                text = content.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                return
            self._db.execute("INSERT INTO memory_fts VALUES (?,?,?,?)",
                             (key, revision_id, source_id, text))

    def ingest(self, scope: Scope | Mapping[str, str], source_id: str, content: bytes,
               media_type: str = "text/plain", provenance: Mapping | None = None) -> dict:
        scope = _scope(scope)
        key = self._key(scope)
        with self._tx(write=True):
            self._verify_heads(key)
            old = self._db.execute("SELECT revision_id FROM memory_heads WHERE scope_key=? "
                                   "AND source_id=?", (key, source_id)).fetchone()
            if old:
                current = self._revision(key, old[0])
                if (current["content"] == content and current["media_type"] == media_type
                        and current["provenance"] == dict(provenance or {})):
                    return {k: v for k, v in current.items() if k != "content"}
                raise ValueError("source already exists; use supersede for a correction")
            ordinal = self._db.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM memory_revisions "
                                       "WHERE scope_key=?", (key,)).fetchone()[0]
            return self._insert(scope, source_id, content, media_type, provenance,
                                ordinal=ordinal, version=1, predecessor=None, reason="ingest")

    def recall(self, scope: Scope | Mapping[str, str], source_id: str, *,
               revision_id: str | None = None, allow_invalidated: bool = False) -> dict:
        key = self._key(_scope(scope))
        with self._tx():
            record = self._revision(key, revision_id or self._head(key, source_id),
                                    allow_invalidated=allow_invalidated)
            if record["source_id"] != source_id:
                raise KeyError("source unavailable in this scope")
            return record

    def _fold(self, key: str, fold_id: str, *, allow_invalidated: bool = False) -> dict:
        row = self._db.execute("SELECT * FROM memory_folds WHERE scope_key=? AND fold_id=?",
                               (key, fold_id)).fetchone()
        if row is None:
            raise KeyError("fold unavailable in this scope")
        manifest = json.loads(row["manifest"])
        if (_seal(manifest) != row["sha256"] or manifest["fold_id"] != fold_id
                or self._key(Scope(**manifest["scope"])) != key):
            raise MemoryIntegrityError(f"fold integrity failed: {fold_id}")
        invalid = self._invalid(key, fold_id)
        if invalid and not allow_invalidated:
            raise MemoryInvalidatedError(fold_id)
        return {"fold_id": fold_id, "manifest": manifest, "sha256": row["sha256"],
                "status": "INVALIDATED" if invalid else "CURRENT"}

    def fold(self, scope: Scope | Mapping[str, str], source_ids: Sequence[str]) -> dict:
        """Fold ordered contiguous current sources (or earlier fold IDs).

        Nesting preserves a hierarchical manifest and flattened leaf checksums.
        It neither edits history nor compresses/claims semantic understanding.
        """
        scope = _scope(scope)
        key = self._key(scope)
        if isinstance(source_ids, (str, bytes)) or not source_ids:
            raise ValueError("fold requires a nonempty ordered sequence")
        with self._tx(write=True):
            self._verify_heads(key)
            members, leaves = [], []
            for source_id in source_ids:
                # Explicit source names take precedence if a caller uses a fold-like name.
                row = self._db.execute("SELECT revision_id FROM memory_heads WHERE scope_key=? "
                                       "AND source_id=?", (key, source_id)).fetchone()
                if row:
                    record = self._revision(key, row[0])
                    leaf = {name: record[name] for name in
                            ("source_id", "revision_id", "sha256", "byte_length", "sequence")}
                    members.append({"kind": "source", **leaf})
                    leaves.append(leaf)
                else:
                    nested = self._fold(key, source_id)
                    members.append({"kind": "fold", "fold_id": source_id,
                                    "sha256": nested["sha256"]})
                    leaves.extend(nested["manifest"]["leaves"])
            current = self._current(key)
            positions = {r["revision_id"]: i for i, r in enumerate(current)}
            try:
                indices = [positions[leaf["revision_id"]] for leaf in leaves]
            except KeyError as exc:
                raise MemoryInvalidatedError("fold contains a noncurrent revision") from exc
            if indices != list(range(indices[0], indices[0] + len(indices))):
                raise ValueError("fold members must be distinct, ordered and contiguous")
            fold_id = _new_id("mfold")
            manifest = {"fold_id": fold_id, "scope": asdict(scope), "created_at": _now(),
                        "kind": "lossless-reference-fold", "members": members, "leaves": leaves,
                        "byte_length": sum(item["byte_length"] for item in leaves)}
            seal = _seal(manifest)
            self._db.execute("INSERT INTO memory_folds VALUES (?,?,?,?)",
                             (fold_id, key, _canonical_json(manifest), seal))
            dependencies = {leaf["revision_id"] for leaf in leaves}
            dependencies.update(m["fold_id"] for m in members if m["kind"] == "fold")
            self._db.executemany("INSERT INTO memory_dependencies VALUES (?,?,?)",
                                 [(key, fold_id, child) for child in sorted(dependencies)])
            return {"fold_id": fold_id, "manifest": manifest, "sha256": seal,
                    "status": "CURRENT"}

    def _unfold(self, key: str, fold_id: str, *, allow_invalidated: bool = False) -> list[dict]:
        fold = self._fold(key, fold_id, allow_invalidated=allow_invalidated)
        pending = [fold]
        visited = set()
        while pending:
            current = pending.pop()
            if current["fold_id"] in visited:
                continue
            visited.add(current["fold_id"])
            expanded = []
            for member in current["manifest"]["members"]:
                if member["kind"] == "fold":
                    nested = self._fold(key, member["fold_id"], allow_invalidated=allow_invalidated)
                    if nested["sha256"] != member["sha256"]:
                        raise MemoryIntegrityError("nested fold checksum differs")
                    expanded.extend(nested["manifest"]["leaves"])
                    pending.append(nested)
                elif member["kind"] == "source":
                    expanded.append({k: v for k, v in member.items() if k != "kind"})
                else:
                    raise MemoryIntegrityError("unknown fold member kind")
            if expanded != current["manifest"]["leaves"]:
                raise MemoryIntegrityError("hierarchical fold leaves differ")
        records = []
        for leaf in fold["manifest"]["leaves"]:
            record = self._revision(key, leaf["revision_id"], allow_invalidated=allow_invalidated)
            if any(record[field] != leaf[field] for field in leaf):
                raise MemoryIntegrityError("fold source metadata differs")
            records.append(record)
        return records

    def unfold(self, scope: Scope | Mapping[str, str], fold_id: str, *,
               allow_invalidated: bool = False) -> list[dict]:
        with self._tx():
            return self._unfold(self._key(_scope(scope)), fold_id,
                                allow_invalidated=allow_invalidated)

    def _invalidate(self, key: str, object_id: str, reason: str) -> list[str]:
        pending = [object_id]
        affected: list[str] = []
        seen: set[str] = set()
        while pending:
            item = pending.pop()
            if item in seen:
                continue
            seen.add(item)
            self._db.execute("INSERT OR IGNORE INTO memory_invalidations VALUES (?,?,?,?,?,?)",
                             (_new_id("minv"), key, item, reason, object_id, _now()))
            affected.append(item)
            pending.extend(row[0] for row in self._db.execute(
                "SELECT parent_id FROM memory_dependencies WHERE scope_key=? AND child_id=?",
                (key, item)))
        return sorted(affected)

    def invalidate(self, scope: Scope | Mapping[str, str], source_id: str, reason: str) -> dict:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("invalidation reason must be explicit")
        key = self._key(_scope(scope))
        with self._tx(write=True):
            revision_id = self._head(key, source_id)
            self._revision(key, revision_id, allow_invalidated=True)
            return {"source_id": source_id, "revision_id": revision_id,
                    "invalidated_ids": self._invalidate(key, revision_id, reason), "reason": reason}

    def supersede(self, scope: Scope | Mapping[str, str], source_id: str, content: bytes, *,
                  media_type: str = "text/plain", provenance: Mapping | None = None,
                  reason: str) -> dict:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("supersession reason must be explicit")
        scope = _scope(scope)
        key = self._key(scope)
        with self._tx(write=True):
            previous = self._revision(key, self._head(key, source_id), allow_invalidated=True)
            successor = self._insert(scope, source_id, content, media_type, provenance,
                                     ordinal=previous["sequence"], version=previous["version"] + 1,
                                     predecessor=previous["revision_id"], reason=reason)
            successor["invalidated_ids"] = self._invalidate(key, previous["revision_id"], reason)
            return successor

    def rebuild_index(self) -> dict:
        if not self.fts_enabled:
            return {"backend": "lexical", "indexed": 0}
        with self._tx(write=True):
            keys = {row[0] for row in self._db.execute("SELECT DISTINCT scope_key FROM memory_revisions")}
            keys.update(row[0] for row in self._db.execute("SELECT DISTINCT scope_key FROM memory_heads"))
            for key in keys:
                self._verify_heads(key)
            self._db.execute("DELETE FROM memory_fts")
            count = 0
            rows = self._db.execute("SELECT scope_key,revision_id FROM memory_heads").fetchall()
            for row in rows:
                if not self._invalid(row["scope_key"], row["revision_id"]):
                    record = self._revision(row["scope_key"], row["revision_id"])
                    self._index(row["scope_key"], row["revision_id"], record["source_id"], record["content"])
                    count += 1
            return {"backend": "fts5", "active_sources_checked": count,
                    "indexed": self._db.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0]}

    def search(self, scope: Scope | Mapping[str, str], query: str, *, limit: int = 20) -> list[dict]:
        """Literal word search, not embeddings or semantic/authority adjudication."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("search query must be nonempty")
        if type(limit) is not int or limit < 1 or limit > 1000:
            raise ValueError("limit must be an integer in [1,1000]")
        key = self._key(_scope(scope))
        with self._tx():
            self._verify_heads(key)
            if self.fts_enabled:
                match = " AND ".join('"' + word.replace('"', '""') + '"' for word in query.split())
                rows = self._db.execute("SELECT f.revision_id FROM memory_fts f "
                    "JOIN memory_heads h ON h.scope_key=f.scope_key AND h.revision_id=f.revision_id "
                    "WHERE memory_fts MATCH ? AND f.scope_key=? AND NOT EXISTS "
                    "(SELECT 1 FROM memory_invalidations i WHERE i.scope_key=f.scope_key "
                    "AND i.object_id=f.revision_id) ORDER BY bm25(memory_fts), f.revision_id LIMIT ?",
                    (match, key, limit)).fetchall()
                records = [self._revision(key, row[0]) for row in rows]
            else:
                words = query.casefold().split()
                records = []
                for record in self._current(key):
                    try:
                        haystack = record["content"].decode("utf-8", errors="strict").casefold()
                    except UnicodeDecodeError:
                        continue
                    if all(word in haystack for word in words):
                        records.append(record)
                        if len(records) == limit:
                            break
            return [{k: v for k, v in record.items() if k != "content"} for record in records]

    def view(self, scope: Scope | Mapping[str, str], *, max_bytes: int = 16384,
             max_chars: int | None = None, recent: int = 8) -> dict:
        """Persist a budgeted text projection, with references to every source.

        Budgets apply to returned ``text`` alone, in UTF-8 bytes / Unicode code
        points. Full metadata and the complete ``references`` list are out of
        band and must not be appended blindly to a prompt with that budget.
        Whole recent sources are included when they fit; none is truncated.
        Omitted bytes remain available through recall/unfold, never summarized.
        """
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("max_bytes must be a nonnegative integer")
        if max_chars is not None and (type(max_chars) is not int or max_chars < 0):
            raise ValueError("max_chars must be a nonnegative integer or None")
        if type(recent) is not int or recent < 0:
            raise ValueError("recent must be a nonnegative integer")
        scope = _scope(scope)
        key = self._key(scope)
        with self._tx(write=True):
            records = self._current(key)
            recent_records = records[-recent:] if recent else []
            old_ids = {r["revision_id"] for r in (records[:-recent] if recent else records)}
            folds = []
            for row in self._db.execute("SELECT fold_id FROM memory_folds WHERE scope_key=?", (key,)):
                if not self._invalid(key, row[0]):
                    fold = self._fold(key, row[0])
                    ids = {leaf["revision_id"] for leaf in fold["manifest"]["leaves"]}
                    if ids <= old_ids:
                        folds.append(fold)
            folds.sort(key=lambda f: (-len(f["manifest"]["leaves"]), f["fold_id"]))
            selected, covered = [], set()
            for fold in folds:
                ids = {leaf["revision_id"] for leaf in fold["manifest"]["leaves"]}
                if not (ids & covered):
                    self._unfold(key, fold["fold_id"])
                    selected.append(fold)
                    covered.update(ids)
            lines: list[str] = []
            included: set[str] = set()

            def append(block: str) -> bool:
                proposed = "\n\n".join([*lines, block])
                if len(proposed.encode("utf-8")) > max_bytes:
                    return False
                if max_chars is not None and len(proposed) > max_chars:
                    return False
                lines.append(block)
                return True

            # Most recent first allocates scarce space deterministically.
            for record in reversed(recent_records):
                try:
                    text = record["content"].decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    continue
                header = _canonical_json({"source_id": record["source_id"],
                                          "revision_id": record["revision_id"], "sha256": record["sha256"]})
                if append("[SOURCE " + header + "]\n" + text):
                    included.add(record["revision_id"])
            fold_refs = [{"kind": "fold", "fold_id": fold["fold_id"], "sha256": fold["sha256"],
                          "source_count": len(fold["manifest"]["leaves"]),
                          "byte_length": fold["manifest"]["byte_length"]} for fold in selected]
            for ref in fold_refs:
                append("[ARCHIVED " + _canonical_json(ref) + "]")
            refs = [{"kind": "source", "source_id": r["source_id"], "revision_id": r["revision_id"],
                     "sha256": r["sha256"], "byte_length": r["byte_length"],
                     "included_verbatim": r["revision_id"] in included,
                     "covered_by_fold": r["revision_id"] in covered} for r in records]
            text = "\n\n".join(lines)
            view_id = _new_id("mview")
            manifest = {"view_id": view_id, "scope": asdict(scope), "created_at": _now(),
                        "references": refs, "folds": fold_refs,
                        "budget": {"applies_to": "text_only", "max_utf8_bytes": max_bytes,
                                   "max_unicode_codepoints": max_chars, "recent": recent},
                        "used_utf8_bytes": len(text.encode("utf-8")), "used_chars": len(text),
                        "text_sha256": _digest(text.encode("utf-8")),
                        "omitted_source_count": len(records) - len(included),
                        "summarization": "none", "truncation": "none"}
            seal = _seal(manifest)
            self._db.execute("INSERT INTO memory_views VALUES (?,?,?,?,?)",
                             (view_id, key, _canonical_json(manifest), text, seal))
            children = [r["revision_id"] for r in records] + [f["fold_id"] for f in selected]
            self._db.executemany("INSERT INTO memory_dependencies VALUES (?,?,?)",
                                 [(key, view_id, child) for child in children])
            return {**manifest, "text": text, "sha256": seal, "status": "CURRENT"}

    def read_view(self, scope: Scope | Mapping[str, str], view_id: str, *,
                  allow_invalidated: bool = False) -> dict:
        key = self._key(_scope(scope))
        with self._tx():
            row = self._db.execute("SELECT * FROM memory_views WHERE scope_key=? AND view_id=?",
                                   (key, view_id)).fetchone()
            if row is None:
                raise KeyError("view unavailable in this scope")
            manifest = json.loads(row["manifest"])
            if (_seal(manifest) != row["sha256"] or manifest["view_id"] != view_id
                    or self._key(Scope(**manifest["scope"])) != key
                    or _digest(row["text"].encode("utf-8")) != manifest["text_sha256"]):
                raise MemoryIntegrityError("view integrity failed")
            invalid = self._invalid(key, view_id)
            if invalid and not allow_invalidated:
                raise MemoryInvalidatedError(view_id)
            # Check references too, not merely the bytes of the cached view.
            for ref in manifest["references"]:
                record = self._revision(key, ref["revision_id"], allow_invalidated=allow_invalidated)
                if record["sha256"] != ref["sha256"]:
                    raise MemoryIntegrityError("view source checksum differs")
            for ref in manifest["folds"]:
                fold = self._fold(key, ref["fold_id"], allow_invalidated=allow_invalidated)
                if fold["sha256"] != ref["sha256"]:
                    raise MemoryIntegrityError("view fold checksum differs")
                self._unfold(key, ref["fold_id"], allow_invalidated=allow_invalidated)
            return {**manifest, "text": row["text"], "sha256": row["sha256"],
                    "status": "INVALIDATED" if invalid else "CURRENT"}
