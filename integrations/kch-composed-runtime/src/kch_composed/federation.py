"""Audited, host-bound federation with the original KCH SuperMCP process.

Discovery is not permission. No server instructions are promoted to authority.
The subprocess is a transport boundary, not an operating-system sandbox.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from typing import Any, Callable


class FederationDenied(ValueError):
    """The request was rejected before transport dispatch."""


class FederationUncertain(RuntimeError):
    """Delivery/result is uncertain; automatic replay is forbidden."""


class FederationProtocolError(RuntimeError):
    pass


SCHEMA = "kch.composed.federation-host.v1"
STUDIO = "construct_successors/KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2/vendor/kch-studio-0.3.16/src"
BASE = "work/KCH_0.11_REEXTRACT_FINAL/src"
HOST_ONLY_ARGUMENTS = frozenset({"actor", "principal", "session", "session_id", "workspace",
    "workspace_root", "runtime_root", "data_dir", "authority", "authority_granted",
    "permissions", "authorization", "authorized", "user_authorized", "system_authority",
    "consent", "consent_basis", "authorization_id", "lock_authorization_id", "human_authorized",
    "confirmed_by_user", "user_authored", "granted_authority", "authority_inherited",
    "authority_after_loss", "authority_source", "actor_pattern", "scope", "scopes",
    "scope_type", "scope_key", "public_session_id", "workspace_id"})


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _loads(raw):
    return json.loads(raw, parse_constant=_reject_constant, object_pairs_hook=_object)


def _reject_host_arguments(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.casefold().replace("-", "_") in HOST_ONLY_ARGUMENTS:
                raise FederationDenied("Identity, scope and authority arguments must be bound by the host")
            _reject_host_arguments(item)
    elif isinstance(value, list):
        for item in value:
            _reject_host_arguments(item)


def _validator(schema):
    try:
        from jsonschema.validators import validator_for
    except ImportError as exc:
        raise FederationDenied("Install kch-composed-runtime[federation] for JSON Schema validation") from exc
    # Remote references must never perform ambient network or file access.
    def check(item):
        if isinstance(item, dict):
            for key, value in item.items():
                if key in {"$ref", "$dynamicRef", "$recursiveRef"} and (not isinstance(value, str) or not value.startswith("#")):
                    raise FederationDenied("External schema references are forbidden")
                check(value)
        elif isinstance(item, list):
            for value in item:
                check(value)
    check(schema)
    cls = validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def kch_config(repository, workspace, state_dir, principal, session, allowed_tools, *, namespace="kch", timeout_seconds=30, max_message_bytes=8 * 1024 * 1024):
    """Build an explicit host configuration; never writes or grants authority."""
    return {"schema": SCHEMA, "namespace": namespace, "repository": str(Path(repository).resolve()),
            "workspace": str(Path(workspace).resolve()), "state_dir": str(Path(state_dir).resolve()),
            "principal": principal, "session": session, "allowed_tools": deepcopy(allowed_tools),
            "timeout_seconds": timeout_seconds, "max_message_bytes": max_message_bytes}


def _stage_governance(source: Path, destination: Path):
    """Recover exact lock bytes after Git EOL conversion, never recompute a lock."""
    lock = _loads((source / "governance.lock.json").read_text())
    # Atomic directory install also avoids exposing partly prepared governance.
    if not destination.exists():
        temporary = destination.with_name(destination.name + "." + os.urandom(8).hex())
        shutil.copytree(source, temporary)
        try:
            for artifact in lock["artifacts"]:
                path = (temporary / artifact["path"]).resolve()
                if not path.is_relative_to(temporary.resolve()) or not path.is_file():
                    raise FederationDenied("Governance artifact path is invalid")
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
                    restored = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                    if hashlib.sha256(restored).hexdigest() != artifact["sha256"]:
                        raise FederationDenied("Governance source does not match its original lock")
                    path.write_bytes(restored)
            try:
                temporary.rename(destination)
            except FileExistsError:
                pass
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    for artifact in lock["artifacts"]:
        path = (destination / artifact["path"]).resolve()
        if not path.is_relative_to(destination.resolve()) or not path.is_file():
            raise FederationDenied("Prepared governance artifact is missing")
        data = path.read_bytes()
        if len(data) != artifact["bytes"] or hashlib.sha256(data).hexdigest() != artifact["sha256"]:
            raise FederationDenied("Prepared governance artifact failed original lock verification")
    # The original runtime separately validates source nodes and graph semantics.
    return {"lock_sha256": hashlib.sha256((source / "governance.lock.json").read_bytes()).hexdigest(),
            "locked_artifacts_verified": len(lock["artifacts"])}


class _Stdio:
    def __init__(self, command, *, cwd, env, timeout, max_bytes):
        self.timeout, self.max_bytes = timeout, max_bytes
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self.responses = queue.Queue(maxsize=64)
        self.stderr_tail = bytearray()
        self.lock = threading.Lock()
        self.counter = 0
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._drain_errors, daemon=True).start()

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(self.max_bytes + 1)
                if not line:
                    raise FederationProtocolError("MCP child exited before response")
                if len(line) > self.max_bytes or not line.endswith(b"\n"):
                    raise FederationProtocolError("MCP message exceeds transport bound")
                value = _loads(line)
                if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
                    raise FederationProtocolError("Invalid JSON-RPC envelope")
                self.responses.put(value, timeout=self.timeout)
        except Exception as exc:
            try:
                self.responses.put(exc, timeout=self.timeout)
            except queue.Full:
                self.process.kill()

    def _drain_errors(self):
        try:
            while True:
                chunk = self.process.stderr.read(4096)
                if not chunk:
                    return
                self.stderr_tail.extend(chunk)
                del self.stderr_tail[:-8192]
        except (ValueError, OSError):
            return  # The host closed the process and its streams.

    def _send(self, value):
        data = (_json(value) + "\n").encode()
        if len(data) > self.max_bytes:
            raise FederationDenied("MCP request exceeds transport bound")
        done = queue.Queue(maxsize=1)
        def write():
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
                done.put(None)
            except Exception as exc:
                done.put(exc)
        threading.Thread(target=write, daemon=True).start()
        try:
            result = done.get(timeout=self.timeout)
        except queue.Empty as exc:
            self.close()
            raise FederationUncertain("MCP write deadline exceeded") from exc
        if result is not None:
            raise result

    def notify(self, method):
        with self.lock:
            self._send({"jsonrpc": "2.0", "method": method})

    def request(self, method, params=None):
        with self.lock:
            self.counter += 1
            ident = self.counter
            self._send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}})
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    value = self.responses.get(timeout=max(0.001, deadline - time.monotonic()))
                except queue.Empty as exc:
                    self.close()
                    raise FederationUncertain("MCP response deadline exceeded") from exc
                if isinstance(value, Exception):
                    raise value
                if "method" in value:
                    if "id" in value:
                        # No sampling, elicitation or authority delegated to child.
                        self._send({"jsonrpc": "2.0", "id": value["id"], "error": {"code": -32601, "message": "Client requests are not enabled"}})
                    if time.monotonic() >= deadline:
                        raise FederationUncertain("MCP notification stream exceeded deadline")
                    continue
                if value.get("id") != ident:
                    raise FederationProtocolError("MCP response identity mismatch")
                if ("result" in value) == ("error" in value):
                    raise FederationProtocolError("Ambiguous MCP response")
                if "error" in value:
                    raise FederationProtocolError("MCP server returned an error: " + _json(value["error"]))
                return value["result"]

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream:
                stream.close()


class FederationBridge:
    def __init__(self, config: dict, audit_path: Path, *, authorize: Callable[[dict], bool] | None = None):
        self._config = _loads(_json(config))
        c = self._config
        expected = {"schema", "namespace", "repository", "workspace", "state_dir", "principal", "session", "allowed_tools", "timeout_seconds", "max_message_bytes"}
        if set(c) - expected or c.get("schema") != SCHEMA:
            raise FederationDenied("Unsupported federation host configuration")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,23}", c.get("namespace", "")):
            raise FederationDenied("Namespace must contain 1–24 safe identifier characters")
        if any(not isinstance(c.get(k), str) or not c[k] for k in ("principal", "session", "workspace", "repository", "state_dir")):
            raise FederationDenied("Host scope and paths must be explicit")
        for k in ("repository", "workspace", "state_dir"):
            if not Path(c[k]).is_absolute():
                raise FederationDenied("Host paths must be absolute")
            c[k] = str(Path(c[k]).resolve())
        if not Path(c["workspace"]).is_dir() or not Path(c["repository"]).is_dir():
            raise FederationDenied("Host repository/workspace is absent")
        timeout = c.setdefault("timeout_seconds", 30)
        max_bytes = c.setdefault("max_message_bytes", 8 * 1024 * 1024)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 300:
            raise FederationDenied("Invalid transport timeout")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 1024 <= max_bytes <= 64 * 1024 * 1024:
            raise FederationDenied("Invalid transport byte limit")
        if not isinstance(c.get("allowed_tools"), dict):
            raise FederationDenied("Explicit tool policy map is required")
        for name, policy in c["allowed_tools"].items():
            if not isinstance(name, str) or not name or not isinstance(policy, dict) or set(policy) - {"read_only", "fixed_arguments", "argument_schema"}:
                raise FederationDenied("Invalid host tool policy")
            if type(policy.get("read_only")) is not bool or not isinstance(policy.setdefault("fixed_arguments", {}), dict):
                raise FederationDenied("Policy requires boolean read_only and object fixed_arguments")
            if "argument_schema" in policy:
                _validator(policy["argument_schema"])
            if not policy["read_only"] and authorize is None:
                raise FederationDenied("Mutating federation requires a trusted host authorizer")
        self._authorize = authorize
        self._client = None
        self._catalog = None
        self._aliases = {}
        self._lock = threading.RLock()
        self._config_hash = _hash(c)
        self._audit = Path(audit_path).resolve()
        self._audit.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS federation_calls(
              binding TEXT,call_id TEXT,request_hash TEXT,status TEXT,response TEXT,
              PRIMARY KEY(binding,call_id));
              CREATE TABLE IF NOT EXISTS federation_events(
              sequence INTEGER PRIMARY KEY,body TEXT,previous_hash TEXT,event_hash TEXT);
              CREATE TABLE IF NOT EXISTS federation_head(
              singleton INTEGER PRIMARY KEY CHECK(singleton=1),sequence INTEGER,event_hash TEXT);""")
            if db.execute("SELECT 1 FROM federation_head WHERE singleton=1").fetchone() is None:
                if db.execute("SELECT 1 FROM federation_events LIMIT 1").fetchone():
                    raise FederationDenied("Federation audit head is absent for existing events")
                db.execute("INSERT INTO federation_head VALUES(1,0,?)", ("0" * 64,))

    @classmethod
    def from_config(cls, config, audit_path, **kwargs):
        return cls(config, audit_path, **kwargs)

    def _db(self):
        db = sqlite3.connect(self._audit, timeout=30)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _event(self, db, kind, payload):
        previous = db.execute("SELECT sequence,event_hash FROM federation_events ORDER BY sequence DESC LIMIT 1").fetchone()
        previous = previous or (0, "0" * 64)
        persisted = db.execute("SELECT sequence,event_hash FROM federation_head WHERE singleton=1").fetchone()
        if persisted != previous:
            raise FederationDenied("Federation audit head differs from retained event history")
        previous_hash = previous[1]
        body = {"kind": kind, "timestamp": datetime.now(timezone.utc).isoformat(),
                "config_hash": self._config_hash, **payload}
        event_hash = _hash({"previous_hash": previous_hash, "body": body})
        db.execute("INSERT INTO federation_events(sequence,body,previous_hash,event_hash) VALUES(?,?,?,?)", (previous[0] + 1, _json(body), previous_hash, event_hash))
        db.execute("UPDATE federation_head SET sequence=?,event_hash=? WHERE singleton=1", (previous[0] + 1, event_hash))
        return event_hash

    def _start(self):
        if self._client is not None:
            return
        c = self._config
        repository, state = Path(c["repository"]), Path(c["state_dir"])
        state.mkdir(parents=True, exist_ok=True)
        # A state directory cannot silently be reused by another authority scope.
        marker = state / "composed-federation-binding.json"
        try:
            with marker.open("x") as handle:
                handle.write(_json({"config_sha256": self._config_hash}))
        except FileExistsError:
            if _loads(marker.read_text()) != {"config_sha256": self._config_hash}:
                raise FederationDenied("Federation state belongs to a different host binding")
        governance = state / "locked_governance"
        self._governance = _stage_governance(repository / STUDIO / "kch_studio/data/governance", governance)
        home = state / "home"
        home.mkdir(exist_ok=True)
        env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": os.pathsep.join(map(str, [repository / STUDIO, repository / BASE,
                   *sorted((repository / BASE).parent.joinpath("vendor").glob("*-py3-none-any.whl"))])),
               "HOME": str(home), "KCH_STUDIO_RUNTIME": str(state / "super_mcp"),
               "KCH_GOVERNANCE_DIST": str(governance)}
        self._client = _Stdio([sys.executable, "-m", "kch_studio.super_mcp_overlay"], cwd=c["workspace"],
                              env=env, timeout=c["timeout_seconds"], max_bytes=c["max_message_bytes"])
        try:
            self._server = self._client.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "kch-composed-federation", "version": "0.2.0"}})
            if self._server.get("protocolVersion") != "2025-06-18":
                raise FederationProtocolError("Unsupported negotiated MCP version")
            self._client.notify("notifications/initialized")
        except Exception:
            self.close()
            raise

    def discover(self):
        with self._lock:
            if self._catalog is not None:
                return deepcopy(self._catalog)
            self._start()
            catalog, cursors, cursor = [], set(), None
            while True:
                page = self._client.request("tools/list", {"cursor": cursor} if cursor else {})
                if not isinstance(page, dict) or not isinstance(page.get("tools"), list):
                    raise FederationProtocolError("Invalid tools/list result")
                catalog.extend(page["tools"])
                if len(catalog) > 10000:
                    raise FederationProtocolError("Catalog exceeds host bound")
                cursor = page.get("nextCursor")
                if not cursor:
                    break
                if not isinstance(cursor, str) or cursor in cursors:
                    raise FederationProtocolError("Invalid catalog pagination")
                cursors.add(cursor)
            names = set()
            for descriptor in catalog:
                if not isinstance(descriptor, dict) or not isinstance(descriptor.get("name"), str) or descriptor["name"] in names:
                    raise FederationProtocolError("Invalid or duplicate canonical tool name")
                names.add(descriptor["name"])
                _validator(descriptor.get("inputSchema", {}))
                alias = self._config["namespace"] + "_" + hashlib.sha256(descriptor["name"].encode()).hexdigest()[:32]
                if alias in self._aliases:
                    raise FederationProtocolError("Federation alias collision")
                self._aliases[alias] = descriptor
            if set(self._config["allowed_tools"]) - names:
                raise FederationDenied("Host allowlist contains unavailable canonical tools")
            for descriptor in catalog:
                policy = self._config["allowed_tools"].get(descriptor["name"])
                if policy and policy["read_only"] and descriptor.get("annotations", {}).get("readOnlyHint") is not True:
                    raise FederationDenied("Read-only host policy requires upstream read-only annotation")
            self._catalog = catalog
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                self._event(db, "DISCOVERED", {"catalog_sha256": _hash(catalog), "count": len(catalog), "permitted_count": len(self._config["allowed_tools"]), "governance": self._governance})
            return deepcopy(catalog)

    def binding(self):
        self.discover()
        c = self._config
        return {"schema": "kch.composed.federation-binding.v1", "config_sha256": self._config_hash,
                "catalog_sha256": _hash(self._catalog), "namespace": c["namespace"],
                "principal": c["principal"], "workspace": c["workspace"], "session": c["session"],
                "scope": {"principal": c["principal"], "workspace": c["workspace"], "session": c["session"]},
                "state_dir": c["state_dir"],
                "authority_inherited": False}

    def schemas(self):
        self.discover()
        result = []
        for alias, descriptor in self._aliases.items():
            policy = self._config["allowed_tools"].get(descriptor["name"])
            if not policy:
                continue
            schema = deepcopy(descriptor["inputSchema"])
            # Fixed authority/scope arguments are absent from model-facing schema.
            for key in policy["fixed_arguments"]:
                schema.get("properties", {}).pop(key, None)
                if key in schema.get("required", []):
                    schema["required"].remove(key)
            result.append({"type": "function", "function": {"name": alias,
                "description": descriptor.get("description", "") + " [Canonical KCH tool: " + descriptor["name"] + "; host policy applies.]",
                "parameters": schema}})
        return result

    def invoke(self, alias, arguments, *, call_id):
        try:
            return self._invoke(alias, arguments, call_id=call_id)
        except FederationDenied:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                self._event(db, "DISPATCH_DENIED", {"call_id": call_id if isinstance(call_id, str) else None,
                    "alias": alias if isinstance(alias, str) else None})
            raise

    def _invoke(self, alias, arguments, *, call_id):
        with self._lock:
            self.discover()
            if not self.audit()["valid"]:
                raise FederationDenied("Federation audit integrity failed before dispatch")
            descriptor = self._aliases.get(alias)
            policy = self._config["allowed_tools"].get(descriptor["name"]) if descriptor else None
            if not policy or not isinstance(arguments, dict) or not isinstance(call_id, str) or not call_id:
                raise FederationDenied("Unknown, disabled or malformed federated invocation")
            arguments = _loads(_json(arguments))
            _reject_host_arguments(arguments)
            if set(arguments) & set(policy["fixed_arguments"]):
                raise FederationDenied("Host-bound arguments cannot be supplied by the caller")
            merged = {**arguments, **deepcopy(policy["fixed_arguments"])}
            try:
                _validator(descriptor["inputSchema"]).validate(merged)
                if "argument_schema" in policy:
                    _validator(policy["argument_schema"]).validate(merged)
            except FederationDenied:
                raise
            except Exception as exc:
                raise FederationDenied("Federated arguments violate canonical or host schema") from exc
            request = {"name": descriptor["name"], "arguments": merged}
            if len((_json({"jsonrpc": "2.0", "id": 999999999999, "method": "tools/call", "params": request}) + "\n").encode()) > self._config["max_message_bytes"]:
                raise FederationDenied("Invocation exceeds transport byte limit")
            binding_hash, request_hash = _hash(self.binding()), _hash(request)
            # Idempotence is keyed by stable host config, not changing catalog.
            # A catalog drift must not turn the same ID into another effect.
            journal_key = self._config_hash
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                old = db.execute("SELECT request_hash,status,response FROM federation_calls WHERE binding=? AND call_id=?", (journal_key, call_id)).fetchone()
                if old:
                    if old[0] != request_hash:
                        raise FederationDenied("Call identifier was already bound to different arguments")
                    if old[1] == "COMPLETED":
                        cached = _loads(old[2])
                        if cached["receipt"]["binding_sha256"] != binding_hash:
                            raise FederationDenied("Catalog changed since this call; cached result is not promoted")
                        if cached["receipt"]["result_sha256"] != _hash(cached["result"]):
                            raise FederationDenied("Stored federation result digest mismatch")
                        return cached
                    raise FederationUncertain("Prior dispatch has no complete receipt; automatic replay is forbidden")
                if not policy["read_only"]:
                    permit = self._authorize({"binding": self.binding(), "call_id": call_id, "request": deepcopy(request)})
                    if permit is not True:
                        raise FederationDenied("Trusted host authorizer denied this exact invocation")
                db.execute("INSERT INTO federation_calls VALUES(?,?,?,'STARTED',NULL)", (journal_key, call_id, request_hash))
                self._event(db, "DISPATCH_STARTED", {"call_id": call_id, "request_sha256": request_hash,
                    "canonical_name": descriptor["name"], "alias": alias, "binding_sha256": binding_hash})
            try:
                result = self._client.request("tools/call", request)
                if not isinstance(result, dict) or not isinstance(result.get("content"), list):
                    raise FederationProtocolError("Invalid tools/call result")
                with self._db() as db:
                    db.execute("BEGIN IMMEDIATE")
                    event_hash = self._event(db, "DISPATCH_COMPLETED", {"call_id": call_id, "request_sha256": request_hash,
                         "result_sha256": _hash(result), "is_error": result.get("isError", False)})
                    response = {"result": result, "receipt": {"schema": "kch.composed.federation-receipt.v1",
                        "call_id": call_id, "canonical_name": descriptor["name"], "alias": alias,
                        "binding_sha256": binding_hash, "request_sha256": request_hash,
                        "result_sha256": _hash(result), "event_hash": event_hash,
                        "authority_inherited": False}}
                    db.execute("UPDATE federation_calls SET status='COMPLETED',response=? WHERE binding=? AND call_id=?", (_json(response), journal_key, call_id))
                return response
            except Exception as exc:
                with self._db() as db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("UPDATE federation_calls SET status='UNCERTAIN' WHERE binding=? AND call_id=?", (journal_key, call_id))
                    self._event(db, "DISPATCH_UNCERTAIN", {"call_id": call_id, "error_type": type(exc).__name__})
                self.close()
                raise FederationUncertain("Federated dispatch lacks a complete receipt; inspect state before a new attempt") from exc

    def audit(self):
        previous, count = "0" * 64, 0
        events, projection = {}, {}
        with self._db() as db:
            db.execute("BEGIN")  # One consistent snapshot during concurrent host calls.
            for sequence, body, stored_previous, event_hash in db.execute("SELECT sequence,body,previous_hash,event_hash FROM federation_events ORDER BY sequence"):
                try:
                    decoded = _loads(body)
                    expected = _hash({"previous_hash": previous, "body": decoded})
                except (ValueError, TypeError):
                    return {"valid": False, "events_verified": count}
                if sequence != count + 1 or previous != stored_previous or event_hash != expected:
                    return {"valid": False, "events_verified": count}
                try:
                    kind = decoded["kind"]
                    if kind.startswith("DISPATCH_") and kind != "DISPATCH_DENIED":
                        key = (decoded["config_hash"], decoded["call_id"])
                        if kind == "DISPATCH_STARTED":
                            if key in projection:
                                return {"valid": False, "events_verified": count}
                            projection[key] = {"request_sha256": decoded["request_sha256"], "status": "STARTED",
                                "binding_sha256": decoded["binding_sha256"], "canonical_name": decoded["canonical_name"], "alias": decoded["alias"]}
                        elif kind in {"DISPATCH_COMPLETED", "DISPATCH_UNCERTAIN"}:
                            if key not in projection or projection[key]["status"] != "STARTED":
                                return {"valid": False, "events_verified": count}
                            projection[key]["status"] = kind.removeprefix("DISPATCH_")
                            if kind == "DISPATCH_COMPLETED":
                                if decoded["request_sha256"] != projection[key]["request_sha256"]:
                                    return {"valid": False, "events_verified": count}
                                projection[key]["result_sha256"] = decoded["result_sha256"]
                                projection[key]["event_hash"] = event_hash
                        else:
                            return {"valid": False, "events_verified": count}
                    elif kind not in {"DISCOVERED", "DISPATCH_DENIED"}:
                        return {"valid": False, "events_verified": count}
                except (KeyError, TypeError, AttributeError):
                    return {"valid": False, "events_verified": count}
                events[event_hash] = decoded
                previous, count = event_hash, count + 1
            if db.execute("SELECT sequence,event_hash FROM federation_head WHERE singleton=1").fetchone() != (count, previous):
                return {"valid": False, "events_verified": count}
            observed = set()
            for binding, call_id, request_hash, status, response in db.execute("SELECT binding,call_id,request_hash,status,response FROM federation_calls"):
                try:
                    key = (binding, call_id)
                    derived = projection[key]
                    observed.add(key)
                    if request_hash != derived["request_sha256"] or status != derived["status"]:
                        return {"valid": False, "events_verified": count}
                    if status != "COMPLETED":
                        if response is not None:
                            return {"valid": False, "events_verified": count}
                        continue
                    item = _loads(response)
                    receipt = item["receipt"]
                    expected_receipt_keys = {"schema", "call_id", "canonical_name", "alias", "binding_sha256",
                        "request_sha256", "result_sha256", "event_hash", "authority_inherited"}
                    if (set(item) != {"result", "receipt"} or not isinstance(receipt, dict)
                            or set(receipt) != expected_receipt_keys
                            or receipt["schema"] != "kch.composed.federation-receipt.v1"
                            or receipt["authority_inherited"] is not False):
                        return {"valid": False, "events_verified": count}
                    event = events[receipt["event_hash"]]
                    if (event["kind"] != "DISPATCH_COMPLETED" or event["config_hash"] != binding
                            or event["call_id"] != call_id or event["request_sha256"] != request_hash
                            or receipt["request_sha256"] != request_hash or receipt["call_id"] != call_id
                            or receipt["event_hash"] != derived["event_hash"]
                            or any(receipt[k] != derived[k] for k in ("binding_sha256", "canonical_name", "alias"))
                            or event["result_sha256"] != receipt["result_sha256"]
                            or receipt["result_sha256"] != _hash(item["result"])):
                        return {"valid": False, "events_verified": count}
                except (ValueError, TypeError, KeyError):
                    return {"valid": False, "events_verified": count}
            if observed != set(projection):
                return {"valid": False, "events_verified": count}
            states = dict(db.execute("SELECT status,COUNT(*) FROM federation_calls GROUP BY status"))
        return {"valid": True, "events_verified": count, "head": previous, "calls_by_status": states}

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None
        self._catalog = None
        self._aliases = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
