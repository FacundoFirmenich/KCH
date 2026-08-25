from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULTS = {
    "locks_enabled": "false",
    "startup_notice": "true",
    "response_mode": "explanatory",
    "persist_exact_inputs": "true",
    "native_first": "true",
    "phl_authorized": "true",
    "phl_training": "false",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def data_dir() -> Path:
    raw = os.environ.get("KCH_NATIVE_DATA")
    if raw:
        root = Path(raw)
    else:
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "KCH" / "NativeR21"
    root.mkdir(parents=True, exist_ok=True)
    return root


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(data_dir() / "kch_native_r21.sqlite", timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=10000")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          event_name TEXT NOT NULL,
          session_id TEXT,
          turn_id TEXT,
          payload_sha256 TEXT NOT NULL,
          payload_json TEXT,
          previous_hash TEXT NOT NULL,
          event_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS locks(
          id TEXT PRIMARY KEY,
          kind TEXT NOT NULL CHECK(kind IN ('EXACT','PREFIX','GLOB')),
          pattern TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          disabled_at TEXT
        );
        CREATE TABLE IF NOT EXISTS proposals(
          id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          session_id TEXT NOT NULL,
          turn_id TEXT,
          tool_name TEXT NOT NULL,
          args_sha256 TEXT NOT NULL,
          resources_json TEXT NOT NULL,
          tool_input_json TEXT NOT NULL,
          reason TEXT NOT NULL DEFAULT '',
          impact TEXT NOT NULL DEFAULT '',
          recovery TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'DRAFT'
        );
        CREATE UNIQUE INDEX IF NOT EXISTS proposal_exact_attempt
          ON proposals(session_id, tool_name, args_sha256, status)
          WHERE status IN ('DRAFT','PROPOSED','AUTHORIZED');
        CREATE TABLE IF NOT EXISTS authorizations(
          proposal_id TEXT PRIMARY KEY REFERENCES proposals(id),
          session_id TEXT NOT NULL,
          args_sha256 TEXT NOT NULL,
          authorized_at TEXT NOT NULL,
          consumed_at TEXT,
          consumed_tool_use_id TEXT
        );
        CREATE TABLE IF NOT EXISTS session_state(
          session_id TEXT PRIMARY KEY,
          governing_prompt TEXT,
          governing_prompt_sha256 TEXT,
          persistence_required INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        """
    )
    lock_columns = {row[1] for row in db.execute("PRAGMA table_info(locks)")}
    if "baseline_sha256" not in lock_columns:
        db.execute("ALTER TABLE locks ADD COLUMN baseline_sha256 TEXT")
    now = utc_now()
    for key, value in DEFAULTS.items():
        db.execute(
            "INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES(?,?,?)",
            (key, value, now),
        )
    db.commit()
    return db


def setting(db: sqlite3.Connection, key: str) -> str:
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else DEFAULTS.get(key, "")


def set_setting(db: sqlite3.Connection, key: str, value: str) -> None:
    db.execute(
        "INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, utc_now()),
    )
    db.commit()


def log_event(db: sqlite3.Connection, event_name: str, payload: dict[str, Any]) -> str:
    exact = canonical(payload)
    payload_sha = sha256_text(exact)
    db.execute("BEGIN IMMEDIATE")
    previous = db.execute("SELECT event_hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
    previous_hash = previous[0] if previous else "0" * 64
    created = utc_now()
    material = canonical(
        {
            "created_at": created,
            "event_name": event_name,
            "session_id": payload.get("session_id"),
            "turn_id": payload.get("turn_id"),
            "payload_sha256": payload_sha,
            "previous_hash": previous_hash,
        }
    )
    event_hash = sha256_text(material)
    stored = exact if setting(db, "persist_exact_inputs") == "true" else None
    db.execute(
        "INSERT INTO events(created_at,event_name,session_id,turn_id,payload_sha256,payload_json,previous_hash,event_hash) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (
            created,
            event_name,
            payload.get("session_id"),
            payload.get("turn_id"),
            payload_sha,
            stored,
            previous_hash,
            event_hash,
        ),
    )
    db.commit()
    return event_hash


def normalize_file(raw: str, cwd: str) -> str:
    value = raw.strip().strip('"\'')
    path = Path(value)
    if not path.is_absolute():
        path = Path(cwd) / path
    try:
        path = path.resolve(strict=False)
    except OSError:
        path = path.absolute()
    return "file:" + os.path.normcase(str(path))


def _walk_paths(value: Any, cwd: str, parent_key: str = "") -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_paths(child, cwd, str(key).lower())
    elif isinstance(value, list):
        for child in value:
            yield from _walk_paths(child, cwd, parent_key)
    elif isinstance(value, str) and parent_key in {
        "path", "file", "file_path", "filepath", "file_uri", "workdir", "cwd", "destination"
    }:
        if not re.match(r"^[a-z]+://", value, re.I):
            yield normalize_file(value, cwd)


SHELL_PATH_ARGUMENT = re.compile(
    r"(?i)(?:^|\s)-(?:LiteralPath|Path|Destination|DestinationPath|FilePath|"
    r"WorkingDirectory|OutFile)\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s;|&]+))"
)
QUOTED_RELATIVE_PATH = re.compile(r"(?:\"([^\"]*[\\/][^\"]*)\"|'([^']*[\\/][^']*)')")


def _shell_paths(command: str, cwd: str) -> Iterable[str]:
    """Extract absolute and relative filesystem operands from shell text.

    Constitutional matching must not depend on callers spelling a protected
    target as an absolute path. PowerShell path-bearing parameters are parsed
    explicitly; other quoted strings containing a separator are retained as a
    conservative fallback. False positives can block, but can never authorize.
    """

    for match in SHELL_PATH_ARGUMENT.finditer(command):
        raw = next((group for group in match.groups() if group is not None), "")
        if raw and not re.match(r"^[a-z]+://", raw, re.I):
            yield normalize_file(raw, cwd)
    for match in QUOTED_RELATIVE_PATH.finditer(command):
        raw = next((group for group in match.groups() if group is not None), "")
        if raw and not re.match(r"^[a-z]+://", raw, re.I):
            yield normalize_file(raw, cwd)


def extract_resources(tool_name: str, tool_input: Any, cwd: str) -> list[str]:
    resources = {"tool:" + tool_name.casefold()}
    resources.update(_walk_paths(tool_input, cwd))
    command = (
        tool_input.get("command", "")
        if isinstance(tool_input, dict)
        else tool_input
        if isinstance(tool_input, str)
        else ""
    )
    if tool_name == "apply_patch" or "*** Begin Patch" in command:
        for match in re.finditer(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", command, re.M):
            resources.add(normalize_file(match.group(1), cwd))
    resources.update(_shell_paths(command, cwd))
    for match in re.finditer(r"(?i)(?:[A-Z]:\\[^\r\n\"'|<>]+|/[A-Za-z0-9_./ -]+)", command):
        candidate = match.group(0).strip()
        if candidate and not candidate.startswith("//"):
            resources.add(normalize_file(candidate, cwd))
    return sorted(resources)


READ_ONLY_TOOLS = {
    "find",
    "get_goal",
    "list_mcp_resource_templates",
    "list_mcp_resources",
    "read_mcp_resource",
    "view_image",
}
MUTATING_TOOLS = {"apply_patch"}
SIMPLE_READ_COMMANDS = {
    "get-content",
    "get-filehash",
    "get-item",
    "get-childitem",
    "measure-object",
    "resolve-path",
    "select-string",
    "test-path",
    "rg",
}
READ_ONLY_GIT_SUBCOMMANDS = {"diff", "log", "show", "status"}


def classify_tool_operation(tool_name: str, tool_input: Any) -> str:
    """Conservatively separate attested simple reads from mutation.

    UNKNOWN deliberately remains subject to constitutional lock matching.  The
    classifier never treats an arbitrary shell, script, pipeline, assignment or
    redirection as read-only merely because its prose sounds non-mutating.
    """

    name = tool_name.casefold().replace("-", "_").split("__")[-1].split(".")[-1]
    if name in READ_ONLY_TOOLS or name.startswith("list_") or name.startswith("read_"):
        return "READ"
    if name in MUTATING_TOOLS:
        return "MUTATE"
    if name not in {"shell_command", "exec_command"} or not isinstance(tool_input, dict):
        return "UNKNOWN"
    command = str(tool_input.get("command", "")).strip()
    if not command or any(token in command for token in ("\r", "\n", ";", "|", "&", ">", "<", "`", "$(")):
        return "UNKNOWN"
    words = command.split()
    head = words[0].strip('"\'').casefold()
    if head in SIMPLE_READ_COMMANDS:
        return "READ"
    if head == "git" and len(words) > 1 and words[1].casefold() in READ_ONLY_GIT_SUBCOMMANDS:
        return "READ"
    return "UNKNOWN"


def lock_matches(kind: str, pattern: str, resource: str) -> bool:
    left = os.path.normcase(resource)
    right = os.path.normcase(pattern)
    if kind == "EXACT":
        return left == right
    if kind == "PREFIX":
        return left.startswith(right)
    return fnmatch.fnmatchcase(left, right)


def matching_locks(db: sqlite3.Connection, resources: list[str]) -> list[sqlite3.Row]:
    rows = db.execute("SELECT * FROM locks WHERE enabled=1 ORDER BY created_at,id").fetchall()
    return [row for row in rows if any(lock_matches(row["kind"], row["pattern"], r) for r in resources)]


def find_or_create_proposal(
    db: sqlite3.Connection,
    session_id: str,
    turn_id: str | None,
    tool_name: str,
    tool_input: Any,
    resources: list[str],
) -> sqlite3.Row:
    args_json = canonical(tool_input)
    args_sha = sha256_text(args_json)
    db.execute("BEGIN IMMEDIATE")
    row = db.execute(
        "SELECT * FROM proposals WHERE session_id=? AND tool_name=? AND args_sha256=? "
        "AND status IN ('DRAFT','PROPOSED','AUTHORIZED') ORDER BY created_at DESC LIMIT 1",
        (session_id, tool_name, args_sha),
    ).fetchone()
    if row:
        db.commit()
        return row
    proposal_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO proposals(id,created_at,session_id,turn_id,tool_name,args_sha256,resources_json,tool_input_json) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (proposal_id, utc_now(), session_id, turn_id, tool_name, args_sha, canonical(resources), args_json),
    )
    db.commit()
    return db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()


def consume_authorization(
    db: sqlite3.Connection,
    session_id: str,
    tool_name: str,
    args_sha: str,
    tool_use_id: str,
) -> str | None:
    db.execute("BEGIN IMMEDIATE")
    row = db.execute(
        "SELECT a.proposal_id FROM authorizations a JOIN proposals p ON p.id=a.proposal_id "
        "WHERE a.session_id=? AND p.tool_name=? AND a.args_sha256=? AND a.consumed_at IS NULL "
        "ORDER BY a.authorized_at LIMIT 1",
        (session_id, tool_name, args_sha),
    ).fetchone()
    if not row:
        db.rollback()
        return None
    now = utc_now()
    changed = db.execute(
        "UPDATE authorizations SET consumed_at=?, consumed_tool_use_id=? "
        "WHERE proposal_id=? AND consumed_at IS NULL",
        (now, tool_use_id, row[0]),
    ).rowcount
    if changed != 1:
        db.rollback()
        return None
    db.execute("UPDATE proposals SET status='CONSUMED' WHERE id=?", (row[0],))
    db.commit()
    return row[0]


def verify_chain(db: sqlite3.Connection) -> tuple[bool, int]:
    previous = "0" * 64
    count = 0
    for row in db.execute("SELECT * FROM events ORDER BY id"):
        material = canonical(
            {
                "created_at": row["created_at"],
                "event_name": row["event_name"],
                "session_id": row["session_id"],
                "turn_id": row["turn_id"],
                "payload_sha256": row["payload_sha256"],
                "previous_hash": previous,
            }
        )
        if row["previous_hash"] != previous or row["event_hash"] != sha256_text(material):
            return False, count
        previous = row["event_hash"]
        count += 1
    return True, count
