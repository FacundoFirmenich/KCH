from __future__ import annotations

from pathlib import Path
from typing import Any

from .recovery import RecoveryVault


class RiskAdvisor:
    """Advises and records; it never silently censors a user-authorized override."""

    IRREPLACEABLE = {"HARNESS", "CONSTITUTION", "RECOVERY_VAULT", "PERSISTENCE_LEDGER"}

    def __init__(self, root: str | Path):
        self.vault = RecoveryVault(Path(root).resolve() / "recovery")

    def assess(self, proposal: dict[str, Any]) -> dict[str, Any]:
        operation = str(proposal.get("operation", "UNKNOWN")).upper()
        target = str(proposal.get("target", "UNKNOWN"))
        target_class = str(proposal.get("target_class", "")).upper()
        dependents = sorted(set(str(item) for item in proposal.get("dependents", [])))
        warnings: list[dict[str, Any]] = []
        if (
            operation in {"DELETE", "DISABLE", "REPLACE", "TRUNCATE"}
            and target_class in self.IRREPLACEABLE
        ):
            warnings.append(
                {
                    "severity": "CRITICAL",
                    "code": "CORE_RECOVERY_OR_AUTHORITY_AT_RISK",
                    "message": f"{operation} on {target_class} can make KCH authority or recovery inoperable",
                }
            )
        if operation in {"DELETE", "DISABLE", "REPLACE"} and dependents:
            warnings.append(
                {
                    "severity": "HIGH",
                    "code": "DEPENDENTS_WOULD_BE_ORPHANED",
                    "message": f"{len(dependents)} declared dependents may stop working",
                    "dependents": dependents,
                }
            )
        if proposal.get("external_write") and not proposal.get("rollback_declared"):
            warnings.append(
                {
                    "severity": "HIGH",
                    "code": "EXTERNAL_WRITE_WITHOUT_ROLLBACK",
                    "message": "the proposed external write has no declared rollback",
                }
            )
        if proposal.get("lossy_conversion") and not proposal.get("original_retained"):
            warnings.append(
                {
                    "severity": "HIGH",
                    "code": "LOSSY_CONVERSION_WITHOUT_ORIGINAL",
                    "message": "a lossy derivative would be created without retaining the original bytes",
                }
            )
        if proposal.get("history_deletion"):
            warnings.append(
                {
                    "severity": "CRITICAL",
                    "code": "HISTORY_CUSTODY_AT_RISK",
                    "message": "the proposal would remove recovery or persistence history",
                }
            )
        order = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        maximum = max((order[item["severity"]] for item in warnings), default=0)
        return {
            "schema": "kch.risk-advice.v0.1.0",
            "proposal": proposal,
            "warnings": warnings,
            "warning_count": len(warnings),
            "maximum_severity": next(
                (name for name, value in order.items() if value == maximum), "INFO"
            ),
            "blocked": False,
            "user_override_available": True,
            "recovery_snapshot_required": bool(warnings),
            "advisor_is_censor": False,
            "target": target,
        }

    def proceed(self, proposal: dict[str, Any], *, user_authorized: bool) -> dict[str, Any]:
        advice = self.assess(proposal)
        snapshot = (
            self.vault.snapshot(f"before:{proposal.get('operation')}:{proposal.get('target')}")
            if advice["warnings"]
            else None
        )
        alerts = [
            self.vault.record_alert(
                severity=item["severity"],
                code=item["code"],
                message=item["message"],
                target=str(proposal.get("target", "UNKNOWN")),
                proposed_operation=str(proposal.get("operation", "UNKNOWN")),
                overridden=bool(user_authorized),
                recovery_snapshot=None if snapshot is None else snapshot["snapshot_id"],
                evidence={"proposal": proposal, "warning": item},
            )
            for item in advice["warnings"]
        ]
        return {
            **advice,
            "user_authorized": bool(user_authorized),
            "proceed": bool(user_authorized),
            "snapshot": snapshot,
            "recorded_alerts": alerts,
        }
