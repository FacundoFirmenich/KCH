from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

ROOT_KINDS = frozenset({"ADHOC", "CODEX_PROJECTS", "AGENT_STATE", "TEMP"})
CACHE_DIRS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
CONDITIONAL_DIRS = frozenset({"node_modules", ".venv", "venv"})
TEMP_SUFFIXES = (".partial", ".tmp", ".temp", ".download", ".crdownload")
LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb")
PYTHON_REBUILD_MARKERS = ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "uv.lock", "poetry.lock")
PROTECTED_AGENT_TOP_LEVEL = frozenset({
    "AGENTS.md", "auth.json", "config.toml", "sessions", "archived_sessions",
    "memories", "skills", "plugins", "rules", "automations", "attachments",
    "thread-writer-locks", "state_5.sqlite", "thread_history_1.sqlite",
    "logs_2.sqlite", "memories_1.sqlite", "goals_1.sqlite",
})
ALLOWED_CLEANUP_CLASSES = frozenset({"REGENERABLE", "TRANSIENT", "REPLICATED_CUSTODY"})


class GeneralCleanupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class JurisdictionRoot:
    kind: str
    path: str
    source: str
    exists: bool


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve(strict=False)
    if candidate == root or root not in candidate.parents:
        raise GeneralCleanupError(f"broad or escaped cleanup target blocked: {relative}")
    return candidate


def _path_fingerprint(path: Path) -> dict[str, Any]:
    if path.is_file():
        stat = path.stat()
        core = {
            "kind": "FILE",
            "bytes": stat.st_size,
            "latest_mtime_ns": stat.st_mtime_ns,
            "sha256": _sha256_file(path),
        }
        return {**core, "signature": _sha256_json(core), "file_count": 1}
    if not path.is_dir():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    latest = path.stat().st_mtime_ns
    total = 0
    for child in sorted(item for item in path.rglob("*") if item.is_file() and not item.is_symlink()):
        stat = child.stat()
        latest = max(latest, stat.st_mtime_ns)
        total += stat.st_size
        rows.append({
            "path": child.relative_to(path).as_posix(),
            "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        })
    core = {
        "kind": "DIRECTORY",
        "bytes": total,
        "latest_mtime_ns": latest,
        "file_count": len(rows),
        "tree_metadata_sha256": _sha256_json(rows),
    }
    return {**core, "signature": _sha256_json(core)}


def _is_active(path: Path, active_paths: tuple[Path, ...]) -> bool:
    return any(path == active or path in active.parents or active in path.parents for active in active_paths)


def _protected(root_kind: str, relative: Path) -> bool:
    if any(part == ".git" for part in relative.parts):
        return True
    if root_kind != "AGENT_STATE" or not relative.parts:
        return False
    first = relative.parts[0]
    if first in PROTECTED_AGENT_TOP_LEVEL:
        return True
    return first.endswith((".sqlite", ".sqlite-wal", ".sqlite-shm"))


def _regenerable_reason(path: Path) -> str | None:
    if path.name in CACHE_DIRS:
        return "KNOWN_DERIVED_CACHE"
    if path.name == "node_modules" and any((path.parent / name).is_file() for name in LOCKFILES):
        return "PACKAGE_LOCK_PRESENT"
    if path.name in {".venv", "venv"} and any((path.parent / name).is_file() for name in PYTHON_REBUILD_MARKERS):
        return "PYTHON_REBUILD_MARKER_PRESENT"
    return None


def _transient_reason(path: Path) -> str | None:
    lowered = path.name.lower()
    if lowered.endswith(TEMP_SUFFIXES):
        return "KNOWN_TEMP_SUFFIX"
    if path.is_file() and path.stat().st_size == 0 and (".tmp-" in lowered or lowered.startswith("tmp-")):
        return "ZERO_BYTE_TEMPORARY"
    return None


class GeneralCleanup:
    SCHEMA = "kch.kwandisk.general-cleanup.v0.2.0"

    @staticmethod
    def discover(
        *,
        home: str | Path | None = None,
        adhoc_roots: Iterable[str | Path] = (),
        agent_roots: Iterable[str | Path] = (),
        temp_roots: Iterable[str | Path] = (),
    ) -> dict[str, Any]:
        user_home = Path(home).resolve(strict=False) if home else Path.home().resolve(strict=False)
        candidates: list[tuple[str, Path, str]] = [
            ("CODEX_PROJECTS", user_home / "Documents" / "Codex", "DEFAULT"),
            ("AGENT_STATE", user_home / ".codex", "DEFAULT"),
            ("AGENT_STATE", user_home / ".agents", "DEFAULT"),
        ]
        candidates.extend(("ADHOC", Path(item), "EXPLICIT") for item in adhoc_roots)
        candidates.extend(("AGENT_STATE", Path(item), "EXPLICIT") for item in agent_roots)
        environment_temp = [os.environ.get(name) for name in ("TEMP", "TMP", "TMPDIR")]
        candidates.extend(("TEMP", Path(item), f"ENV:{name}") for name, item in zip(("TEMP", "TMP", "TMPDIR"), environment_temp) if item)
        candidates.append(("TEMP", Path(tempfile.gettempdir()), "PYTHON_TEMP"))
        if os.name == "nt":
            candidates.append(("TEMP", Path("C:/tmp"), "WINDOWS_CONVENTION"))
        candidates.extend(("TEMP", Path(item), "EXPLICIT") for item in temp_roots)

        roots: list[JurisdictionRoot] = []
        seen: set[str] = set()
        for kind, raw, source in candidates:
            resolved = raw.expanduser().resolve(strict=False)
            key = os.path.normcase(str(resolved))
            if key in seen:
                continue
            seen.add(key)
            roots.append(JurisdictionRoot(kind, str(resolved), source, resolved.exists()))
        return {
            "schema": "kch.kwandisk.jurisdictions.v0.2.0",
            "storage_priority": [
                "GOOGLE_DRIVE",
                "GITHUB_WITHIN_PROVIDER_LIMITS",
                "LOCAL_OR_VPS_ONLY_EXPLICIT_OR_INDISPENSABLE",
            ],
            "roots": [asdict(item) for item in roots],
            "automatic_deletion": False,
        }

    @staticmethod
    def plan(
        discovery: dict[str, Any],
        *,
        older_than_hours: float = 24.0,
        active_paths: Iterable[str | Path] = (),
        replicated_receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if older_than_hours < 0:
            raise ValueError("older_than_hours must be non-negative")
        active = tuple(Path(item).resolve(strict=False) for item in active_paths)
        now_ns = datetime.now(UTC).timestamp() * 1_000_000_000
        threshold_ns = older_than_hours * 3600 * 1_000_000_000
        candidates: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        replicated = (replicated_receipt or {}).get("entries", [])

        for root_item in discovery.get("roots", []):
            kind = root_item.get("kind")
            if kind not in ROOT_KINDS or not root_item.get("exists"):
                continue
            root = Path(root_item["path"]).resolve(strict=True)

            for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
                current_path = Path(current)
                kept: list[str] = []
                for name in sorted(dirs):
                    path = current_path / name
                    relative = path.relative_to(root)
                    if _protected(kind, relative) or _is_active(path, active):
                        blocked.append({"root": str(root), "path": relative.as_posix(), "reason": "PROTECTED_OR_ACTIVE"})
                        continue
                    reason = _regenerable_reason(path)
                    if reason is None:
                        kept.append(name)
                        continue
                    try:
                        fingerprint = _path_fingerprint(path)
                    except (FileNotFoundError, OSError):
                        blocked.append({"root": str(root), "path": relative.as_posix(), "reason": "TARGET_CHANGED_OR_UNREADABLE"})
                        continue
                    age_ns = now_ns - fingerprint["latest_mtime_ns"]
                    if age_ns < threshold_ns:
                        blocked.append({"root": str(root), "path": relative.as_posix(), "reason": "TOO_RECENT"})
                        continue
                    candidates.append({
                        "root": str(root), "root_kind": kind, "path": relative.as_posix(),
                        "classification": "REGENERABLE", "reason": reason, **fingerprint,
                    })
                dirs[:] = kept
                for name in sorted(files):
                    path = current_path / name
                    relative = path.relative_to(root)
                    if _protected(kind, relative) or _is_active(path, active):
                        continue
                    reason = _transient_reason(path)
                    if reason is None:
                        continue
                    try:
                        fingerprint = _path_fingerprint(path)
                    except (FileNotFoundError, OSError):
                        blocked.append({"root": str(root), "path": relative.as_posix(), "reason": "TARGET_CHANGED_OR_UNREADABLE"})
                        continue
                    if now_ns - fingerprint["latest_mtime_ns"] < threshold_ns:
                        continue
                    candidates.append({
                        "root": str(root), "root_kind": kind, "path": relative.as_posix(),
                        "classification": "TRANSIENT", "reason": reason, **fingerprint,
                    })

            for item in replicated:
                if item.get("root") != str(root):
                    continue
                relative = str(item.get("path", ""))
                try:
                    path = _safe_child(root, relative)
                except GeneralCleanupError as error:
                    blocked.append({"root": str(root), "path": relative, "reason": str(error)})
                    continue
                if not path.exists() or _protected(kind, Path(relative)) or _is_active(path, active):
                    blocked.append({"root": str(root), "path": relative, "reason": "MISSING_PROTECTED_OR_ACTIVE"})
                    continue
                if not (
                    item.get("drive_verified") is True
                    and item.get("github_verified") is True
                    and item.get("recovery_verified") is True
                ):
                    blocked.append({"root": str(root), "path": relative, "reason": "BACKUP_CHAIN_INCOMPLETE"})
                    continue
                try:
                    fingerprint = _path_fingerprint(path)
                except (FileNotFoundError, OSError):
                    blocked.append({"root": str(root), "path": relative, "reason": "TARGET_CHANGED_OR_UNREADABLE"})
                    continue
                if fingerprint["signature"] != item.get("local_signature"):
                    blocked.append({"root": str(root), "path": relative, "reason": "LOCAL_CHANGED_AFTER_RECEIPT"})
                    continue
                candidates.append({
                    "root": str(root), "root_kind": kind, "path": relative,
                    "classification": "REPLICATED_CUSTODY",
                    "reason": "DRIVE_GITHUB_RECOVERY_VERIFIED", **fingerprint,
                })

        candidates.sort(key=lambda item: (item["root"], item["path"], item["classification"]))
        blocked.sort(key=lambda item: (item["root"], item["path"], item["reason"]))
        core = {
            "schema": "kch.kwandisk.cleanup-plan.v0.2.0",
            "storage_priority": discovery.get("storage_priority", []),
            "older_than_hours": older_than_hours,
            "candidates": candidates,
            "blocked": blocked,
            "candidate_bytes": sum(int(item["bytes"]) for item in candidates),
            "automatic_deletion": False,
            "requires_exact_user_authorization": True,
        }
        return {**core, "plan_sha256": _sha256_json(core)}

    @staticmethod
    def execute(
        plan: dict[str, Any],
        *,
        actor: str,
        exact_authorization_id: str,
        expected_plan_sha256: str,
    ) -> dict[str, Any]:
        if actor != "USER" or not exact_authorization_id.strip():
            raise PermissionError("exact USER cleanup authorization required")
        observed_plan_sha256 = plan.get("plan_sha256")
        core = {key: value for key, value in plan.items() if key != "plan_sha256"}
        if observed_plan_sha256 != _sha256_json(core) or expected_plan_sha256 != observed_plan_sha256:
            raise GeneralCleanupError("cleanup plan identity mismatch")
        removed: list[dict[str, Any]] = []
        already_absent: list[dict[str, str]] = []
        for item in plan.get("candidates", []):
            if item.get("classification") not in ALLOWED_CLEANUP_CLASSES:
                raise GeneralCleanupError(f"unapproved classification: {item.get('classification')}")
            root = Path(item["root"]).resolve(strict=True)
            target = _safe_child(root, item["path"])
            if _protected(item["root_kind"], Path(item["path"])):
                raise GeneralCleanupError(f"protected target blocked: {item['path']}")
            if not target.exists():
                already_absent.append({"root": str(root), "path": item["path"]})
                continue
            try:
                observed = _path_fingerprint(target)
            except FileNotFoundError:
                already_absent.append({"root": str(root), "path": item["path"]})
                continue
            if observed["signature"] != item.get("signature"):
                raise GeneralCleanupError(f"target changed after plan: {item['path']}")
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            removed.append({
                "root": str(root), "path": item["path"],
                "classification": item["classification"], "bytes": item["bytes"],
                "signature": item["signature"],
            })
        return {
            "schema": "kch.kwandisk.cleanup-receipt.v0.2.0",
            "status": "PASS",
            "authorization_id": exact_authorization_id,
            "plan_sha256": observed_plan_sha256,
            "removed": removed,
            "already_absent": already_absent,
            "freed_bytes": sum(int(item["bytes"]) for item in removed),
            "automatic_deletion": False,
            "recovery_boundary": "REGENERABLE_OR_TRANSIENT_OR_VERIFIED_DRIVE_GITHUB_CUSTODY_ONLY",
        }
