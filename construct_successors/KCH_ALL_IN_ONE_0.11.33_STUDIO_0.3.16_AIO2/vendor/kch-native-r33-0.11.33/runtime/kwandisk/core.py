from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Protocol


class KwanDiskError(RuntimeError):
    pass


class SecretExposureError(KwanDiskError):
    pass


class RemoteVerificationError(KwanDiskError):
    pass


DERIVED_DIRS = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", ".venv", "venv", "build"}
)
SEPARATE_CUSTODY_DIRS = frozenset({".git"})
SENSITIVE_PATH_PATTERNS = (
    re.compile(r"(^|/)(\.env)(\.|$)", re.I),
    re.compile(r"(^|/)(id_rsa|id_ed25519|credentials|secrets?)(\.|$)", re.I),
    re.compile(r"\.(pem|p12|pfx|key)$", re.I),
)
SENSITIVE_CONTENT_PATTERNS = {
    "PRIVATE_KEY": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GITHUB_TOKEN": re.compile(rb"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "OPENAI_KEY": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    "GENERIC_SECRET_ASSIGNMENT": re.compile(
        rb"(?im)^\s*(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s#]{8,}"
    ),
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: object) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_child(root: Path, relative: str | Path) -> Path:
    if Path(relative).is_absolute():
        raise KwanDiskError(f"absolute relative path forbidden: {relative}")
    root = root.resolve(strict=True)
    target = (root / relative).resolve(strict=False)
    if target != root and root not in target.parents:
        raise KwanDiskError(f"path escape blocked: {relative}")
    return target


@dataclass(frozen=True, slots=True)
class SyncPolicy:
    policy_id: str
    auto_inventory: bool = True
    auto_sync_non_sensitive: bool = False
    cloud_target_encrypted: bool = False
    exact_remote_hash_required_for_cleanup: bool = True
    quarantine_days: int = 14
    part_bytes: int = 95_000_000
    large_file_bytes: int = 500 * 1024 * 1024
    warning_free_bytes: int = 10 * 1024**3
    critical_free_bytes: int = 2 * 1024**3
    emergency_free_bytes: int = 512 * 1024**2

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or self.quarantine_days < 1 or self.part_bytes < 1:
            raise ValueError("invalid KwanDisk policy")


class StorageAdapter(Protocol):
    adapter_id: str
    kind: str
    independent_hash_supported: bool

    def put(self, key: str, source: Path) -> dict[str, Any]: ...
    def get(self, key: str, destination: Path) -> dict[str, Any]: ...
    def stat(self, key: str) -> dict[str, Any] | None: ...
    def list(self, prefix: str = "") -> list[dict[str, Any]]: ...


class FileSystemAdapter:
    def __init__(self, adapter_id: str, root: str | Path, *, kind: str = "LOCAL_OR_MOUNTED_CLOUD") -> None:
        self.adapter_id = adapter_id
        self.kind = kind
        self.independent_hash_supported = True
        self.root = Path(root).resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return safe_child(self.root, PurePosixPath(key))

    def put(self, key: str, source: Path) -> dict[str, Any]:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + f".{uuid.uuid4().hex}.partial")
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
        return self.stat(key) or {}

    def get(self, key: str, destination: Path) -> dict[str, Any]:
        source = self._path(key).resolve(strict=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + f".{uuid.uuid4().hex}.partial")
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
        return {"key": key, "bytes": destination.stat().st_size, "sha256": sha256_file(destination)}

    def stat(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.is_file():
            return None
        return {"key": key, "bytes": path.stat().st_size, "sha256": sha256_file(path), "remote_id": str(path)}

    def list(self, prefix: str = "") -> list[dict[str, Any]]:
        base = self._path(prefix) if prefix else self.root
        if not base.exists():
            return []
        return [self.stat(path.relative_to(self.root).as_posix()) for path in sorted(base.rglob("*")) if path.is_file()]  # type: ignore[list-item]


class CallbackAdapter:
    """CSI bridge for Drive, GitHub, S3 or another provider connector."""

    def __init__(
        self,
        adapter_id: str,
        kind: str,
        *,
        put_callback: Callable[[str, Path], dict[str, Any]],
        get_callback: Callable[[str, Path], dict[str, Any]],
        stat_callback: Callable[[str], dict[str, Any] | None],
        list_callback: Callable[[str], list[dict[str, Any]]],
        independent_hash_supported: bool,
    ) -> None:
        self.adapter_id = adapter_id
        self.kind = kind
        self.put_callback = put_callback
        self.get_callback = get_callback
        self.stat_callback = stat_callback
        self.list_callback = list_callback
        self.independent_hash_supported = independent_hash_supported

    def put(self, key: str, source: Path) -> dict[str, Any]:
        return self.put_callback(key, source)

    def get(self, key: str, destination: Path) -> dict[str, Any]:
        return self.get_callback(key, destination)

    def stat(self, key: str) -> dict[str, Any] | None:
        return self.stat_callback(key)

    def list(self, prefix: str = "") -> list[dict[str, Any]]:
        return self.list_callback(prefix)


class KwanDisk:
    SCHEMA = "kch.kwandisk.v0.1.0"

    def __init__(self, state_root: str | Path, policy: SyncPolicy) -> None:
        self.state_root = Path(state_root).resolve(strict=False)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.policy = policy
        self.database = self.state_root / "kwandisk.sqlite3"
        self.quarantine = self.state_root / "quarantine"
        self.quarantine.mkdir(exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS snapshots(
                    snapshot_id TEXT PRIMARY KEY, root TEXT NOT NULL, created_at TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL, file_count INTEGER NOT NULL, total_bytes INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sync_receipts(
                    receipt_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, adapter_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, gate TEXT NOT NULL, payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quarantine_receipts(
                    quarantine_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, purge_after TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def pressure(self, path: str | Path) -> dict[str, Any]:
        root = Path(path).resolve(strict=True)
        usage = shutil.disk_usage(root)
        if usage.free < self.policy.emergency_free_bytes:
            state, allowed = "EMERGENCY", False
        elif usage.free < self.policy.critical_free_bytes:
            state, allowed = "CRITICAL", False
        elif usage.free < self.policy.warning_free_bytes:
            state, allowed = "WARNING", True
        else:
            state, allowed = "GREEN", True
        return {
            "instance": str(root.anchor),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "free_ratio": usage.free / usage.total if usage.total else 0.0,
            "state": state,
            "nonessential_writes_allowed": allowed,
        }

    @staticmethod
    def _secret_findings(path: Path, relative: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for pattern in SENSITIVE_PATH_PATTERNS:
            if pattern.search(relative):
                findings.append({"kind": "SENSITIVE_PATH", "path": relative})
                break
        if path.stat().st_size <= 2 * 1024 * 1024:
            raw = path.read_bytes()
            for kind, pattern in SENSITIVE_CONTENT_PATTERNS.items():
                match = pattern.search(raw)
                if match:
                    findings.append(
                        {
                            "kind": kind,
                            "path": relative,
                            "line": raw[: match.start()].count(b"\n") + 1,
                            "match_sha256": sha256_bytes(match.group(0)),
                            "secret_value_exposed": False,
                        }
                    )
        return findings

    def inventory(self, root: str | Path, *, excluded_prefixes: Iterable[str] = ()) -> dict[str, Any]:
        source = Path(root).resolve(strict=True)
        prefixes = [PurePosixPath(item).parts for item in excluded_prefixes]
        entries: list[dict[str, Any]] = []
        excluded: list[dict[str, str]] = []
        findings: list[dict[str, Any]] = []

        def prefixed(parts: tuple[str, ...]) -> bool:
            return any(parts[: len(prefix)] == prefix for prefix in prefixes)

        def walk_error(error: OSError) -> None:
            path = Path(error.filename) if error.filename else source
            try:
                relative = path.relative_to(source).as_posix()
            except ValueError:
                relative = str(path)
            excluded.append(
                {
                    "path": relative,
                    "reason": f"ACCESS_ERROR:{getattr(error, 'winerror', None) or error.errno}",
                }
            )

        for current, dirs, files in os.walk(source, topdown=True, followlinks=False, onerror=walk_error):
            current_path = Path(current)
            relative_current = current_path.relative_to(source)
            kept: list[str] = []
            for name in sorted(dirs):
                relative = relative_current / name
                parts = PurePosixPath(relative.as_posix()).parts
                if name in DERIVED_DIRS or name.endswith(".egg-info"):
                    excluded.append({"path": relative.as_posix(), "reason": "DERIVED_REGENERABLE"})
                elif name in SEPARATE_CUSTODY_DIRS:
                    excluded.append({"path": relative.as_posix(), "reason": "REPOSITORY_METADATA_SEPARATE_CUSTODY"})
                elif prefixed(parts):
                    excluded.append({"path": relative.as_posix(), "reason": "POLICY_PREFIX"})
                else:
                    kept.append(name)
            dirs[:] = kept
            for name in sorted(files):
                path = current_path / name
                relative = path.relative_to(source).as_posix()
                parts = PurePosixPath(relative).parts
                if prefixed(parts):
                    excluded.append({"path": relative, "reason": "POLICY_PREFIX"})
                    continue
                if path.is_symlink():
                    excluded.append({"path": relative, "reason": "SYMLINK_NOT_FOLLOWED"})
                    continue
                try:
                    stat = path.stat()
                    digest = sha256_file(path)
                    file_findings = self._secret_findings(path, relative)
                except OSError as error:
                    excluded.append(
                        {
                            "path": relative,
                            "reason": f"ACCESS_ERROR:{getattr(error, 'winerror', None) or error.errno}",
                        }
                    )
                    continue
                findings.extend(file_findings)
                entries.append(
                    {
                        "path": relative,
                        "bytes": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                        "sha256": digest,
                        "sensitive": bool(file_findings),
                        "large": stat.st_size >= self.policy.large_file_bytes,
                    }
                )
        entries.sort(key=lambda item: item["path"])
        excluded.sort(key=lambda item: item["path"])
        manifest_core = {
            "schema": "kch.kwandisk.inventory.v0.1.0",
            "root": str(source),
            "policy_id": self.policy.policy_id,
            "entries": entries,
            "excluded": excluded,
            "secret_findings": findings,
        }
        manifest_hash = sha256_json(manifest_core)
        content_manifest = [
            {"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]}
            for item in entries
        ]
        content_manifest_hash = sha256_json(content_manifest)
        snapshot_id = f"SNAP-{manifest_hash[:20]}"
        payload = {
            **manifest_core,
            "snapshot_id": snapshot_id,
            "manifest_sha256": manifest_hash,
            "content_manifest_sha256": content_manifest_hash,
            "created_at": utc_now(),
            "file_count": len(entries),
            "total_bytes": sum(int(item["bytes"]) for item in entries),
        }
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?,?,?,?)",
                (
                    snapshot_id,
                    str(source),
                    payload["created_at"],
                    manifest_hash,
                    payload["file_count"],
                    payload["total_bytes"],
                    canonical_json(payload),
                ),
            )
        return payload

    @staticmethod
    def _duplicate_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[tuple[str, int], list[str]] = {}
        for item in entries:
            groups.setdefault((item["sha256"], item["bytes"]), []).append(item["path"])
        return [
            {
                "sha256": digest,
                "bytes_each": size,
                "paths": sorted(paths),
                "recoverable_bytes_if_one_canonical_copy": size * (len(paths) - 1),
            }
            for (digest, size), paths in sorted(groups.items())
            if len(paths) > 1 and size > 0
        ]

    def analyze(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        duplicates = self._duplicate_groups(snapshot["entries"])
        derived_bytes = 0
        for item in snapshot["excluded"]:
            if item["reason"] != "DERIVED_REGENERABLE":
                continue
            path = Path(snapshot["root"]) / item["path"]
            if path.is_dir():
                derived_bytes += sum(child.stat().st_size for child in path.rglob("*") if child.is_file())
        pressure = self.pressure(snapshot["root"])
        urgent: list[dict[str, Any]] = []
        if pressure["state"] in {"CRITICAL", "EMERGENCY"}:
            urgent.append({"action": "BLOCK_NONESSENTIAL_WRITES", "reason": pressure["state"]})
        if snapshot["secret_findings"]:
            urgent.append({"action": "BLOCK_UNSANITIZED_CLOUD_SYNC", "count": len(snapshot["secret_findings"])})
        soon = []
        if derived_bytes:
            soon.append({"action": "QUARANTINE_DERIVED_CACHES_AFTER_SCOPE_CONFIRMATION", "recoverable_bytes": derived_bytes})
        if duplicates:
            soon.append({"action": "REVIEW_EXACT_DUPLICATES", "recoverable_bytes": sum(item["recoverable_bytes_if_one_canonical_copy"] for item in duplicates)})
        optimize = [
            {"action": "TIER_LARGE_FILE", "path": item["path"], "bytes": item["bytes"], "suggested_tier": "COLD"}
            for item in snapshot["entries"]
            if item["large"]
        ]
        return {
            "schema": "kch.kwandisk.analysis.v0.1.0",
            "snapshot_id": snapshot["snapshot_id"],
            "pressure": pressure,
            "duplicates": duplicates,
            "derived_regenerable_bytes": derived_bytes,
            "recommendations": {"IMMEDIATE": urgent, "SOON": soon, "OPTIMIZE": optimize},
            "automatic_deletion": False,
        }

    def sync(
        self,
        snapshot: dict[str, Any],
        adapter: StorageAdapter,
        namespace: str,
        *,
        authority: str,
        sensitive_upload_authorized: bool = False,
    ) -> dict[str, Any]:
        if authority not in {"USER", f"POLICY:{self.policy.policy_id}"}:
            raise PermissionError("exact USER or configured KwanDisk policy authority required")
        if authority.startswith("POLICY:") and not self.policy.auto_sync_non_sensitive:
            raise PermissionError("policy does not authorize automatic synchronization")
        if not namespace.strip("/"):
            raise ValueError("a non-empty provider namespace is required")
        if snapshot["secret_findings"] and not (
            sensitive_upload_authorized and self.policy.cloud_target_encrypted
        ):
            raise SecretExposureError("sensitive material blocked before cloud synchronization")
        source = Path(snapshot["root"])
        transfers: list[dict[str, Any]] = []
        for item in snapshot["entries"]:
            key = f"{namespace.strip('/')}/{item['path']}"
            existing = adapter.stat(key)
            if existing and existing.get("bytes") == item["bytes"] and existing.get("sha256") == item["sha256"]:
                transfers.append({"path": item["path"], "key": key, "action": "UNCHANGED", "source_sha256": item["sha256"], "remote": existing, "exact": True})
                continue
            remote = adapter.put(key, source / item["path"])
            size_ok = remote.get("bytes") == item["bytes"]
            hash_value = remote.get("sha256")
            hash_ok = hash_value == item["sha256"] if adapter.independent_hash_supported else None
            if not size_ok or (adapter.independent_hash_supported and not hash_ok):
                raise RemoteVerificationError(f"remote verification failed for {item['path']}")
            transfers.append(
                {
                    "path": item["path"],
                    "key": key,
                    "action": "UPLOADED",
                    "source_sha256": item["sha256"],
                    "remote": remote,
                    "exact": bool(hash_ok),
                    "verification": "SIZE_AND_INDEPENDENT_HASH" if adapter.independent_hash_supported else "SIZE_IDENTITY_ONLY",
                }
            )
        exact = all(item["exact"] for item in transfers)
        gate = "PASS_EXACT_REMOTE_CUSTODY" if exact else "PASS_REMOTE_SIZE_IDENTITY_HASH_UNAVAILABLE"
        receipt_core = {
            "schema": "kch.kwandisk.sync-receipt.v0.1.0",
            "snapshot_id": snapshot["snapshot_id"],
            "manifest_sha256": snapshot["manifest_sha256"],
            "content_manifest_sha256": snapshot["content_manifest_sha256"],
            "adapter_id": adapter.adapter_id,
            "adapter_kind": adapter.kind,
            "namespace": namespace,
            "transfers": transfers,
            "gate": gate,
            "cleanup_eligible": exact or not self.policy.exact_remote_hash_required_for_cleanup,
            "automatic_deletion": False,
            "created_at": utc_now(),
        }
        receipt_id = f"SYNC-{sha256_json(receipt_core)[:20]}"
        receipt = {**receipt_core, "receipt_id": receipt_id, "receipt_sha256": sha256_json(receipt_core)}
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO sync_receipts VALUES(?,?,?,?,?,?)",
                (receipt_id, snapshot["snapshot_id"], adapter.adapter_id, receipt["created_at"], gate, canonical_json(receipt)),
            )
        return receipt

    def reconstruct(
        self,
        receipt: dict[str, Any],
        adapter: StorageAdapter,
        destination: str | Path,
        *,
        actor: str,
    ) -> dict[str, Any]:
        if actor != "USER":
            raise PermissionError("exact USER authority required for reconstruction")
        target_root = Path(destination).resolve(strict=False)
        if target_root.exists():
            raise FileExistsError(target_root)
        target_root.mkdir(parents=True)
        results = []
        try:
            for item in receipt["transfers"]:
                destination_path = safe_child(target_root, item["path"])
                result = adapter.get(item["key"], destination_path)
                expected = item["remote"]
                if result.get("bytes") != expected.get("bytes") or result.get("sha256") != item["source_sha256"]:
                    raise RemoteVerificationError(f"reconstruction mismatch: {item['path']}")
                results.append({"path": item["path"], **result})
        except Exception:
            shutil.rmtree(target_root, ignore_errors=True)
            raise
        content_manifest = [
            {"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]}
            for item in sorted(results, key=lambda value: value["path"])
        ]
        content_manifest_hash = sha256_json(content_manifest)
        if content_manifest_hash != receipt["content_manifest_sha256"]:
            shutil.rmtree(target_root, ignore_errors=True)
            raise RemoteVerificationError("reconstructed content manifest differs from synchronized source")
        return {
            "schema": "kch.kwandisk.reconstruction.v0.1.0",
            "status": "PASS",
            "destination": str(target_root),
            "files": results,
            "file_count": len(results),
            "content_manifest_sha256": content_manifest_hash,
        }

    def quarantine_paths(
        self,
        root: str | Path,
        relative_paths: list[str],
        sync_receipt: dict[str, Any],
        *,
        actor: str,
        exact_authorization_id: str,
    ) -> dict[str, Any]:
        if actor != "USER" or not exact_authorization_id.strip():
            raise PermissionError("exact USER quarantine authorization required")
        if sync_receipt.get("cleanup_eligible") is not True:
            raise RemoteVerificationError("remote custody is insufficient for cleanup")
        source = Path(root).resolve(strict=True)
        remote_custody = {item["path"]: item for item in sync_receipt.get("transfers", [])}
        quarantine_id = f"Q-{uuid.uuid4().hex[:16]}"
        target_root = self.quarantine / quarantine_id
        target_root.mkdir()
        moved = []
        for relative in sorted(set(relative_paths)):
            if relative not in remote_custody or remote_custody[relative].get("exact") is not True:
                raise RemoteVerificationError(f"path lacks exact remote custody: {relative}")
            source_path = safe_child(source, relative).resolve(strict=True)
            if not source_path.is_file():
                raise FileNotFoundError(source_path)
            target = safe_child(target_root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = sha256_file(source_path)
            if digest != remote_custody[relative].get("source_sha256"):
                raise RemoteVerificationError(f"local path changed after synchronized custody: {relative}")
            shutil.move(str(source_path), str(target))
            moved.append({"path": relative, "bytes": target.stat().st_size, "sha256": digest})
        purge_after = datetime.now(UTC) + timedelta(days=self.policy.quarantine_days)
        receipt = {
            "schema": "kch.kwandisk.quarantine-receipt.v0.1.0",
            "quarantine_id": quarantine_id,
            "source_root": str(source),
            "quarantine_root": str(target_root),
            "sync_receipt_id": sync_receipt["receipt_id"],
            "authorization_id": exact_authorization_id,
            "moved": moved,
            "created_at": utc_now(),
            "purge_after": purge_after.isoformat().replace("+00:00", "Z"),
            "recoverable": True,
            "purged": False,
        }
        with self._connect() as db:
            db.execute(
                "INSERT INTO quarantine_receipts VALUES(?,?,?,?)",
                (quarantine_id, receipt["created_at"], receipt["purge_after"], canonical_json(receipt)),
            )
        return receipt

    def restore_quarantine(self, quarantine_receipt: dict[str, Any], *, actor: str) -> dict[str, Any]:
        if actor != "USER":
            raise PermissionError("exact USER authority required for restore")
        source_root = Path(quarantine_receipt["source_root"])
        quarantine_root = Path(quarantine_receipt["quarantine_root"])
        restored = []
        for item in quarantine_receipt["moved"]:
            source = safe_child(quarantine_root, item["path"]).resolve(strict=True)
            target = safe_child(source_root, item["path"])
            if target.exists():
                raise FileExistsError(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            if sha256_file(target) != item["sha256"]:
                raise RemoteVerificationError(f"restored hash mismatch: {item['path']}")
            restored.append(item)
        return {"schema": "kch.kwandisk.quarantine-restore.v0.1.0", "status": "PASS", "restored": restored}

    def startup_advisory(self, roots: Iterable[str | Path]) -> dict[str, Any]:
        instances = [self.pressure(root) for root in roots]
        highest = max(instances, key=lambda item: {"GREEN": 0, "WARNING": 1, "CRITICAL": 2, "EMERGENCY": 3}[item["state"]])
        return {
            "schema": "kch.kwandisk.startup-advisory.v0.1.0",
            "instances": instances,
            "highest_pressure": highest["state"],
            "proactive_inventory_enabled": self.policy.auto_inventory,
            "proactive_sync_enabled": self.policy.auto_sync_non_sensitive,
            "automatic_deletion": False,
            "message": (
                f"KwanDisk activo: presión máxima {highest['state']}; inventario proactivo "
                f"{'activado' if self.policy.auto_inventory else 'desactivado'}; eliminación automática desactivada."
            ),
        }
