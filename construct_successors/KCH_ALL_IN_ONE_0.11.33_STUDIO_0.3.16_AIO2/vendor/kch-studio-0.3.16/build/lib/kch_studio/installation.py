from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .contracts import file_manifest, safe_child, sha256_json


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ConsentDecision(StrEnum):
    YES = "YES"
    NO = "NO"
    NEVER_THIS_SESSION = "NEVER_THIS_SESSION"
    ALWAYS_THIS_SESSION = "ALWAYS_THIS_SESSION"


@dataclass(frozen=True, slots=True)
class InstallPlan:
    plan_id: str
    artifact_kind: str
    source: str
    target_relative: str
    action: str
    isolation: str
    preconditions: tuple[str, ...]
    rollback: tuple[str, ...]
    network_required: bool
    global_install: bool
    executable_content: bool
    schema: str = "kch.install-plan.v0.1.0"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["preconditions"] = list(self.preconditions)
        value["rollback"] = list(self.rollback)
        return value


class ConsentPolicy:
    def __init__(self) -> None:
        self._always = False
        self._never = False

    def adjudicate(self, decision: ConsentDecision) -> bool:
        if self._never:
            return False
        if self._always:
            return True
        if decision == ConsentDecision.NEVER_THIS_SESSION:
            self._never = True
            return False
        if decision == ConsentDecision.ALWAYS_THIS_SESSION:
            self._always = True
            return True
        return decision == ConsentDecision.YES

    def state(self) -> dict[str, bool]:
        return {"always_this_session": self._always, "never_this_session": self._never}


class IsolatedInstaller:
    """Copy/install sealed candidates only inside an explicit governed sandbox root."""

    def __init__(self, sandbox_root: str | Path):
        self.root = Path(sandbox_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.policy = ConsentPolicy()
        self.receipts = self.root / "receipts"
        self.receipts.mkdir(exist_ok=True)

    def plan(self, source: str | Path, *, artifact_kind: str, target_name: str) -> InstallPlan:
        source_path = Path(source).resolve()
        if not source_path.is_dir():
            raise ValueError(f"install source is not a directory: {source_path}")
        target_relative = f"profiles/{target_name}"
        safe_child(self.root, target_relative)
        return InstallPlan(
            plan_id=f"INSTALL-{uuid.uuid4()}",
            artifact_kind=artifact_kind,
            source=str(source_path),
            target_relative=target_relative,
            action="COPY_VERBATIM_INTO_ISOLATED_PROFILE",
            isolation="KCH_DISPOSABLE_PROFILE",
            preconditions=("SEALED_CANDIDATE", "EXPLICIT_CONSENT", "TARGET_WITHIN_SANDBOX"),
            rollback=("VERIFY_TARGET_BOUNDARY", "REMOVE_EXACT_TARGET", "RECORD_ROLLBACK_RECEIPT"),
            network_required=False,
            global_install=False,
            executable_content=True,
        )

    def execute(self, plan: InstallPlan, decision: ConsentDecision) -> dict[str, Any]:
        authorized = self.policy.adjudicate(decision)
        if not authorized:
            return {
                "schema": "kch.install-receipt.v0.1.0",
                "plan_id": plan.plan_id,
                "state": "DECLINED_NO_SIDE_EFFECTS",
                "consent": decision.value,
                "policy": self.policy.state(),
                "target": None,
            }
        if plan.global_install or plan.network_required:
            raise ValueError("isolated installer refuses global or networked plans")
        target = safe_child(self.root, plan.target_relative)
        if target.exists():
            raise ValueError(f"isolated target already exists: {target}")
        source = Path(plan.source).resolve()
        shutil.copytree(source, target)
        manifest = file_manifest(target)
        receipt = {
            "schema": "kch.install-receipt.v0.1.0",
            "plan_id": plan.plan_id,
            "state": "INSTALLED_ISOLATED_DISABLED",
            "consent": decision.value,
            "policy": self.policy.state(),
            "source": str(source),
            "target": str(target),
            "manifest": manifest,
            "manifest_hash": sha256_json(manifest),
            "enabled": False,
            "external_environment_modified": False,
            "installed_at": utc_now(),
        }
        (self.receipts / f"{plan.plan_id}.json").write_text(
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return receipt

    def verify(self, receipt: dict[str, Any]) -> dict[str, Any]:
        if receipt.get("state") != "INSTALLED_ISOLATED_DISABLED":
            return {"passed": False, "reason": "receipt is not an installed state"}
        target = Path(str(receipt["target"])).resolve()
        expected_boundary = self.root.resolve()
        if not target.is_relative_to(expected_boundary) or target == expected_boundary:
            return {"passed": False, "reason": "target escapes isolated boundary"}
        manifest = file_manifest(target) if target.is_dir() else []
        return {
            "passed": manifest == receipt.get("manifest"),
            "target": str(target),
            "manifest_hash": sha256_json(manifest),
            "enabled": False,
        }

    def rollback(self, receipt: dict[str, Any]) -> dict[str, Any]:
        target = Path(str(receipt.get("target", ""))).resolve()
        if target == self.root or not target.is_relative_to(self.root):
            raise ValueError("rollback target escapes isolated sandbox")
        existed = target.exists()
        if existed:
            shutil.rmtree(target)
        rollback = {
            "schema": "kch.rollback-receipt.v0.1.0",
            "plan_id": receipt.get("plan_id"),
            "state": "ROLLED_BACK" if existed else "ALREADY_ABSENT",
            "target": str(target),
            "target_exists_after": target.exists(),
            "external_environment_modified": False,
            "rolled_back_at": utc_now(),
        }
        (self.receipts / f"{receipt.get('plan_id')}.rollback.json").write_text(
            json.dumps(rollback, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return rollback
