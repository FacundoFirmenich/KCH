from __future__ import annotations

import json
import os
import stat
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .constitutional import Actor, ConstitutionalAuthorityError
from .contracts import safe_child, sha256_bytes, sha256_json, sqlite_connection
from .recovery import RecoveryVault


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class CheckpointManager:
    """Full checkpoints and content-addressed structured persistence with exact reconstruction."""

    def __init__(self, root: str | Path, managed_roots: dict[str, str | Path]):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.blobs = self.root / "blobs"
        self.blobs.mkdir(exist_ok=True)
        self.manifests = self.root / "manifests"
        self.manifests.mkdir(exist_ok=True)
        self.full = self.root / "full"
        self.full.mkdir(exist_ok=True)
        self.restore_root = self.root / "restores"
        self.restore_root.mkdir(exist_ok=True)
        self.temp = self.root / "temp"
        self.temp.mkdir(exist_ok=True)
        self.vault = RecoveryVault(self.root / "recovery")
        self.managed_roots = {name: Path(path).resolve() for name, path in managed_roots.items()}
        for name, path in self.managed_roots.items():
            if not path.is_dir():
                raise NotADirectoryError(f"{name}: {path}")

    @staticmethod
    def _require_user(actor: Actor) -> None:
        if actor is not Actor.USER:
            raise ConstitutionalAuthorityError(
                "checkpoint/restore execution requires USER authority"
            )

    @staticmethod
    def _skip(path: Path) -> bool:
        return any(
            part in {"__pycache__", ".pytest_cache", ".git"} for part in path.parts
        ) or path.name.endswith(("-wal", "-shm"))

    def _files(self) -> Iterable[tuple[str, Path, str]]:
        for root_name, root in sorted(self.managed_roots.items()):
            for path in sorted(
                (item for item in root.rglob("*") if item.is_file()),
                key=lambda item: item.relative_to(root).as_posix(),
            ):
                if path.resolve().is_relative_to(self.root):
                    continue
                if not self._skip(path.relative_to(root)):
                    yield root_name, path, path.relative_to(root).as_posix()

    def estimate(self) -> dict[str, Any]:
        rows = []
        total = 0
        for root_name, path, relative in self._files():
            size = path.stat().st_size
            total += size
            rows.append({"root": root_name, "path": relative, "bytes": size})
        known = {path.name for path in self.blobs.glob("*/*") if path.is_file()}
        return {
            "schema": "kch.checkpoint-estimate.v0.1.0",
            "file_count": len(rows),
            "logical_bytes": total,
            "full_checkpoint_worst_case_bytes": total,
            "structured_new_bytes_upper_bound": total,
            "existing_blob_count": len(known),
            "warning": "FULL_CHECKPOINT_CAN_OCCUPY_A_VERY_LARGE_AMOUNT_OF_DISK",
            "full_requires_explicit_confirmation": True,
        }

    def _stable_bytes(self, path: Path) -> tuple[bytes, str]:
        header = path.read_bytes()[:16]
        if header == b"SQLite format 3\x00":
            target = self.temp / f"{uuid.uuid4()}.sqlite3"
            uri = f"file:{path.as_posix()}?mode=ro"
            with (
                sqlite_connection(uri, uri=True) as source,
                sqlite_connection(target) as destination,
            ):
                source.backup(destination)
            raw = target.read_bytes()
            target.unlink()
            return raw, "SQLITE_BACKUP_API"
        return path.read_bytes(), "DIRECT_STABLE_FILE_READ"

    def _store_blob(self, raw: bytes) -> tuple[str, Path, bool]:
        digest = sha256_bytes(raw)
        target = self.blobs / digest[:2] / digest
        created = False
        if not target.is_file():
            target.parent.mkdir(exist_ok=True)
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(raw)
            os.replace(temporary, target)
            created = True
        if sha256_bytes(target.read_bytes()) != digest:
            raise ValueError("checkpoint blob verification failed")
        return digest, target, created

    def create_structured(self, label: str, *, actor: Actor) -> dict[str, Any]:
        self._require_user(actor)
        previous = None
        manifests = sorted(self.manifests.glob("*.json"), key=lambda path: path.stat().st_mtime_ns)
        if manifests:
            previous = json.loads(manifests[-1].read_text(encoding="utf-8"))
        entries = []
        new_bytes = 0
        reused_bytes = 0
        for root_name, path, relative in self._files():
            raw, capture_method = self._stable_bytes(path)
            digest, _blob, created = self._store_blob(raw)
            mode = stat.S_IMODE(path.stat().st_mode)
            entries.append(
                {
                    "root": root_name,
                    "path": relative,
                    "bytes": len(raw),
                    "sha256": digest,
                    "mode": mode,
                    "capture_method": capture_method,
                }
            )
            if created:
                new_bytes += len(raw)
            else:
                reused_bytes += len(raw)
        checkpoint_id = f"SCP-{uuid.uuid4()}"
        previous_map = (
            {}
            if previous is None
            else {(item["root"], item["path"]): item["sha256"] for item in previous["files"]}
        )
        current_map = {(item["root"], item["path"]): item["sha256"] for item in entries}
        graph = {
            "previous_checkpoint_id": None if previous is None else previous["checkpoint_id"],
            "added": [list(key) for key in sorted(current_map.keys() - previous_map.keys())],
            "removed": [list(key) for key in sorted(previous_map.keys() - current_map.keys())],
            "modified": [
                list(key)
                for key in sorted(current_map.keys() & previous_map.keys())
                if current_map[key] != previous_map[key]
            ],
            "unchanged": sum(
                current_map[key] == previous_map[key]
                for key in current_map.keys() & previous_map.keys()
            ),
        }
        manifest = {
            "schema": "kch.structured-checkpoint.v0.1.0",
            "checkpoint_id": checkpoint_id,
            "label": label,
            "created_at": utc_now(),
            "roots": {key: str(value) for key, value in self.managed_roots.items()},
            "files": entries,
            "files_hash": sha256_json(entries),
            "graph": graph,
            "logical_bytes": sum(item["bytes"] for item in entries),
            "new_blob_bytes": new_bytes,
            "deduplicated_reused_bytes": reused_bytes,
            "reconstructable_exact_bytes": True,
        }
        path = self.manifests / f"{checkpoint_id}.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        custody = self.vault.save_json(
            f"structured/{checkpoint_id}.json",
            manifest,
            kind="STRUCTURED_CHECKPOINT",
            actor="USER",
            operation="CREATE_INCREMENTAL",
        )
        return {**manifest, "manifest_path": str(path), "custody": custody}

    def full_plan(self, label: str) -> dict[str, Any]:
        estimate = self.estimate()
        plan_id = f"FULLPLAN-{uuid.uuid4()}"
        value = {
            "plan_id": plan_id,
            "label": label,
            "state": "AWAITING_EXPLICIT_LARGE_CHECKPOINT_CONFIRMATION",
            **estimate,
        }
        self.vault.save_json(
            f"full-plans/{plan_id}.json",
            value,
            kind="FULL_CHECKPOINT_PLAN",
            actor="KCH_SYSTEM",
            operation="PLAN_WARN",
        )
        return value

    def create_full(
        self, plan_id: str, *, confirm_large_checkpoint: bool, actor: Actor
    ) -> dict[str, Any]:
        self._require_user(actor)
        if not confirm_large_checkpoint:
            return {"plan_id": plan_id, "state": "NOT_EXECUTED_USER_DID_NOT_CONFIRM"}
        plan = json.loads(
            str(self.vault.latest(f"full-plans/{plan_id}.json", decode=True)["content"])
        )
        checkpoint_id = f"FCP-{uuid.uuid4()}"
        target = self.full / f"{checkpoint_id}.zip"
        entries = []
        with zipfile.ZipFile(
            target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for root_name, path, relative in self._files():
                raw, capture_method = self._stable_bytes(path)
                arcname = f"roots/{root_name}/{relative}"
                info = zipfile.ZipInfo(arcname, (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, raw)
                entries.append(
                    {
                        "root": root_name,
                        "path": relative,
                        "bytes": len(raw),
                        "sha256": sha256_bytes(raw),
                        "capture_method": capture_method,
                    }
                )
            manifest = {
                "schema": "kch.full-checkpoint.v0.1.0",
                "checkpoint_id": checkpoint_id,
                "label": plan["label"],
                "files": entries,
                "files_hash": sha256_json(entries),
                "created_at": utc_now(),
            }
            info = zipfile.ZipInfo("FULL_CHECKPOINT_MANIFEST.json", (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        if zipfile.ZipFile(target).testzip() is not None:
            raise ValueError("full checkpoint CRC gate failed")
        receipt = {
            "plan_id": plan_id,
            "checkpoint_id": checkpoint_id,
            "state": "FULL_CHECKPOINT_CREATED",
            "path": str(target),
            "bytes": target.stat().st_size,
            "sha256": sha256_bytes(target.read_bytes()),
            "logical_bytes": sum(item["bytes"] for item in entries),
            "file_count": len(entries),
        }
        self.vault.save_json(
            f"full/{checkpoint_id}.json",
            receipt,
            kind="FULL_CHECKPOINT_RECEIPT",
            actor="USER",
            operation="CREATE_CONFIRMED",
        )
        return receipt

    def get_manifest(self, checkpoint_id: str) -> dict[str, Any]:
        path = self.manifests / f"{checkpoint_id}.json"
        if not path.is_file():
            raise KeyError(checkpoint_id)
        value = json.loads(path.read_text(encoding="utf-8"))
        if sha256_json(value["files"]) != value["files_hash"]:
            raise ValueError("structured manifest integrity failure")
        return value

    def diff_current(self, checkpoint_id: str) -> dict[str, Any]:
        manifest = self.get_manifest(checkpoint_id)
        desired = {(item["root"], item["path"]): item for item in manifest["files"]}
        current = {}
        for root_name, path, relative in self._files():
            raw, _method = self._stable_bytes(path)
            current[(root_name, relative)] = sha256_bytes(raw)
        return {
            "checkpoint_id": checkpoint_id,
            "missing_now": [list(key) for key in sorted(desired.keys() - current.keys())],
            "extra_now": [list(key) for key in sorted(current.keys() - desired.keys())],
            "changed_now": [
                list(key)
                for key in sorted(current.keys() & desired.keys())
                if current[key] != desired[key]["sha256"]
            ],
            "restoration_executed": False,
        }

    def restore_to_new_root(
        self, checkpoint_id: str, destination: str | Path, *, actor: Actor
    ) -> dict[str, Any]:
        self._require_user(actor)
        manifest = self.get_manifest(checkpoint_id)
        base = Path(destination).resolve()
        if base.exists() and any(base.iterdir()):
            raise ValueError("structured restore requires a new or empty destination")
        base.mkdir(parents=True, exist_ok=True)
        written = []
        for item in manifest["files"]:
            target = safe_child(base, Path(item["root"]) / Path(item["path"]))
            target.parent.mkdir(parents=True, exist_ok=True)
            blob = self.blobs / item["sha256"][:2] / item["sha256"]
            raw = blob.read_bytes()
            if sha256_bytes(raw) != item["sha256"]:
                raise ValueError("restore blob hash mismatch")
            target.write_bytes(raw)
            os.chmod(target, item["mode"])
            written.append({"path": str(target), "sha256": item["sha256"]})
        verification = []
        for item in manifest["files"]:
            target = base / item["root"] / Path(item["path"])
            verification.append(sha256_bytes(target.read_bytes()) == item["sha256"])
        receipt = {
            "checkpoint_id": checkpoint_id,
            "state": "RESTORED_TO_NEW_ROOT",
            "destination": str(base),
            "file_count": len(written),
            "all_hashes_verified": all(verification),
            "source_manifest_hash": manifest["files_hash"],
        }
        self.vault.save_json(
            f"restores/{uuid.uuid4()}.json",
            receipt,
            kind="STRUCTURED_RESTORE_RECEIPT",
            actor="USER",
            operation="RESTORE_NEW_ROOT",
        )
        return receipt

    def trace_file(self, root_name: str, relative_path: str) -> list[dict[str, Any]]:
        history = []
        for path in sorted(self.manifests.glob("*.json"), key=lambda item: item.stat().st_mtime_ns):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            item = next(
                (
                    row
                    for row in manifest["files"]
                    if row["root"] == root_name and row["path"] == relative_path
                ),
                None,
            )
            history.append(
                {
                    "checkpoint_id": manifest["checkpoint_id"],
                    "created_at": manifest["created_at"],
                    "state": "ABSENT" if item is None else "PRESENT",
                    "sha256": None if item is None else item["sha256"],
                    "bytes": None if item is None else item["bytes"],
                }
            )
        return history

    def status(self) -> dict[str, Any]:
        manifests = list(self.manifests.glob("*.json"))
        blobs = list(self.blobs.glob("*/*"))
        full = list(self.full.glob("*.zip"))
        return {
            "schema": "kch.checkpoint-manager-status.v0.1.0",
            "structured_checkpoints": len(manifests),
            "deduplicated_blobs": len(blobs),
            "blob_bytes": sum(path.stat().st_size for path in blobs),
            "full_checkpoints": len(full),
            "full_checkpoint_bytes": sum(path.stat().st_size for path in full),
            "full_warning_required": True,
            "bidirectional_trace_available": True,
            "restore_policy": "NEW_EMPTY_ROOT_BY_DEFAULT",
        }
