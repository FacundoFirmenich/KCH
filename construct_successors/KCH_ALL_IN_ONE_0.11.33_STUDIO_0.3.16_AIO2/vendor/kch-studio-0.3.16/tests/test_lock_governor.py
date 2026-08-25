from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from kch_studio.advanced_runtime import KCHAdvancedRuntime
from kch_studio.constitutional import Actor, ConstitutionalAuthorityError
from kch_studio.contracts import sha256_bytes, sha256_json
from kch_studio.lock_governor import LockGovernor, resource_for_path


def binding(content: bytes) -> dict[str, str | None]:
    digest = sha256_bytes(content)
    return {
        "current_sha256": None,
        "proposed_sha256": digest,
        "payload_sha256": sha256_json({"content_sha256": digest}),
    }


def lock_file(governor: LockGovernor, path: Path) -> dict[str, object]:
    return governor.create_lock(
        resource_pattern=resource_for_path(path),
        match_mode="EXACT",
        operations=["CREATE", "MODIFY", "DELETE"],
        reason="Canonical fixture must not change without exact user authority.",
        actor=Actor.USER,
    )


def propose(
    governor: LockGovernor,
    path: Path,
    proposal_binding: dict[str, str | None],
) -> dict[str, object]:
    return governor.propose(
        resource=resource_for_path(path),
        operation="CREATE",
        current_sha256=proposal_binding["current_sha256"],
        proposed_sha256=proposal_binding["proposed_sha256"],
        payload_sha256=str(proposal_binding["payload_sha256"]),
        rationale="Create the explicitly requested successor fixture.",
        impact="Only the exact new fixture path changes.",
        dependencies=["tests"],
        recovery_plan="Delete the new fixture and verify the prior manifest.",
    )


def test_optional_default_does_not_block_until_user_enables(tmp_path: Path) -> None:
    governor = LockGovernor(tmp_path / "runtime")
    target = tmp_path / "candidate" / "frozen.txt"
    lock_file(governor, target)
    payload = binding(b"new\n")

    result = governor.preflight(
        resource=resource_for_path(target), operation="CREATE", **payload
    )

    assert result["gate"] == "ALLOW_GOVERNOR_DISABLED"
    assert governor.status()["default_enabled"] is False
    assert governor.status()["session_wide_unlock_supported"] is False


def test_enabled_exact_lock_blocks_without_authorization(tmp_path: Path) -> None:
    governor = LockGovernor(tmp_path / "runtime")
    target = tmp_path / "candidate" / "frozen.txt"
    lock_file(governor, target)
    governor.set_enabled(True, actor=Actor.USER)

    result = governor.preflight(
        resource=resource_for_path(target), operation="CREATE", **binding(b"new\n")
    )

    assert result["gate"] == "BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED"
    assert result["authorized"] is False
    assert result["session_wide_consent_accepted"] is False
    assert result["matched_locks"][0]["reason"].startswith("Canonical fixture")


def test_model_and_untrusted_channel_cannot_authorize(tmp_path: Path) -> None:
    governor = LockGovernor(tmp_path / "runtime")
    target = tmp_path / "candidate" / "frozen.txt"
    lock_file(governor, target)
    governor.set_enabled(True, actor=Actor.USER)
    change = propose(governor, target, binding(b"new\n"))

    with pytest.raises(ConstitutionalAuthorityError):
        governor.trusted_authorize(
            str(change["proposal_id"]),
            actor=Actor.MODEL,
            trusted_channel="KCH_LOCAL_UI",
        )
    with pytest.raises(ConstitutionalAuthorityError):
        governor.trusted_authorize(
            str(change["proposal_id"]),
            actor=Actor.USER,
            trusted_channel="CALLER_DECLARED_USER",
        )


def test_exact_authorization_is_bound_and_consumed_once(tmp_path: Path) -> None:
    governor = LockGovernor(tmp_path / "runtime")
    target = tmp_path / "candidate" / "frozen.txt"
    lock_file(governor, target)
    governor.set_enabled(True, actor=Actor.USER)
    payload = binding(b"new\n")
    change = propose(governor, target, payload)
    authorization = governor.trusted_authorize(
        str(change["proposal_id"]),
        actor=Actor.USER,
        trusted_channel="KCH_LOCAL_UI",
    )

    allowed = governor.preflight(
        resource=resource_for_path(target),
        operation="CREATE",
        authorization_id=str(authorization["authorization_id"]),
        **payload,
    )

    assert allowed["gate"] == "ALLOW_EXACT_ONE_SHOT_AUTHORIZATION_CONSUMED"
    assert governor.authorization_status(str(change["proposal_id"]))[
        "authorization"
    ]["consumed"] is True
    with pytest.raises(PermissionError, match="already consumed"):
        governor.preflight(
            resource=resource_for_path(target),
            operation="CREATE",
            authorization_id=str(authorization["authorization_id"]),
            **payload,
        )


def test_concurrent_consumption_has_exactly_one_winner(tmp_path: Path) -> None:
    governor = LockGovernor(tmp_path / "runtime")
    target = tmp_path / "candidate" / "race.txt"
    lock_file(governor, target)
    governor.set_enabled(True, actor=Actor.USER)
    payload = binding(b"one winner\n")
    change = propose(governor, target, payload)
    authorization = governor.trusted_authorize(
        str(change["proposal_id"]),
        actor=Actor.USER,
        trusted_channel="KCH_LOCAL_UI",
    )

    def attempt() -> str:
        try:
            result = governor.preflight(
                resource=resource_for_path(target),
                operation="CREATE",
                authorization_id=str(authorization["authorization_id"]),
                **payload,
            )
            return str(result["gate"])
        except PermissionError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _index: attempt(), range(16)))

    assert outcomes.count("ALLOW_EXACT_ONE_SHOT_AUTHORIZATION_CONSUMED") == 1
    assert outcomes.count("lock authorization is already consumed") == 15
    assert governor.verify()["gate"] == "PASS"


def test_changed_payload_cannot_use_existing_authorization(tmp_path: Path) -> None:
    governor = LockGovernor(tmp_path / "runtime")
    target = tmp_path / "candidate" / "frozen.txt"
    lock_file(governor, target)
    governor.set_enabled(True, actor=Actor.USER)
    original = binding(b"authorized\n")
    change = propose(governor, target, original)
    authorization = governor.trusted_authorize(
        str(change["proposal_id"]),
        actor=Actor.USER,
        trusted_channel="KCH_LOCAL_UI",
    )

    with pytest.raises(PermissionError, match="differs from the exact"):
        governor.preflight(
            resource=resource_for_path(target),
            operation="CREATE",
            authorization_id=str(authorization["authorization_id"]),
            **binding(b"silently altered\n"),
        )
    status = governor.authorization_status(str(change["proposal_id"]))
    assert status["authorization"]["consumed"] is False


def test_prefix_and_glob_locks_match_nested_resources(tmp_path: Path) -> None:
    governor = LockGovernor(tmp_path / "runtime")
    base = tmp_path / "candidate"
    governor.create_lock(
        resource_pattern=resource_for_path(base),
        match_mode="PREFIX",
        operations=["MODIFY"],
        reason="Freeze candidate subtree.",
        actor=Actor.USER,
    )
    governor.create_lock(
        resource_pattern="tool://internal/construct_*",
        match_mode="GLOB",
        operations=["EXECUTE"],
        reason="Guard every Construct mutation tool.",
        actor=Actor.USER,
        capture_baseline=False,
    )
    governor.set_enabled(True, actor=Actor.USER)

    assert governor.matching_locks(resource_for_path(base / "a" / "b.py"), "MODIFY")
    assert governor.matching_locks("tool://internal/construct_file_write", "EXECUTE")
    assert not governor.matching_locks("tool://internal/full_read_file", "EXECUTE")


def test_exact_file_drift_is_detected_but_not_overclaimed(tmp_path: Path) -> None:
    governor = LockGovernor(tmp_path / "runtime")
    target = tmp_path / "frozen.txt"
    target.write_text("stable\n", encoding="utf-8", newline="\n")
    lock_file(governor, target)
    governor.set_enabled(True, actor=Actor.USER)
    assert governor.verify_drift()["gate"] == "PASS_NO_DRIFT"

    target.write_text("external drift\n", encoding="utf-8", newline="\n")
    drift = governor.verify_drift()

    assert drift["gate"] == "FAIL_DRIFT_DETECTED"
    assert drift["external_change_prevention_claimed"] is False
    assert drift["external_change_detection_supported"] is True


def test_hash_chain_tampering_is_detected(tmp_path: Path) -> None:
    governor = LockGovernor(tmp_path / "runtime")
    governor.set_enabled(True, actor=Actor.USER)
    assert governor.verify()["gate"] == "PASS"

    with sqlite3.connect(governor.path) as connection:
        connection.execute("UPDATE events SET event_hash=? WHERE seq=1", ("0" * 64,))
        connection.commit()

    assert governor.verify()["gate"] == "FAIL"


def test_runtime_blocks_mutating_tool_until_trusted_ui_authorizes(tmp_path: Path) -> None:
    stable = tmp_path / "stable"
    stable.mkdir()
    (stable / "README.md").write_text("stable\n", encoding="utf-8", newline="\n")
    runtime = KCHAdvancedRuntime(tmp_path / "runtime", stable_root=stable)
    arguments = {"platform": "TEST", "title": "exact locked call"}
    try:
        runtime.lock_user_create(
            {
                "resource_pattern": "tool://internal/persistence_chat_create",
                "match_mode": "EXACT",
                "operations": ["EXECUTE"],
                "reason": "Chat creation is frozen during this development gate.",
                "capture_baseline": False,
            }
        )
        runtime.lock_user_enable(True)

        blocked = runtime.handlers["persistence_chat_create"](arguments)
        assert blocked["state"] == "BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED"
        assert blocked["side_effect_executed"] is False
        assert "lock_user_authorize" not in runtime.handlers

        proposal = runtime.handlers["lock_tool_call_propose"](
            {
                "tool_name": "persistence_chat_create",
                "arguments": arguments,
                "rationale": "Create one bounded test chat.",
                "impact": "Adds one local persistence record only.",
                "dependencies": ["persistence"],
                "recovery_plan": "Discard the disposable runtime.",
            }
        )
        proposal_id = proposal["proposal"]["proposal_id"]
        runtime.lock_user_authorize(proposal_id)
        authorization_id = runtime.handlers["lock_authorization_status"](
            {"proposal_id": proposal_id}
        )["authorization"]["authorization_id"]

        executed = runtime.handlers["lock_authorized_execute"](
            {
                "authorization_id": authorization_id,
                "tool_name": "persistence_chat_create",
                "arguments": arguments,
            }
        )
        assert executed["state"] == "EXECUTED_EXACT_ONE_SHOT_AUTHORIZATION_CONSUMED"
        assert executed["result"]["chat_id"].startswith("CHAT-")
        with pytest.raises(PermissionError, match="already consumed"):
            runtime.handlers["lock_authorized_execute"](
                {
                    "authorization_id": authorization_id,
                    "tool_name": "persistence_chat_create",
                    "arguments": arguments,
                }
            )
        assert runtime.locks.verify()["gate"] == "PASS"
    finally:
        runtime.close()


def test_construct_file_lock_blocks_bytes_then_allows_exact_once(tmp_path: Path) -> None:
    stable = tmp_path / "stable"
    stable.mkdir()
    (stable / "README.md").write_text("stable\n", encoding="utf-8", newline="\n")
    runtime = KCHAdvancedRuntime(tmp_path / "runtime", stable_root=stable)
    try:
        session = runtime.construct.start("Test exact file lock", actor=Actor.USER)
        target = Path(session["candidate_root"]) / "new" / "locked.txt"
        runtime.lock_user_create(
            {
                "resource_pattern": resource_for_path(target),
                "match_mode": "EXACT",
                "operations": ["CREATE", "MODIFY", "DELETE"],
                "reason": "This candidate file requires exact user authorization.",
            }
        )
        runtime.lock_user_enable(True)

        blocked = runtime.construct.write_file(
            session["session_id"],
            "new/locked.txt",
            "authorized bytes\n",
            actor=Actor.USER,
        )
        assert blocked["state"] == "BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED"
        assert blocked["candidate_bytes_modified"] is False
        assert not target.exists()

        proposed = runtime.construct.propose_write(
            session["session_id"],
            "new/locked.txt",
            "authorized bytes\n",
            rationale="Add the exact test fixture required by the R21 gate.",
            impact="Creates one file in a disposable Construct successor.",
            dependencies=["R21 lock regression"],
            recovery_plan="Restore the untouched stable backup.",
            actor=Actor.MODEL,
        )
        authorization = runtime.lock_user_authorize(
            proposed["proposal"]["proposal_id"]
        )
        written = runtime.construct.write_file(
            session["session_id"],
            "new/locked.txt",
            "authorized bytes\n",
            actor=Actor.USER,
            lock_authorization_id=authorization["authorization_id"],
        )

        assert written["lock_preflight"]["gate"] == (
            "ALLOW_EXACT_ONE_SHOT_AUTHORIZATION_CONSUMED"
        )
        assert target.read_bytes() == b"authorized bytes\n"
        with pytest.raises(PermissionError, match="already consumed"):
            runtime.construct.write_file(
                session["session_id"],
                "new/locked.txt",
                "authorized bytes\n",
                actor=Actor.USER,
                lock_authorization_id=authorization["authorization_id"],
            )
    finally:
        runtime.close()
