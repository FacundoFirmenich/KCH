from __future__ import annotations

import csv
import json
import re
import sqlite3
import uuid
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator
from xml.etree import ElementTree

from .contracts import canonical_json, sha256_json, sqlite_connection
from .recovery import RecoveryVault
from .universal_text import UniversalAssetStore

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_sha256 TEXT NOT NULL UNIQUE,
    media_type TEXT NOT NULL,
    parser TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    manifest_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS layers (
    layer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    rank INTEGER NOT NULL UNIQUE,
    purpose TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    record_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    layer_id TEXT NOT NULL REFERENCES layers(layer_id),
    record_type TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    locator_json TEXT NOT NULL,
    data_json TEXT NOT NULL,
    data_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(source_id,layer_id,ordinal)
);
CREATE TABLE IF NOT EXISTS tags (
    tag_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    definition TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS record_tags (
    record_id TEXT NOT NULL REFERENCES records(record_id),
    tag_id TEXT NOT NULL REFERENCES tags(tag_id),
    confidence REAL,
    method TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    PRIMARY KEY(record_id,tag_id,method)
);
CREATE TABLE IF NOT EXISTS tag_relations (
    parent_tag_id TEXT NOT NULL REFERENCES tags(tag_id),
    child_tag_id TEXT NOT NULL REFERENCES tags(tag_id),
    relation TEXT NOT NULL,
    rank INTEGER NOT NULL,
    PRIMARY KEY(parent_tag_id,child_tag_id,relation)
);
CREATE TABLE IF NOT EXISTS programs (
    program_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    revision INTEGER NOT NULL,
    enabled INTEGER NOT NULL,
    program_json TEXT NOT NULL,
    program_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watch_roots (
    watch_id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    recursive INTEGER NOT NULL,
    program_id TEXT,
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""

LAYER_SEED = [
    ("LAYER-RAW", "RAW_CUSTODY", 10, "Exact source bytes and provenance"),
    ("LAYER-PARSED", "PARSED", 20, "Parser output without semantic promotion"),
    ("LAYER-STRUCTURED", "STRUCTURED", 30, "Typed records and inferred schema"),
    ("LAYER-ENRICHED", "ENRICHED", 40, "Tags, relations, and program output"),
    ("LAYER-CURATED", "CURATED", 50, "User-approved archival and library organization"),
]

TOKEN = re.compile(r"[^\W\d_][\w-]{2,}", re.UNICODE)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def infer_scalar(value: Any) -> str:
    if value is None or value == "":
        return "NULL"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int) and not isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    text = str(value)
    if re.fullmatch(r"[-+]?\d+", text):
        return "INTEGER_TEXT"
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", text):
        return "REAL_TEXT"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ][^ ]+)?", text):
        return "TEMPORAL_TEXT"
    return "TEXT"


class KwanData:
    """Provenance-first heterogeneous structuring; distinct from KwanDocs evidence authority."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "kwandata.sqlite3"
        self.assets = UniversalAssetStore(self.root / "universal")
        self.vault = RecoveryVault(self.root / "recovery")
        with self.connect() as connection:
            connection.executescript(DDL)
            for row in LAYER_SEED:
                connection.execute("INSERT OR IGNORE INTO layers VALUES(?,?,?,?)", row)
            connection.commit()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _csv_rows(path: Path) -> Iterator[tuple[dict[str, Any], dict[str, Any], str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(
                stream, delimiter="\t" if path.suffix.lower() == ".tsv" else ","
            )
            if reader.fieldnames is None:
                return
            for number, row in enumerate(reader, start=2):
                yield dict(row), {"line": number, "columns": reader.fieldnames}, "TABULAR_ROW"

    @staticmethod
    def _json_rows(path: Path) -> Iterator[tuple[dict[str, Any], dict[str, Any], str]]:
        if path.suffix.lower() == ".jsonl":
            with path.open("r", encoding="utf-8-sig") as stream:
                for number, line in enumerate(stream, start=1):
                    if line.strip():
                        value = json.loads(line)
                        yield (
                            value if isinstance(value, dict) else {"value": value},
                            {"line": number},
                            "JSONL_RECORD",
                        )
            return
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        values = value if isinstance(value, list) else [value]
        for index, item in enumerate(values):
            yield (
                item if isinstance(item, dict) else {"value": item},
                {"json_index": index},
                "JSON_RECORD",
            )

    @staticmethod
    def _xml_rows(path: Path) -> Iterator[tuple[dict[str, Any], dict[str, Any], str]]:
        root = ElementTree.parse(path).getroot()
        for index, element in enumerate(list(root) or [root]):
            value = {
                "tag": element.tag,
                **{f"@{key}": item for key, item in element.attrib.items()},
            }
            for child in element:
                value[child.tag] = child.text or ""
            if element.text and element.text.strip():
                value["#text"] = element.text.strip()
            yield value, {"element_index": index, "tag": element.tag}, "XML_ELEMENT"

    @staticmethod
    def _sqlite_rows(path: Path) -> Iterator[tuple[dict[str, Any], dict[str, Any], str]]:
        uri = f"file:{path.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            tables = [
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            for table in tables:
                quoted = '"' + table.replace('"', '""') + '"'
                for rowid, row in enumerate(connection.execute(f"SELECT * FROM {quoted}"), start=1):
                    yield dict(row), {"table": table, "row_ordinal": rowid}, "SQLITE_ROW"
        finally:
            connection.close()

    @staticmethod
    def _text_rows(path: Path) -> Iterator[tuple[dict[str, Any], dict[str, Any], str]]:
        text = path.read_text(encoding="utf-8-sig")
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        for index, block in enumerate(blocks, start=1):
            heading = block.splitlines()[0].lstrip("# ") if block.startswith("#") else None
            yield {"text": block, "heading": heading}, {"block": index}, "TEXT_BLOCK"

    def _parser(
        self, path: Path
    ) -> tuple[str, Iterable[tuple[dict[str, Any], dict[str, Any], str]]]:
        suffix = path.suffix.lower()
        if suffix in {".csv", ".tsv"}:
            return "CSV_DICT", self._csv_rows(path)
        if suffix in {".json", ".jsonl"}:
            return "JSON", self._json_rows(path)
        if suffix == ".xml":
            return "XML", self._xml_rows(path)
        if suffix in {".sqlite", ".sqlite3", ".db"}:
            return "SQLITE_READ_ONLY", self._sqlite_rows(path)
        if suffix in {".txt", ".md", ".py", ".html", ".htm", ".tex", ".yaml", ".yml", ".toml"}:
            return "TEXT_BLOCKS", self._text_rows(path)
        return "BINARY_CUSTODY_ONLY", []

    def create_program(self, name: str, program: dict[str, Any]) -> dict[str, Any]:
        allowed = {"static_tags", "field_tag_map", "regex_tags", "collection", "layer_target"}
        unknown = set(program) - allowed
        if unknown:
            raise ValueError(f"unknown KwanData program keys: {sorted(unknown)}")
        for item in program.get("regex_tags", []):
            re.compile(item["pattern"])
        timestamp = utc_now()
        program_id = f"KDPROG-{uuid.uuid4()}"
        digest = sha256_json(program)
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO programs VALUES(?,?,?,?,?,?,?,?)",
                (program_id, name, 1, 1, canonical_json(program), digest, timestamp, timestamp),
            )
            connection.commit()
        custody = self.vault.save_json(
            f"programs/{program_id}.json",
            program,
            kind="KWANDATA_PROGRAM",
            actor="USER",
            operation="CREATE_PROGRAM",
        )
        return {
            "program_id": program_id,
            "name": name,
            "revision": 1,
            "program_hash": digest,
            "custody": custody,
        }

    def _ensure_tag(
        self,
        connection: sqlite3.Connection,
        name: str,
        *,
        kind: str,
        definition: str,
        created_by: str,
    ) -> str:
        normalized = re.sub(r"\s+", " ", name.strip().lower())
        if not normalized:
            raise ValueError("tag name cannot be empty")
        row = connection.execute("SELECT tag_id FROM tags WHERE name=?", (normalized,)).fetchone()
        if row:
            return str(row["tag_id"])
        tag_id = f"TAG-{uuid.uuid4()}"
        connection.execute(
            "INSERT INTO tags VALUES(?,?,?,?,?,?)",
            (tag_id, normalized, kind, definition, created_by, utc_now()),
        )
        return tag_id

    def _tag_record(
        self,
        connection: sqlite3.Connection,
        record_id: str,
        name: str,
        *,
        method: str,
        evidence: dict[str, Any],
        kind: str = "TAG",
    ) -> None:
        tag_id = self._ensure_tag(connection, name, kind=kind, definition="", created_by=method)
        connection.execute(
            "INSERT OR IGNORE INTO record_tags VALUES(?,?,?,?,?)",
            (record_id, tag_id, None, method, canonical_json(evidence)),
        )

    def ingest(self, source: str | Path, *, program_id: str | None = None) -> dict[str, Any]:
        path = Path(source).resolve()
        asset = self.assets.ingest(path)
        source_hash = asset["original"]["content_sha256"]
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM sources WHERE source_sha256=?", (source_hash,)
            ).fetchone()
            if existing:
                return {
                    "state": "DEDUPLICATED_BY_EXACT_SHA256",
                    "source_id": existing["source_id"],
                    "asset_id": existing["asset_id"],
                    "sha256": source_hash,
                }
        parser_name, rows = self._parser(path)
        program: dict[str, Any] = {}
        if program_id:
            with closing(self.connect()) as connection:
                row = connection.execute(
                    "SELECT * FROM programs WHERE program_id=? AND enabled=1", (program_id,)
                ).fetchone()
                if row is None:
                    raise KeyError(program_id)
                program = json.loads(str(row["program_json"]))
        source_id = f"SOURCE-{uuid.uuid4()}"
        timestamp = utc_now()
        record_count = 0
        field_types: dict[str, Counter[str]] = {}
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    source_id,
                    asset["asset_id"],
                    path.name,
                    source_hash,
                    asset["media_type"],
                    parser_name,
                    "INGESTING",
                    timestamp,
                    canonical_json(asset),
                ),
            )
            for ordinal, (data, locator, record_type) in enumerate(rows, start=1):
                record_id = f"RECORD-{uuid.uuid4()}"
                connection.execute(
                    "INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        record_id,
                        source_id,
                        "LAYER-STRUCTURED",
                        record_type,
                        ordinal,
                        canonical_json(locator),
                        canonical_json(data),
                        sha256_json(data),
                        timestamp,
                    ),
                )
                for field, value in data.items():
                    field_types.setdefault(str(field), Counter())[infer_scalar(value)] += 1
                self._tag_record(
                    connection,
                    record_id,
                    f"source:{path.suffix.lower().lstrip('.') or 'no-extension'}",
                    method="DETERMINISTIC_SOURCE_TYPE",
                    evidence={"suffix": path.suffix},
                )
                for field in data:
                    self._tag_record(
                        connection,
                        record_id,
                        f"field:{field}",
                        method="DETERMINISTIC_FIELD",
                        evidence={"field": field},
                    )
                text = " ".join(str(value) for value in data.values() if isinstance(value, str))
                keywords = Counter(token.lower() for token in TOKEN.findall(text))
                for token, count in keywords.most_common(8):
                    self._tag_record(
                        connection,
                        record_id,
                        token,
                        method="LEXICAL_FREQUENCY",
                        evidence={"count": count},
                    )
                for tag in program.get("static_tags", []):
                    self._tag_record(
                        connection,
                        record_id,
                        str(tag),
                        method="USER_PROGRAM_STATIC",
                        evidence={"program_id": program_id},
                    )
                for rule in program.get("regex_tags", []):
                    if re.search(rule["pattern"], text, flags=re.IGNORECASE):
                        self._tag_record(
                            connection,
                            record_id,
                            rule["tag"],
                            method="USER_PROGRAM_REGEX",
                            evidence={"pattern": rule["pattern"]},
                        )
                record_count += 1
            state = "STRUCTURED" if record_count else "CUSTODIED_UNPARSED"
            connection.execute("UPDATE sources SET state=? WHERE source_id=?", (state, source_id))
            connection.commit()
        schema = {
            field: {
                "observed_types": dict(sorted(counter.items())),
                "non_null_count": sum(value for key, value in counter.items() if key != "NULL"),
            }
            for field, counter in sorted(field_types.items())
        }
        receipt = {
            "schema": "kwandata.ingest-receipt.v0.1.0",
            "source_id": source_id,
            "asset_id": asset["asset_id"],
            "source_sha256": source_hash,
            "parser": parser_name,
            "state": state,
            "record_count": record_count,
            "inferred_schema": schema,
            "program_id": program_id,
            "source_original_retained": True,
            "KwanDocs_authority_inherited": False,
            "semantic_intelligence_claim": "DETERMINISTIC_STRUCTURE_AND_USER_PROGRAMS_ONLY",
        }
        self.vault.save_json(
            f"ingests/{source_id}.json",
            receipt,
            kind="KWANDATA_INGEST_RECEIPT",
            actor="KCH_SYSTEM",
            operation="SEAL_INGEST",
        )
        return receipt

    def create_supertag(
        self, name: str, children: list[str], *, relation: str = "CONTAINS"
    ) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            parent = self._ensure_tag(
                connection,
                name,
                kind="SUPERTAG",
                definition="User-defined supertag",
                created_by="USER",
            )
            child_ids = []
            for rank, child in enumerate(children, start=1):
                child_id = self._ensure_tag(
                    connection, child, kind="TAG", definition="", created_by="USER"
                )
                connection.execute(
                    "INSERT OR REPLACE INTO tag_relations VALUES(?,?,?,?)",
                    (parent, child_id, relation, rank),
                )
                child_ids.append(child_id)
            connection.commit()
        value = {
            "supertag_id": parent,
            "name": name,
            "relation": relation,
            "children": child_ids,
            "child_count": len(child_ids),
        }
        self.vault.save_json(
            f"supertags/{parent}.json",
            value,
            kind="KWANDATA_SUPERTAG",
            actor="USER",
            operation="CREATE_SUPERTAG",
        )
        return value

    def query(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """SELECT r.record_id,r.record_type,r.ordinal,r.data_json,r.locator_json,s.source_name,s.source_sha256
                FROM records r JOIN sources s USING(source_id)
                WHERE r.data_json LIKE ? OR EXISTS(
                  SELECT 1 FROM record_tags rt JOIN tags t USING(tag_id)
                  WHERE rt.record_id=r.record_id AND t.name LIKE ?
                ) ORDER BY s.created_at,r.ordinal LIMIT ?""",
                (pattern, pattern, limit),
            ).fetchall()
            return [
                {
                    **dict(row),
                    "data": json.loads(row["data_json"]),
                    "locator": json.loads(row["locator_json"]),
                }
                for row in rows
            ]

    def add_watch_root(
        self, path: str | Path, *, recursive: bool = True, program_id: str | None = None
    ) -> dict[str, Any]:
        root = Path(path).resolve()
        if not root.is_dir():
            raise NotADirectoryError(root)
        watch_id = f"WATCH-{uuid.uuid4()}"
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO watch_roots VALUES(?,?,?,?,?,?)",
                (watch_id, str(root), int(recursive), program_id, 1, utc_now()),
            )
            connection.commit()
        return {
            "watch_id": watch_id,
            "path": str(root),
            "recursive": recursive,
            "program_id": program_id,
            "automatic_pickup": True,
        }

    def scan_watch_root(self, watch_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM watch_roots WHERE watch_id=? AND enabled=1", (watch_id,)
            ).fetchone()
            if row is None:
                raise KeyError(watch_id)
        root = Path(row["path"])
        paths = root.rglob("*") if row["recursive"] else root.glob("*")
        results = []
        for path in sorted(
            (item for item in paths if item.is_file()), key=lambda item: str(item).lower()
        ):
            results.append(
                {"path": str(path), "receipt": self.ingest(path, program_id=row["program_id"])}
            )
        return {"watch_id": watch_id, "files_seen": len(results), "results": results}

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            counts = {
                "sources": connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
                "records": connection.execute("SELECT COUNT(*) FROM records").fetchone()[0],
                "tags": connection.execute("SELECT COUNT(*) FROM tags").fetchone()[0],
                "supertags": connection.execute(
                    "SELECT COUNT(*) FROM tags WHERE kind='SUPERTAG'"
                ).fetchone()[0],
                "programs": connection.execute("SELECT COUNT(*) FROM programs").fetchone()[0],
            }
        return {
            "schema": "kwandata.status.v0.1.0",
            **counts,
            "layers": [
                {"id": row[0], "name": row[1], "rank": row[2], "purpose": row[3]}
                for row in LAYER_SEED
            ],
            "KwanDocs_boundary": "KwanData structures and archives; it does not confer KwanDocs evidence authority.",
        }
