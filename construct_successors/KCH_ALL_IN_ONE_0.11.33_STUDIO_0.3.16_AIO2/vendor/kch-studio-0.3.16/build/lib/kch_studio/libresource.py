from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import canonical_json, sha256_json, sqlite_connection

FORMAT_SCHEMA = "kch.libresource.package.v0.1.0"
ROUTES = ("NATIVE", "IMPORT", "EXPORT", "COEXIST", "REPLACE", "ROLLBACK")
COMPATIBILITY_DIMENSIONS = (
    "SYNTACTIC",
    "SEMANTIC",
    "STATE",
    "OPERATIONAL",
    "AGENTIC",
    "AUTHORITY",
    "HISTORICAL",
    "INVERSE",
)
RESOURCE_KINDS = (
    "ACCOUNT",
    "BROWSER",
    "CLOUD",
    "DATABASE",
    "FORMAT",
    "HARDWARE",
    "JURISDICTION",
    "LANGUAGE",
    "MODEL",
    "OPERATING_SYSTEM",
    "PROTOCOL",
    "PROVIDER",
    "REPOSITORY",
    "RUNTIME",
    "SDK",
    "SERVICE",
    "TOOLCHAIN",
)
FLUSH_STATES = (
    "FOREIGN_REQUIRED",
    "CSI_CONTRACTED",
    "CSI_SHADOW",
    "CSI_DIFFERENTIAL_PASS",
    "CSI_PREFERRED",
    "FOREIGN_OPTIONAL",
    "FOREIGN_REMOVABLE",
    "LIBRESOURCE_FLUSHED",
    "SEALED",
)
NEXT_STATE = dict(zip(FLUSH_STATES[:-1], FLUSH_STATES[1:], strict=True))
UNIVERSAL_WITHDRAWAL_GATES = (
    "INVENTORY_COMPLETE",
    "DISCONNECT",
    "INDEPENDENT_BOOT",
    "STATE_RECONSTRUCT",
    "AUTHORITY_HASH_VERIFY",
    "DEGRADATION_MEASURE",
    "SUBSTITUTE",
    "HISTORY_PRESERVE",
)
FLUSH_DECISION_GATES = (
    "SUCCESSOR_COMPETENCE",
    "FLUSH_PROPORTIONALITY",
)
PLUG_AND_PLAY_GATES = (
    "CLEAN_INSTALL",
    "AUTODETECT",
    "ONE_SHOT_PAIRING",
    "CAPABILITY_USE",
    "PERMISSION_VISIBILITY",
    "UNINSTALL_STATE_PRESERVED",
    "ROLLBACK",
    "OFFLINE_CORE_CONTINUITY",
)
GATE_OUTCOMES = {"PASS", "FAIL", "DEGRADED_RECOVERABLE", "NOT_ESTIMABLE", "NOT_RUN"}

ADAPTER_CONTRACTS: dict[str, dict[str, Any]] = {
    "WINDOWS": {
        "zone": "FOREIGN_CAPABILITY_ZONE",
        "authority": "NONE",
        "capabilities": [
            "host-detection",
            "local-thin-bridge",
            "one-shot-pairing",
            "clipboard",
            "capture",
            "audio",
            "notifications",
            "self-diagnosis",
            "reversible-uninstall",
        ],
        "core_state_allowed": False,
    },
    "VSCODE": {
        "zone": "FOREIGN_CAPABILITY_ZONE",
        "authority": "NONE",
        "capabilities": [
            "chat-and-execution",
            "sco-session-selection",
            "plan-run-construct-checkpoints",
            "live-process-status",
            "constitutional-lock-ui",
            "graph-kwandata-files",
            "diagnosis-update-reconnect",
        ],
        "core_state_allowed": False,
    },
    "GITHUB": {
        "zone": "FOREIGN_CAPABILITY_ZONE",
        "authority": "NONE",
        "capabilities": [
            "git-ssh-api",
            "clone-sync-branches-commits",
            "pull-requests-issues-releases-webhooks",
            "fine-grained-authentication",
            "governed-bidirectional-replication",
            "ci-observation",
        ],
        "canonical_repository_allowed": False,
        "core_state_allowed": False,
    },
    "GOOGLE": {
        "zone": "FOREIGN_CAPABILITY_ZONE",
        "authority": "NONE",
        "capabilities": [
            "drive",
            "docs-sheets-slides",
            "colab",
            "kaggle",
            "gmail-calendar-optional",
            "search-import-export-verified-copy",
            "finite-progressive-oauth",
        ],
        "official_sdk_required_in_core": False,
        "core_state_allowed": False,
    },
    "GENERIC_PROVIDER": {
        "zone": "FOREIGN_CAPABILITY_ZONE",
        "authority": "NONE",
        "capabilities": [
            "capability-negotiation",
            "namespaced-extensions",
            "declared-degradation",
            "bidirectional-import-export",
        ],
        "core_state_allowed": False,
    },
}

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS nodes(
    node_id TEXT NOT NULL,
    version TEXT NOT NULL,
    zone TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(node_id,version)
);
CREATE TABLE IF NOT EXISTS flushes(
    flush_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    node_version TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    state TEXT NOT NULL,
    csi_contract_json TEXT NOT NULL,
    rollback_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(node_id,node_version) REFERENCES nodes(node_id,version)
);
CREATE TABLE IF NOT EXISTS gates(
    gate_id TEXT PRIMARY KEY,
    flush_id TEXT NOT NULL REFERENCES flushes(flush_id),
    gate_name TEXT NOT NULL,
    outcome TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS command_receipts(
    command_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    result_json TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class LibresourceError(ValueError):
    pass


def _require_nonempty(value: Any, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise LibresourceError(f"{field} must be non-empty")
    return text


def validate_package_manifest(value: dict[str, Any]) -> dict[str, Any]:
    manifest = json.loads(canonical_json(value))
    if manifest.get("schema") != FORMAT_SCHEMA:
        raise LibresourceError(f"manifest schema must be {FORMAT_SCHEMA}")
    for field in ("node_id", "version", "zone", "license", "state_export"):
        manifest[field] = _require_nonempty(manifest.get(field), field)
    if manifest["zone"] not in {"STRICT_CORE", "FOREIGN_CAPABILITY_ZONE"}:
        raise LibresourceError("zone must be STRICT_CORE or FOREIGN_CAPABILITY_ZONE")
    if manifest.get("initial_authority") != "NONE":
        raise LibresourceError("every LIBRESOURCE package must start with authority NONE")
    routes = dict(manifest.get("routes", {}))
    if set(routes) != set(ROUTES):
        raise LibresourceError(f"routes must be exactly {list(ROUTES)}")
    for name in ROUTES:
        route = dict(routes[name])
        if not isinstance(route.get("supported"), bool):
            raise LibresourceError(f"route {name} requires a boolean supported field")
        refs = route.get("evidence_refs", [])
        if not isinstance(refs, list) or any(not str(item).strip() for item in refs):
            raise LibresourceError(f"route {name} evidence_refs must be a list of identifiers")
        routes[name] = {"supported": route["supported"], "evidence_refs": sorted(set(refs))}
    manifest["routes"] = routes
    for field in (
        "content_hashes",
        "csi_contracts",
        "sbom",
        "provenance",
        "dependencies",
        "permissions",
        "build_recipes",
        "platforms",
        "alternatives",
        "migrations",
        "conformance_tests",
        "signatures",
    ):
        if not isinstance(manifest.get(field), list):
            raise LibresourceError(f"{field} must be a list")
    if not manifest["content_hashes"] or not manifest["csi_contracts"]:
        raise LibresourceError("content hashes and CSI contracts cannot be empty")
    if not manifest["sbom"] or not manifest["provenance"]:
        raise LibresourceError("SBOM and provenance cannot be empty")
    dependency_ids: set[str] = set()
    normalized_dependencies: list[dict[str, Any]] = []
    for dependency in manifest["dependencies"]:
        item = dict(dependency)
        for field in ("resource_id", "kind", "role", "jurisdiction"):
            item[field] = _require_nonempty(item.get(field), f"dependency.{field}")
        item["kind"] = item["kind"].upper()
        if item["kind"] not in RESOURCE_KINDS:
            raise LibresourceError(f"unsupported dependency kind: {item['kind']}")
        if item["resource_id"] in dependency_ids:
            raise LibresourceError("dependency resource_id values must be unique")
        dependency_ids.add(item["resource_id"])
        if not isinstance(item.get("constitutive"), bool):
            raise LibresourceError("dependency.constitutive must be boolean")
        alternatives = item.get("alternatives", [])
        if not isinstance(alternatives, list):
            raise LibresourceError("dependency.alternatives must be a list")
        item["alternatives"] = sorted(set(str(value) for value in alternatives if str(value)))
        item["authority"] = _require_nonempty(
            item.get("authority", "NONE"), "dependency.authority"
        ).upper()
        item["removal_route"] = _require_nonempty(
            item.get("removal_route"), "dependency.removal_route"
        )
        normalized_dependencies.append(item)
    manifest["dependencies"] = normalized_dependencies

    capability_contract = dict(manifest.get("capability_contract", {}))
    if not isinstance(capability_contract.get("core"), list):
        raise LibresourceError("capability_contract.core must be a list")
    if not isinstance(capability_contract.get("namespaced_extensions"), list):
        raise LibresourceError(
            "capability_contract.namespaced_extensions must be a list"
        )
    capability_contract["degradation_policy"] = _require_nonempty(
        capability_contract.get("degradation_policy"),
        "capability_contract.degradation_policy",
    )
    manifest["capability_contract"] = capability_contract

    canonical_state = dict(manifest.get("canonical_state", {}))
    for field in ("schema", "export", "restore", "verification"):
        canonical_state[field] = _require_nonempty(
            canonical_state.get(field), f"canonical_state.{field}"
        )
    manifest["canonical_state"] = canonical_state

    platform = dict(manifest.get("platform_independence", {}))
    platform["reference_implementation"] = _require_nonempty(
        platform.get("reference_implementation"),
        "platform_independence.reference_implementation",
    )
    if not isinstance(platform.get("alternate_paths"), list):
        raise LibresourceError("platform_independence.alternate_paths must be a list")
    if platform.get("single_platform_is_canonical") is not False:
        raise LibresourceError("no execution platform may be constitutionally canonical")
    manifest["platform_independence"] = platform

    compatibility = dict(manifest.get("compatibility", {}))
    if set(compatibility) != set(COMPATIBILITY_DIMENSIONS):
        raise LibresourceError(
            f"compatibility must declare exactly {list(COMPATIBILITY_DIMENSIONS)}"
        )
    for dimension in COMPATIBILITY_DIMENSIONS:
        declaration = dict(compatibility[dimension])
        declaration["contract"] = _require_nonempty(
            declaration.get("contract"), f"compatibility.{dimension}.contract"
        )
        refs = declaration.get("evidence_refs", [])
        if not isinstance(refs, list):
            raise LibresourceError(
                f"compatibility.{dimension}.evidence_refs must be a list"
            )
        declaration["evidence_refs"] = sorted(
            set(str(value) for value in refs if str(value))
        )
        compatibility[dimension] = declaration
    manifest["compatibility"] = compatibility
    policy = dict(manifest.get("human_policy", {}))
    if policy.get("nationality_discrimination") is not False:
        raise LibresourceError("LIBRESOURCE forbids discrimination of people by nationality")
    manifest["human_policy"] = policy
    return manifest


class LibresourceRuntime:
    """Transactional LIBRESOURCE package and CSI Flush governor.

    This runtime proves local state-machine and custody properties only. It does
    not infer that an external adapter, alternate OS or legal license has passed
    a real-world conformance gate.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "libresource.sqlite3"
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
    def _event_hash(
        event_type: str, payload_sha256: str, previous_hash: str, created_at: str
    ) -> str:
        return sha256_json(
            {
                "event_type": event_type,
                "payload_sha256": payload_sha256,
                "previous_hash": previous_hash,
                "created_at": created_at,
            }
        )

    def _append_event(
        self, connection: sqlite3.Connection, event_type: str, payload: dict[str, Any]
    ) -> str:
        payload_json = canonical_json(payload)
        payload_sha = sha256_json(payload)
        row = connection.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous = str(row[0]) if row else "0" * 64
        created = utc_now()
        event_hash = self._event_hash(event_type, payload_sha, previous, created)
        connection.execute(
            "INSERT INTO events(event_type,payload_json,payload_sha256,previous_hash,event_hash,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (event_type, payload_json, payload_sha, previous, event_hash, created),
        )
        return event_hash

    @staticmethod
    def _cached(
        connection: sqlite3.Connection, command_id: str, operation: str, input_sha: str
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT * FROM command_receipts WHERE command_id=?", (command_id,)
        ).fetchone()
        if row is None:
            return None
        if row["operation"] != operation or row["input_sha256"] != input_sha:
            raise LibresourceError("command_id was already used with different exact input")
        return json.loads(str(row["result_json"]))

    @staticmethod
    def _receipt(
        connection: sqlite3.Connection,
        command_id: str,
        operation: str,
        input_sha: str,
        result: dict[str, Any],
        event_hash: str,
    ) -> None:
        connection.execute(
            "INSERT INTO command_receipts VALUES(?,?,?,?,?)",
            (command_id, operation, input_sha, canonical_json(result), event_hash),
        )

    def register_node(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command_id = _require_nonempty(arguments.get("command_id"), "command_id")
        manifest = validate_package_manifest(dict(arguments["manifest"]))
        input_sha = sha256_json({"manifest": manifest})
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cached = self._cached(connection, command_id, "NODE_REGISTER", input_sha)
            if cached is not None:
                connection.commit()
                return cached
            existing = connection.execute(
                "SELECT manifest_sha256 FROM nodes WHERE node_id=? AND version=?",
                (manifest["node_id"], manifest["version"]),
            ).fetchone()
            manifest_sha = sha256_json(manifest)
            if existing and existing[0] != manifest_sha:
                raise LibresourceError("node version is immutable; create a successor version")
            if not existing:
                connection.execute(
                    "INSERT INTO nodes VALUES(?,?,?,?,?,?)",
                    (
                        manifest["node_id"],
                        manifest["version"],
                        manifest["zone"],
                        canonical_json(manifest),
                        manifest_sha,
                        utc_now(),
                    ),
                )
            result = {
                "schema": "kch.libresource.node-receipt.v0.1.0",
                "node_id": manifest["node_id"],
                "version": manifest["version"],
                "manifest_sha256": manifest_sha,
                "initial_authority": "NONE",
                "registered": not bool(existing),
            }
            event_hash = self._append_event(connection, "NODE_REGISTERED", result)
            result["event_hash"] = event_hash
            self._receipt(connection, command_id, "NODE_REGISTER", input_sha, result, event_hash)
            connection.commit()
            return result

    def inspect_node(self, node_id: str, version: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM nodes WHERE node_id=? AND version=?", (node_id, version)
            ).fetchone()
            if row is None:
                raise KeyError((node_id, version))
            manifest = json.loads(str(row["manifest_json"]))
            return {
                "manifest": manifest,
                "manifest_sha256": row["manifest_sha256"],
                "local_format_valid": validate_package_manifest(manifest) == manifest,
                "conformance_claimed": False,
            }

    def begin_flush(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command_id = _require_nonempty(arguments.get("command_id"), "command_id")
        node_id = _require_nonempty(arguments.get("node_id"), "node_id")
        version = _require_nonempty(arguments.get("version"), "version")
        resource_id = _require_nonempty(arguments.get("resource_id"), "resource_id")
        contract = dict(arguments.get("csi_contract", {}))
        rollback = dict(arguments.get("rollback", {}))
        if not contract or not rollback:
            raise LibresourceError("CSI contract and rollback contract are required before a flush")
        material = {
            "node_id": node_id,
            "version": version,
            "resource_id": resource_id,
            "csi_contract": contract,
            "rollback": rollback,
        }
        input_sha = sha256_json(material)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cached = self._cached(connection, command_id, "FLUSH_BEGIN", input_sha)
            if cached is not None:
                connection.commit()
                return cached
            node = connection.execute(
                "SELECT 1 FROM nodes WHERE node_id=? AND version=?", (node_id, version)
            ).fetchone()
            if node is None:
                raise KeyError((node_id, version))
            flush_id = f"FLUSH-{uuid.uuid4()}"
            now = utc_now()
            connection.execute(
                "INSERT INTO flushes VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    flush_id,
                    node_id,
                    version,
                    resource_id,
                    "FOREIGN_REQUIRED",
                    canonical_json(contract),
                    canonical_json(rollback),
                    now,
                    now,
                ),
            )
            result = {
                "schema": "kch.libresource.flush-receipt.v0.1.0",
                "flush_id": flush_id,
                "resource_id": resource_id,
                "state": "FOREIGN_REQUIRED",
                "automatic_promotion": False,
            }
            event_hash = self._append_event(connection, "FLUSH_BEGUN", result)
            result["event_hash"] = event_hash
            self._receipt(connection, command_id, "FLUSH_BEGIN", input_sha, result, event_hash)
            connection.commit()
            return result

    def record_gate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command_id = _require_nonempty(arguments.get("command_id"), "command_id")
        flush_id = _require_nonempty(arguments.get("flush_id"), "flush_id")
        gate = _require_nonempty(arguments.get("gate_name"), "gate_name").upper()
        outcome = _require_nonempty(arguments.get("outcome"), "outcome").upper()
        evidence = sorted(set(str(item) for item in arguments.get("evidence_refs", [])))
        if gate not in (
            set(UNIVERSAL_WITHDRAWAL_GATES)
            | set(FLUSH_DECISION_GATES)
            | set(PLUG_AND_PLAY_GATES)
        ):
            raise LibresourceError("gate is not part of LIBRESOURCE conformance")
        if outcome not in GATE_OUTCOMES:
            raise LibresourceError(f"unsupported gate outcome: {outcome}")
        if outcome != "NOT_RUN" and not evidence:
            raise LibresourceError("observed gate outcomes require evidence references")
        material = {"flush_id": flush_id, "gate": gate, "outcome": outcome, "evidence": evidence}
        input_sha = sha256_json(material)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cached = self._cached(connection, command_id, "GATE_RECORD", input_sha)
            if cached is not None:
                connection.commit()
                return cached
            if connection.execute("SELECT 1 FROM flushes WHERE flush_id=?", (flush_id,)).fetchone() is None:
                raise KeyError(flush_id)
            gate_id = f"GATE-{uuid.uuid4()}"
            connection.execute(
                "INSERT INTO gates VALUES(?,?,?,?,?,?)",
                (gate_id, flush_id, gate, outcome, canonical_json(evidence), utc_now()),
            )
            result = {"gate_id": gate_id, **material}
            event_hash = self._append_event(connection, "GATE_RECORDED", result)
            result["event_hash"] = event_hash
            self._receipt(connection, command_id, "GATE_RECORD", input_sha, result, event_hash)
            connection.commit()
            return result

    @staticmethod
    def _latest_gates(connection: sqlite3.Connection, flush_id: str) -> dict[str, dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM gates WHERE flush_id=? ORDER BY observed_at,gate_id", (flush_id,)
        ).fetchall()
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            latest[str(row["gate_name"])] = {
                "outcome": row["outcome"],
                "evidence_refs": json.loads(str(row["evidence_json"])),
                "observed_at": row["observed_at"],
            }
        return latest

    def transition_flush(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command_id = _require_nonempty(arguments.get("command_id"), "command_id")
        flush_id = _require_nonempty(arguments.get("flush_id"), "flush_id")
        target = _require_nonempty(arguments.get("target_state"), "target_state").upper()
        evidence = sorted(set(str(item) for item in arguments.get("evidence_refs", [])))
        if not evidence:
            raise LibresourceError("each flush transition requires evidence")
        material = {"flush_id": flush_id, "target": target, "evidence": evidence}
        input_sha = sha256_json(material)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cached = self._cached(connection, command_id, "FLUSH_TRANSITION", input_sha)
            if cached is not None:
                connection.commit()
                return cached
            row = connection.execute("SELECT * FROM flushes WHERE flush_id=?", (flush_id,)).fetchone()
            if row is None:
                raise KeyError(flush_id)
            current = str(row["state"])
            expected = NEXT_STATE.get(current)
            if target != expected:
                raise LibresourceError(f"flush transition must be sequential: {current} -> {expected}")
            gates = self._latest_gates(connection, flush_id)
            if target in {"LIBRESOURCE_FLUSHED", "SEALED"}:
                missing = [
                    name
                    for name in (*UNIVERSAL_WITHDRAWAL_GATES, *FLUSH_DECISION_GATES)
                    if gates.get(name, {}).get("outcome") != "PASS"
                ]
                if missing:
                    raise LibresourceError(f"withdrawal gates not passed: {missing}")
            connection.execute(
                "UPDATE flushes SET state=?,updated_at=? WHERE flush_id=?",
                (target, utc_now(), flush_id),
            )
            result = {
                "flush_id": flush_id,
                "previous_state": current,
                "state": target,
                "evidence_refs": evidence,
                "automatic_promotion": False,
            }
            event_hash = self._append_event(connection, "FLUSH_TRANSITIONED", result)
            result["event_hash"] = event_hash
            self._receipt(connection, command_id, "FLUSH_TRANSITION", input_sha, result, event_hash)
            connection.commit()
            return result

    def evaluate(self, flush_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM flushes WHERE flush_id=?", (flush_id,)).fetchone()
            if row is None:
                raise KeyError(flush_id)
            gates = self._latest_gates(connection, flush_id)
        observed = {name: gates.get(name, {"outcome": "NOT_RUN"}) for name in UNIVERSAL_WITHDRAWAL_GATES}
        outcomes = [item["outcome"] for item in observed.values()]
        if "FAIL" in outcomes:
            conclusion = "LIBRESOURCE_FAIL_CONSTITUTIVE_DEPENDENCY"
        elif all(outcome == "PASS" for outcome in outcomes):
            conclusion = "LIBRESOURCE_INDEPENDENCE_PASS"
        elif any(outcome == "DEGRADED_RECOVERABLE" for outcome in outcomes) and not any(
            outcome in {"FAIL", "NOT_ESTIMABLE"} for outcome in outcomes
        ):
            conclusion = "LIBRESOURCE_DEGRADED_BUT_RECOVERABLE"
        else:
            conclusion = "LIBRESOURCE_NOT_ESTABLISHED"
        return {
            "schema": "kch.libresource.evaluation.v0.1.0",
            "flush_id": flush_id,
            "resource_id": row["resource_id"],
            "state": row["state"],
            "withdrawal_gates": observed,
            "conclusion": conclusion,
            "absence_established": conclusion == "LIBRESOURCE_INDEPENDENCE_PASS"
            and row["state"] in {"LIBRESOURCE_FLUSHED", "SEALED"},
            "independence_established": conclusion == "LIBRESOURCE_INDEPENDENCE_PASS",
            "history_rewrite_authorized": False,
        }

    def adapter_contract(self, adapter: str) -> dict[str, Any]:
        key = adapter.upper()
        contract = ADAPTER_CONTRACTS.get(key)
        if contract is None:
            contract = ADAPTER_CONTRACTS["GENERIC_PROVIDER"]
            key = f"GENERIC_PROVIDER:{adapter}"
        return {
            "schema": "kch.libresource.adapter-contract.v0.1.0",
            "adapter": key,
            **contract,
            "required_routes": list(ROUTES),
            "required_plug_and_play_gates": list(PLUG_AND_PLAY_GATES),
            "plug_and_play_established": False,
        }

    def dependency_audit(self, node_id: str, version: str) -> dict[str, Any]:
        node = self.inspect_node(node_id, version)
        manifest = node["manifest"]
        dependencies = list(manifest["dependencies"])
        constitutive_without_alternative = sorted(
            item["resource_id"]
            for item in dependencies
            if item["constitutive"] and not item["alternatives"]
        )
        authority_violations = sorted(
            item["resource_id"]
            for item in dependencies
            if item.get("authority", "NONE") != "NONE"
        )
        by_kind: dict[str, list[str]] = {}
        by_jurisdiction: dict[str, list[str]] = {}
        for item in dependencies:
            by_kind.setdefault(item["kind"], []).append(item["resource_id"])
            by_jurisdiction.setdefault(item["jurisdiction"], []).append(
                item["resource_id"]
            )
        for group in (*by_kind.values(), *by_jurisdiction.values()):
            group.sort()
        failures = constitutive_without_alternative + authority_violations
        conclusion = (
            "LIBRESOURCE_FAIL_CONSTITUTIVE_DEPENDENCY"
            if failures
            else "NO_DECLARED_CONSTITUTIVE_SINGLE_POINT_WITHDRAWAL_NOT_PROVEN"
        )
        result = {
            "schema": "kch.libresource.dependency-audit.v0.1.0",
            "node_id": node_id,
            "version": version,
            "manifest_sha256": node["manifest_sha256"],
            "dependency_count": len(dependencies),
            "dependencies_by_kind": dict(sorted(by_kind.items())),
            "dependencies_by_jurisdiction": dict(sorted(by_jurisdiction.items())),
            "constitutive_without_alternative": constitutive_without_alternative,
            "authority_violations": authority_violations,
            "conclusion": conclusion,
            "absence_established": False,
            "independence_established": False,
            "withdrawal_execution_required": True,
        }
        return {**result, "receipt_sha256": sha256_json(result)}

    @staticmethod
    def _adjudicate_observations(
        observations: dict[str, Any], required: tuple[str, ...]
    ) -> tuple[dict[str, dict[str, Any]], str]:
        if set(observations) != set(required):
            raise LibresourceError(f"observations must be exactly {list(required)}")
        normalized: dict[str, dict[str, Any]] = {}
        for name in required:
            item = dict(observations[name])
            outcome = _require_nonempty(item.get("outcome"), f"{name}.outcome").upper()
            if outcome not in GATE_OUTCOMES:
                raise LibresourceError(f"unsupported outcome for {name}: {outcome}")
            refs = item.get("evidence_refs", [])
            if not isinstance(refs, list):
                raise LibresourceError(f"{name}.evidence_refs must be a list")
            refs = sorted(set(str(value) for value in refs if str(value)))
            if outcome != "NOT_RUN" and not refs:
                raise LibresourceError(f"{name} requires evidence references")
            normalized[name] = {"outcome": outcome, "evidence_refs": refs}
        outcomes = [item["outcome"] for item in normalized.values()]
        if "FAIL" in outcomes:
            conclusion = "FAIL"
        elif all(outcome == "PASS" for outcome in outcomes):
            conclusion = "PASS_BOUNDED_DECLARED_SCOPE"
        elif any(outcome == "DEGRADED_RECOVERABLE" for outcome in outcomes) and not any(
            outcome in {"FAIL", "NOT_ESTIMABLE", "NOT_RUN"} for outcome in outcomes
        ):
            conclusion = "DEGRADED_BUT_RECOVERABLE"
        else:
            conclusion = "NOT_ESTABLISHED"
        return normalized, conclusion

    def adjudicate_compatibility(self, arguments: dict[str, Any]) -> dict[str, Any]:
        subject = _require_nonempty(arguments.get("subject"), "subject")
        scope = dict(arguments.get("scope", {}))
        if not scope:
            raise LibresourceError("compatibility adjudication requires an exact scope")
        dimensions, dimension_result = self._adjudicate_observations(
            dict(arguments.get("dimensions", {})), COMPATIBILITY_DIMENSIONS
        )
        routes, route_result = self._adjudicate_observations(
            dict(arguments.get("routes", {})), ROUTES
        )
        candidate = dimension_result == route_result == "PASS_BOUNDED_DECLARED_SCOPE"
        result = {
            "schema": "kch.libresource.compatibility-adjudication.v0.1.0",
            "subject": subject,
            "scope": scope,
            "dimensions": dimensions,
            "routes": routes,
            "dimension_result": dimension_result,
            "route_result": route_result,
            "bounded_candidate_pass": candidate,
            "ultracompatibility_established": False,
            "reason_not_established": (
                "INDEPENDENT_EVIDENCE_VERIFICATION_REQUIRED"
                if candidate
                else "DECLARED_GATES_INCOMPLETE_OR_ADVERSE"
            ),
            "automatic_promotion": False,
        }
        return {**result, "receipt_sha256": sha256_json(result)}

    def adjudicate_plug_and_play(self, arguments: dict[str, Any]) -> dict[str, Any]:
        adapter = _require_nonempty(arguments.get("adapter"), "adapter").upper()
        environment = dict(arguments.get("environment", {}))
        for field in ("host", "os", "architecture", "client_version"):
            environment[field] = _require_nonempty(
                environment.get(field), f"environment.{field}"
            )
        capabilities = sorted(
            set(str(value) for value in arguments.get("capabilities", []) if str(value))
        )
        if not capabilities:
            raise LibresourceError("at least one exercised capability is required")
        gates, structural_result = self._adjudicate_observations(
            dict(arguments.get("gates", {})), PLUG_AND_PLAY_GATES
        )
        candidate = structural_result == "PASS_BOUNDED_DECLARED_SCOPE"
        result = {
            "schema": "kch.libresource.plug-and-play-adjudication.v0.1.0",
            "adapter": adapter,
            "adapter_contract": self.adapter_contract(adapter),
            "environment": environment,
            "capabilities": capabilities,
            "gates": gates,
            "structural_result": structural_result,
            "bounded_candidate_pass": candidate,
            "plug_and_play_established": False,
            "reason_not_established": (
                "INDEPENDENT_EXECUTION_RECEIPT_VERIFICATION_REQUIRED"
                if candidate
                else "HOST_GATES_INCOMPLETE_OR_ADVERSE"
            ),
            "generalization_authorized": False,
            "automatic_promotion": False,
        }
        return {**result, "receipt_sha256": sha256_json(result)}

    def verify(self) -> dict[str, Any]:
        previous = "0" * 64
        errors: list[str] = []
        count = 0
        with closing(self.connect()) as connection:
            for row in connection.execute("SELECT * FROM events ORDER BY sequence"):
                expected = self._event_hash(
                    row["event_type"], row["payload_sha256"], previous, row["created_at"]
                )
                if row["previous_hash"] != previous or row["event_hash"] != expected:
                    errors.append(f"EVENT_CHAIN:{row['sequence']}")
                if sha256_json(json.loads(str(row["payload_json"]))) != row["payload_sha256"]:
                    errors.append(f"EVENT_PAYLOAD:{row['sequence']}")
                previous = str(row["event_hash"])
                count += 1
            nodes = int(connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
            flushes = int(connection.execute("SELECT COUNT(*) FROM flushes").fetchone()[0])
        return {
            "valid": not errors,
            "errors": errors,
            "event_count": count,
            "node_count": nodes,
            "flush_count": flushes,
            "physical_append_only_established": False,
        }

    def status(self) -> dict[str, Any]:
        integrity = self.verify()
        return {
            "schema": "kch.libresource.status.v0.1.0",
            "doctrine": "COMPATIBLE_BY_CONSTRUCTION_INDEPENDENT_BY_CONSTITUTION_REPLACEABLE_BY_CSI_FLUSH",
            "sovereignty_principle": "VOCATIONALLY_SOVEREIGN_NOT_RECKLESS",
            "flush_policy": "KEEP_VALUABLE_RESOURCES_UNTIL_A_PROPORTIONATE_SUCCESSOR_IS_PROSPECTIVELY_DEMONSTRATED",
            "format_schema": FORMAT_SCHEMA,
            "routes": list(ROUTES),
            "compatibility_dimensions": list(COMPATIBILITY_DIMENSIONS),
            "resource_kinds": list(RESOURCE_KINDS),
            "flush_states": list(FLUSH_STATES),
            "withdrawal_gates": list(UNIVERSAL_WITHDRAWAL_GATES),
            "flush_decision_gates": list(FLUSH_DECISION_GATES),
            "plug_and_play_gates": list(PLUG_AND_PLAY_GATES),
            "adapter_contracts": sorted(ADAPTER_CONTRACTS),
            "integrity": integrity,
            "geopolitical_non_alignment": True,
            "nationality_discrimination": False,
            "license_legally_validated": False,
            "world_priority_established": False,
            "alternate_os_execution_established": False,
            "plug_and_play_hosts_established": [],
            "mcp_required": False,
            "phl_training_executed": False,
            "claim_ceiling": "LOCAL_EXECUTABLE_LIBRESOURCE_GOVERNOR_NOT_EXTERNAL_CONFORMANCE",
        }

    def handlers(self) -> dict[str, Any]:
        return {
            "libresource_status": lambda _a: self.status(),
            "libresource_node_register": self.register_node,
            "libresource_node_inspect": lambda a: self.inspect_node(
                str(a["node_id"]), str(a["version"])
            ),
            "libresource_flush_begin": self.begin_flush,
            "libresource_gate_record": self.record_gate,
            "libresource_flush_transition": self.transition_flush,
            "libresource_evaluate": lambda a: self.evaluate(str(a["flush_id"])),
            "libresource_adapter_contract": lambda a: self.adapter_contract(str(a["adapter"])),
            "libresource_dependency_audit": lambda a: self.dependency_audit(
                str(a["node_id"]), str(a["version"])
            ),
            "libresource_compatibility_adjudicate": self.adjudicate_compatibility,
            "libresource_pnp_adjudicate": self.adjudicate_plug_and_play,
        }

    @staticmethod
    def tool_descriptors() -> list[dict[str, Any]]:
        def descriptor(name: str, description: str, *, read_only: bool) -> dict[str, Any]:
            return {
                "name": name,
                "title": name.replace("_", " ").title(),
                "description": description,
                "inputSchema": {"type": "object", "additionalProperties": True},
                "readOnly": read_only,
            }

        return [
            descriptor("libresource_status", "Inspect bounded LIBRESOURCE doctrine, gates and claims.", read_only=True),
            descriptor("libresource_node_register", "Register one validated, authority-free LIBRESOURCE package.", read_only=False),
            descriptor("libresource_node_inspect", "Inspect one exact package version and its local format seal.", read_only=True),
            descriptor("libresource_flush_begin", "Begin a reversible CSI Flush with an explicit contract and rollback.", read_only=False),
            descriptor("libresource_gate_record", "Record one evidence-bearing withdrawal or plug-and-play gate.", read_only=False),
            descriptor("libresource_flush_transition", "Advance exactly one CSI Flush state without skipping gates.", read_only=False),
            descriptor("libresource_evaluate", "Evaluate independence without promoting absent evidence.", read_only=True),
            descriptor("libresource_adapter_contract", "Inspect a zero-authority exterior adapter contract.", read_only=True),
            descriptor("libresource_dependency_audit", "Audit a package for declared constitutive dependencies, authority violations and concentration without claiming withdrawal proof.", read_only=True),
            descriptor("libresource_compatibility_adjudicate", "Adjudicate eight compatibility dimensions and all six routes within one exact declared scope; independent verification remains required.", read_only=True),
            descriptor("libresource_pnp_adjudicate", "Adjudicate all plug-and-play gates for one exact host and exercised capability set without generalizing beyond its evidence.", read_only=True),
        ]
