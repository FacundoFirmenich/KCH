from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from kch_studio.advanced_runtime import KCHAdvancedRuntime


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--stable-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    runtime = KCHAdvancedRuntime(
        Path(args.runtime_root).resolve(), stable_root=Path(args.stable_root).resolve()
    )
    exact_arguments = {
        "label": "R21 installed exact authorization fixture",
        "orientation": "VERTICAL",
        "rank": 901,
        "consent": "ALWAYS_THIS_SESSION",
    }
    altered_arguments = {**exact_arguments, "rank": 902}
    try:
        lock = runtime.lock_user_create(
            {
                "resource_pattern": "tool://internal/constitution_plane_add",
                "match_mode": "EXACT",
                "operations": ["EXECUTE"],
                "reason": "Installed R21 must require exact local user authority.",
                "capture_baseline": False,
            }
        )
        runtime.lock_user_enable(True)
        blocked = runtime.handlers["constitution_plane_add"](exact_arguments)
        proposal = runtime.handlers["lock_tool_call_propose"](
            {
                "tool_name": "constitution_plane_add",
                "arguments": exact_arguments,
                "rationale": "Exercise one disposable installed mutation.",
                "impact": "Adds one plane only inside the disposable gate runtime.",
                "dependencies": ["installed R21", "constitutional lock governor"],
                "recovery_plan": "Discard the isolated installed-gate runtime.",
            }
        )
        authorization = runtime.lock_user_authorize(
            proposal["proposal"]["proposal_id"]
        )
        altered_rejected = None
        try:
            runtime.handlers["lock_authorized_execute"](
                {
                    "authorization_id": authorization["authorization_id"],
                    "tool_name": "constitution_plane_add",
                    "arguments": altered_arguments,
                }
            )
        except PermissionError as error:
            altered_rejected = str(error)
        after_altered = runtime.handlers["lock_authorization_status"](
            {"proposal_id": proposal["proposal"]["proposal_id"]}
        )
        executed = runtime.handlers["lock_authorized_execute"](
            {
                "authorization_id": authorization["authorization_id"],
                "tool_name": "constitution_plane_add",
                "arguments": exact_arguments,
            }
        )
        reuse_rejected = None
        try:
            runtime.handlers["lock_authorized_execute"](
                {
                    "authorization_id": authorization["authorization_id"],
                    "tool_name": "constitution_plane_add",
                    "arguments": exact_arguments,
                }
            )
        except PermissionError as error:
            reuse_rejected = str(error)
        final_status = runtime.handlers["lock_authorization_status"](
            {"proposal_id": proposal["proposal"]["proposal_id"]}
        )
        integrity = runtime.locks.verify()
        checks = {
            "always_this_session_does_not_bypass_lock": blocked["state"]
            == "BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED"
            and blocked["side_effect_executed"] is False,
            "authority_methods_absent_from_mcp_handlers": {
                "lock_user_enable",
                "lock_user_create",
                "lock_user_deactivate",
                "lock_user_authorize",
            }.isdisjoint(runtime.handlers),
            "altered_arguments_rejected": altered_rejected
            == "mutation differs from the exact authorized proposal",
            "altered_attempt_did_not_consume": after_altered["authorization"][
                "consumed"
            ]
            is False,
            "exact_call_executed": executed["state"]
            == "EXECUTED_EXACT_ONE_SHOT_AUTHORIZATION_CONSUMED"
            and executed["result"]["state"] == "EXECUTED_UNDER_SCOPED_USER_CONSENT",
            "authorization_consumed_once": final_status["authorization"]["consumed"]
            is True,
            "reuse_rejected": reuse_rejected
            == "lock authorization is already consumed",
            "hash_chain_pass": integrity["gate"] == "PASS",
            "phl_not_executed": runtime.phl.status()["training_executed"] is False,
        }
        payload: dict[str, Any] = {
            "schema": "kch.r21-installed-constitutional-lock-gate.v0.1.0",
            "gate": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "lock": lock,
            "blocked": blocked,
            "proposal": proposal,
            "authorization": authorization,
            "altered_rejected": altered_rejected,
            "executed": executed,
            "reuse_rejected": reuse_rejected,
            "final_status": final_status,
            "integrity": integrity,
            "phl_authorized": True,
            "phl_training_executed": False,
            "phl_real_executed": False,
            "claim_ceiling": "LOCAL_FRESH_INSTALL_LOCK_INTERPOSITION_AND_EXACT_AUTHORITY_ONLY",
        }
        sealed = {**payload, "sha256": canonical_sha256(payload)}
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(sealed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            json.dumps(
                {
                    "gate": sealed["gate"],
                    "checks": checks,
                    "output": str(output),
                    "sha256": sealed["sha256"],
                },
                ensure_ascii=False,
            )
        )
        return 0 if sealed["gate"] == "PASS" else 1
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
