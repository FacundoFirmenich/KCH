from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constitutional import Actor, ConstitutionalAuthorityError
from .contracts import canonical_json, file_manifest, safe_child, sha256_bytes, sha256_json
from .recovery import RecoveryVault


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def tree_hash(root: Path) -> tuple[list[dict[str, Any]], str]:
    ignored = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".runtime",
        "runtime_live",
        "runtime_live_r2",
    }
    manifest = [
        item
        for item in file_manifest(root)
        if not any(part in ignored for part in Path(item["path"]).parts)
    ]
    return manifest, sha256_json(manifest)


class ConstructMode:
    """Guided KCH self-construction through versioned successors, never blind in-place edits."""

    def __init__(self, root: str | Path, stable_root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.stable_root = Path(stable_root).resolve()
        if not self.stable_root.is_dir():
            raise NotADirectoryError(self.stable_root)
        self.backups = self.root / "stable_backups"
        self.backups.mkdir(exist_ok=True)
        self.candidates = self.root / "candidates"
        self.candidates.mkdir(exist_ok=True)
        self.promoted = self.root / "promoted"
        self.promoted.mkdir(exist_ok=True)
        self.vault = RecoveryVault(self.root / "recovery")
        self.pointer = self.root / "NEXT_START_STABLE.json"
        if not self.pointer.is_file():
            manifest, digest = tree_hash(self.stable_root)
            self.pointer.write_text(
                canonical_json(
                    {
                        "schema": "kch.construct-stable-pointer.v0.1.0",
                        "stable_id": "CURRENT_INPUT_STABLE",
                        "root": str(self.stable_root),
                        "manifest_hash": digest,
                        "created_at": utc_now(),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

    @staticmethod
    def _require_user(actor: Actor) -> None:
        if actor is not Actor.USER:
            raise ConstitutionalAuthorityError(
                "CONSTRUCT mutations require explicit USER authority"
            )

    @staticmethod
    def _excluded(path: Path, base: Path) -> bool:
        parts = path.relative_to(base).parts
        return any(
            part
            in {
                ".git",
                "__pycache__",
                ".pytest_cache",
                ".runtime",
                "runtime_live",
                "runtime_live_r2",
            }
            for part in parts
        )

    def _backup_stable(self) -> dict[str, Any]:
        manifest, digest = tree_hash(self.stable_root)
        target = self.backups / f"KCH_STABLE_{digest}.zip"
        reused = target.is_file()
        if not reused:
            with zipfile.ZipFile(
                target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as archive:
                for item in manifest:
                    path = self.stable_root / Path(item["path"])
                    if self._excluded(path, self.stable_root):
                        continue
                    info = zipfile.ZipInfo(item["path"], (2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, path.read_bytes())
            if zipfile.ZipFile(target).testzip() is not None:
                raise ValueError("stable backup ZIP failed CRC verification")
        return {
            "path": str(target),
            "sha256": sha256_bytes(target.read_bytes()),
            "source_manifest_hash": digest,
            "source_file_count": len(manifest),
            "reused_existing_exact_backup": reused,
        }

    def start(self, objective: str, *, actor: Actor) -> dict[str, Any]:
        self._require_user(actor)
        if not objective.strip():
            raise ValueError("CONSTRUCT objective cannot be empty")
        backup = self._backup_stable()
        session_id = f"CONSTRUCT-{uuid.uuid4()}"
        target = safe_child(self.candidates, session_id)
        shutil.copytree(
            self.stable_root,
            target,
            ignore=shutil.ignore_patterns(
                ".git", "__pycache__", ".pytest_cache", ".runtime", "runtime_live*"
            ),
        )
        manifest, digest = tree_hash(target)
        state = {
            "schema": "kch.construct-session.v0.1.0",
            "session_id": session_id,
            "objective": objective,
            "state": "CANDIDATE_COPIED",
            "stable_root": str(self.stable_root),
            "candidate_root": str(target),
            "stable_backup": backup,
            "initial_candidate_manifest_hash": digest,
            "created_at": utc_now(),
            "user_authority_required": True,
            "runtime_active_bytes_modified": False,
        }
        custody = self.vault.save_json(
            f"sessions/{session_id}.json",
            state,
            kind="KCH_CONSTRUCT_SESSION",
            actor="USER",
            operation="START_WITH_STABLE_BACKUP",
        )
        return {**state, "custody": custody}

    def state(self, session_id: str) -> dict[str, Any]:
        return json.loads(
            str(self.vault.latest(f"sessions/{session_id}.json", decode=True)["content"])
        )

    def write_file(
        self, session_id: str, relative_path: str, content: bytes | str, *, actor: Actor
    ) -> dict[str, Any]:
        self._require_user(actor)
        state = self.state(session_id)
        if state["state"] not in {"CANDIDATE_COPIED", "MODIFIED", "VALIDATION_FAILED"}:
            raise ValueError("construct session is not editable")
        root = Path(state["candidate_root"])
        target = safe_child(root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        before = target.read_bytes() if target.is_file() else None
        if before is not None:
            self.vault.save(
                f"sessions/{session_id}/before/{relative_path}",
                before,
                kind="CONSTRUCT_PREIMAGE",
                actor="KCH_SYSTEM",
                operation="BACKUP_BEFORE_WRITE",
                media_type="application/octet-stream",
            )
        raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        target.write_bytes(raw)
        state["state"] = "MODIFIED"
        state["updated_at"] = utc_now()
        state.setdefault("changes", []).append(
            {
                "path": relative_path,
                "before_sha256": None if before is None else sha256_bytes(before),
                "after_sha256": sha256_bytes(raw),
                "bytes": len(raw),
            }
        )
        custody = self.vault.save_json(
            f"sessions/{session_id}.json",
            state,
            kind="KCH_CONSTRUCT_SESSION",
            actor="USER",
            operation="WRITE_CANDIDATE_FILE",
        )
        return {
            "session_id": session_id,
            "path": str(target),
            "sha256": sha256_bytes(raw),
            "runtime_active_bytes_modified": False,
            "custody": custody,
        }

    def validate(
        self, session_id: str, *, actor: Actor, timeout_seconds: int = 600
    ) -> dict[str, Any]:
        self._require_user(actor)
        state = self.state(session_id)
        root = Path(state["candidate_root"])
        commands = [
            [sys.executable, "-m", "compileall", "-q", str(root)],
        ]
        if (root / "tests").is_dir():
            commands.append(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(root / "tests"),
                    "-q",
                    "--basetemp",
                    str(self.root / "pytest_tmp" / session_id),
                ]
            )
        results = []
        for command in commands:
            completed = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
            )
            results.append(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout_tail": completed.stdout[-4000:],
                    "stderr_tail": completed.stderr[-4000:],
                }
            )
            if completed.returncode != 0:
                break
        manifest, digest = tree_hash(root)
        passed = all(item["returncode"] == 0 for item in results)
        state.update(
            {
                "state": "VALIDATED_CANDIDATE" if passed else "VALIDATION_FAILED",
                "validation": {
                    "passed": passed,
                    "commands": results,
                    "manifest_hash": digest,
                    "file_count": len(manifest),
                },
                "updated_at": utc_now(),
            }
        )
        custody = self.vault.save_json(
            f"sessions/{session_id}.json",
            state,
            kind="KCH_CONSTRUCT_SESSION",
            actor="USER",
            operation="VALIDATE_CANDIDATE",
        )
        return {
            **state["validation"],
            "session_id": session_id,
            "state": state["state"],
            "custody": custody,
        }

    def promote_for_next_start(self, session_id: str, *, actor: Actor) -> dict[str, Any]:
        self._require_user(actor)
        state = self.state(session_id)
        if state["state"] != "VALIDATED_CANDIDATE" or not state["validation"]["passed"]:
            raise ValueError("only a validated candidate can be promoted")
        source = Path(state["candidate_root"])
        manifest, digest = tree_hash(source)
        target = safe_child(self.promoted, f"KCH_SUCCESSOR_{digest}")
        if not target.exists():
            shutil.copytree(source, target)
        previous = json.loads(self.pointer.read_text(encoding="utf-8"))
        pointer = {
            "schema": "kch.construct-stable-pointer.v0.1.0",
            "stable_id": f"SUCCESSOR-{digest[:16]}",
            "root": str(target),
            "manifest_hash": digest,
            "previous": previous,
            "promoted_from_session": session_id,
            "effective": "NEXT_START_ONLY",
            "promoted_at": utc_now(),
        }
        temporary = self.pointer.with_suffix(".tmp")
        temporary.write_text(canonical_json(pointer) + "\n", encoding="utf-8")
        os.replace(temporary, self.pointer)
        state["state"] = "PROMOTED_FOR_NEXT_START"
        state["promotion"] = pointer
        state["updated_at"] = utc_now()
        custody = self.vault.save_json(
            f"sessions/{session_id}.json",
            state,
            kind="KCH_CONSTRUCT_SESSION",
            actor="USER",
            operation="PROMOTE_NEXT_START",
        )
        return {
            "session_id": session_id,
            "state": state["state"],
            "pointer": pointer,
            "last_stable_backup": state["stable_backup"],
            "runtime_active_bytes_modified": False,
            "custody": custody,
        }

    def rollback_pointer(self, *, actor: Actor) -> dict[str, Any]:
        self._require_user(actor)
        current = json.loads(self.pointer.read_text(encoding="utf-8"))
        previous = current.get("previous")
        if not previous:
            raise ValueError("no previous stable pointer is recorded")
        temporary = self.pointer.with_suffix(".tmp")
        temporary.write_text(canonical_json(previous) + "\n", encoding="utf-8")
        os.replace(temporary, self.pointer)
        receipt = {
            "state": "ROLLED_BACK_NEXT_START_POINTER",
            "from": current,
            "to": previous,
            "rolled_back_at": utc_now(),
        }
        self.vault.save_json(
            f"rollbacks/{uuid.uuid4()}.json",
            receipt,
            kind="KCH_CONSTRUCT_ROLLBACK",
            actor="USER",
            operation="ROLLBACK_POINTER",
        )
        return receipt

    def status(self) -> dict[str, Any]:
        return {
            "schema": "kch.construct-mode-status.v0.1.0",
            "stable_pointer": json.loads(self.pointer.read_text(encoding="utf-8")),
            "backup_count": len(list(self.backups.glob("KCH_STABLE_*.zip"))),
            "candidate_count": len([path for path in self.candidates.iterdir() if path.is_dir()]),
            "modes": ["PLAN", "RUN", "CONSTRUCT"],
            "in_place_self_overwrite": False,
        }
