from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .constitutional import Actor, ConstitutionalAuthorityError
from .recovery import RecoveryVault


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


DEFAULT_RULES = [
    {
        "rule_id": "KCH-DEFAULT-SESSION-CONSTITUTION",
        "priority": 1000,
        "enabled": True,
        "condition": {"path": "event.type", "operator": "EQ", "value": "session.start"},
        "then": {"mode": "DIRECT", "tool": "constitution_effective", "arguments": {}},
        "else": None,
        "purpose": "Load the effective user constitution before ordinary orchestration.",
    },
    {
        "rule_id": "KCH-DEFAULT-EDIT-CHECKPOINT",
        "priority": 900,
        "enabled": True,
        "condition": {
            "path": "event.type",
            "operator": "IN",
            "value": ["box.edited", "artifact.edited", "chat.turn.received"],
        },
        "then": {
            "mode": "DIRECT",
            "tool": "recovery_checkpoint",
            "arguments": {"label": {"$path": "event.type"}, "payload": {"$path": "event"}},
        },
        "else": None,
        "purpose": "Preserve every KCH-observed material edit without asking again.",
    },
    {
        "rule_id": "KCH-DEFAULT-RISK-ADVICE",
        "priority": 800,
        "enabled": True,
        "condition": {"path": "event.type", "operator": "EQ", "value": "change.proposed"},
        "then": {
            "mode": "DIRECT",
            "tool": "risk_assess",
            "arguments": {"proposal": {"$path": "event.proposal"}},
        },
        "else": None,
        "purpose": "Warn and preserve recovery evidence before risky changes; do not censor the user.",
    },
    {
        "rule_id": "KCH-DEFAULT-USER-PROGRAMMED-CAPABILITY",
        "priority": 700,
        "enabled": True,
        "condition": {
            "all": [
                {"path": "event.type", "operator": "EQ", "value": "capability.requested"},
                {"path": "event.authority", "operator": "EQ", "value": "USER_PROGRAM"},
                {"path": "event.capability", "operator": "EXISTS", "value": True},
            ]
        },
        "then": {
            "mode": "DIRECT",
            "tool": {"$path": "event.capability"},
            "arguments": {"$path": "event.arguments"},
        },
        "else": None,
        "purpose": "Launch any registered capability in the background when the user program emits an authorized request.",
    },
]


class ProgrammedPolicy:
    SCHEMA = "kch.programmed-proactive-policy.v0.1.0"

    def __init__(self, root: str | Path, policy_id: str = "default"):
        self.root = Path(root).resolve()
        self.vault = RecoveryVault(self.root / "recovery")
        self.policy_id = policy_id
        self.key = f"programmed-policy/{policy_id}.json"
        try:
            self._load()
        except KeyError:
            self._initialize()

    def _initialize(self) -> None:
        value = {
            "schema": self.SCHEMA,
            "policy_id": self.policy_id,
            "enabled": True,
            "precedence": "ABOVE_PROACTIVE_CONSULTATION_GATE",
            "announce_on_session_start": True,
            "default_if_no_match": "CONSULT_FOUR_WAY_GATE",
            "rules": deepcopy(DEFAULT_RULES),
            "model_can_mutate": False,
            "created_at": utc_now(),
            "revision": 1,
        }
        self.vault.save_json(
            self.key,
            value,
            kind="PROGRAMMED_PROACTIVE_POLICY",
            actor=Actor.KCH_SYSTEM.value,
            operation="INITIALIZE_DEFAULT_POLICY",
        )

    def _load(self) -> dict[str, Any]:
        state = json.loads(str(self.vault.latest(self.key, decode=True)["content"]))
        self._validate(state)
        return state

    @staticmethod
    def _validate_condition(condition: dict[str, Any]) -> None:
        if "all" in condition:
            if not isinstance(condition["all"], list) or not condition["all"]:
                raise ValueError("all condition requires a non-empty list")
            for item in condition["all"]:
                ProgrammedPolicy._validate_condition(item)
            return
        if "any" in condition:
            if not isinstance(condition["any"], list) or not condition["any"]:
                raise ValueError("any condition requires a non-empty list")
            for item in condition["any"]:
                ProgrammedPolicy._validate_condition(item)
            return
        if "not" in condition:
            ProgrammedPolicy._validate_condition(condition["not"])
            return
        if not str(condition.get("path", "")).startswith("event."):
            raise ValueError("condition paths are confined to the declared event")
        if condition.get("operator") not in {
            "EQ",
            "NE",
            "IN",
            "CONTAINS",
            "EXISTS",
            "GT",
            "GE",
            "LT",
            "LE",
        }:
            raise ValueError("unsupported declarative condition operator")

    def _validate(self, state: dict[str, Any]) -> None:
        if state.get("schema") != self.SCHEMA or state.get("model_can_mutate") is not False:
            raise ValueError("invalid programmed policy authority contract")
        ids: set[str] = set()
        for rule in state.get("rules", []):
            if rule["rule_id"] in ids:
                raise ValueError("duplicate programmed rule id")
            ids.add(rule["rule_id"])
            self._validate_condition(rule["condition"])
            for branch in (rule.get("then"), rule.get("else")):
                if branch is not None and branch.get("mode") not in {
                    "DIRECT",
                    "CONSULT",
                    "NO_ACTION",
                }:
                    raise ValueError("branch mode must be DIRECT, CONSULT, or NO_ACTION")

    def state(self) -> dict[str, Any]:
        return deepcopy(self._load())

    def replace(self, state: dict[str, Any], *, actor: Actor) -> dict[str, Any]:
        if actor is not Actor.USER:
            raise ConstitutionalAuthorityError(
                "only USER may alter the programmed proactive policy"
            )
        value = deepcopy(state)
        value["revision"] = int(value.get("revision", 0)) + 1
        value["updated_at"] = utc_now()
        self._validate(value)
        receipt = self.vault.save_json(
            self.key,
            value,
            kind="PROGRAMMED_PROACTIVE_POLICY",
            actor=actor.value,
            operation="REPLACE_USER_PROGRAM",
        )
        return {"policy": value, "custody": receipt}

    def add_rule(self, rule: dict[str, Any], *, actor: Actor) -> dict[str, Any]:
        state = self._load()
        state["rules"].append(deepcopy(rule))
        return self.replace(state, actor=actor)

    def set_preferences(
        self,
        *,
        enabled: bool | None = None,
        announce_on_session_start: bool | None = None,
        actor: Actor,
    ) -> dict[str, Any]:
        state = self._load()
        if enabled is not None:
            state["enabled"] = bool(enabled)
        if announce_on_session_start is not None:
            state["announce_on_session_start"] = bool(announce_on_session_start)
        return self.replace(state, actor=actor)

    @staticmethod
    def _get_path(value: dict[str, Any], path: str) -> tuple[bool, Any]:
        cursor: Any = value
        for part in path.split("."):
            if not isinstance(cursor, dict) or part not in cursor:
                return False, None
            cursor = cursor[part]
        return True, cursor

    @classmethod
    def _matches(cls, condition: dict[str, Any], event: dict[str, Any]) -> bool:
        if "all" in condition:
            return all(cls._matches(item, event) for item in condition["all"])
        if "any" in condition:
            return any(cls._matches(item, event) for item in condition["any"])
        if "not" in condition:
            return not cls._matches(condition["not"], event)
        exists, observed = cls._get_path({"event": event}, str(condition["path"]))
        operator = condition["operator"]
        expected = condition.get("value")
        if operator == "EXISTS":
            return exists is bool(expected)
        if not exists:
            return False
        if operator == "EQ":
            return observed == expected
        if operator == "NE":
            return observed != expected
        if operator == "IN":
            return observed in expected
        if operator == "CONTAINS":
            return expected in observed
        if operator == "GT":
            return observed > expected
        if operator == "GE":
            return observed >= expected
        if operator == "LT":
            return observed < expected
        if operator == "LE":
            return observed <= expected
        return False

    @classmethod
    def _resolve(cls, value: Any, event: dict[str, Any]) -> Any:
        if isinstance(value, dict) and set(value) == {"$path"}:
            exists, observed = cls._get_path({"event": event}, str(value["$path"]))
            if not exists:
                raise ValueError(f"event path is unavailable: {value['$path']}")
            return observed
        if isinstance(value, dict):
            return {key: cls._resolve(item, event) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._resolve(item, event) for item in value]
        return value

    def evaluate(self, event: dict[str, Any]) -> dict[str, Any]:
        matches = self.evaluate_all(event)
        if matches:
            return matches[0]
        state = self._load()
        return {
            "decision": state["default_if_no_match"],
            "matched_rule": None,
            "policy_revision": state["revision"],
            "consultation_bypassed_by_user_program": False,
        }

    def evaluate_all(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        state = self._load()
        if not state["enabled"]:
            return []
        adjudications: list[dict[str, Any]] = []
        for rule in sorted(
            state["rules"], key=lambda item: (-int(item["priority"]), item["rule_id"])
        ):
            if not rule["enabled"]:
                continue
            matched = self._matches(rule["condition"], event)
            branch = rule["then"] if matched else rule.get("else")
            if branch is None:
                continue
            adjudications.append(
                {
                    "decision": branch["mode"],
                    "matched_rule": rule["rule_id"],
                    "tool": self._resolve(branch.get("tool"), event),
                    "arguments": self._resolve(branch.get("arguments", {}), event),
                    "policy_revision": state["revision"],
                    "consultation_bypassed_by_user_program": branch["mode"] == "DIRECT",
                }
            )
        return adjudications

    def session_announcement(self) -> dict[str, Any]:
        state = self._load()
        direct = [
            rule["rule_id"]
            for rule in state["rules"]
            if rule["enabled"] and rule["then"]["mode"] == "DIRECT"
        ]
        return {
            "schema": "kch.programmed-policy-announcement.v0.1.0",
            "policy_id": self.policy_id,
            "policy_revision": state["revision"],
            "enabled": state["enabled"],
            "precedence": state["precedence"],
            "direct_rule_count": len(direct),
            "direct_rules": direct,
            "message": "KCH programmed proactive policy is active; matching DIRECT rules execute without consultation.",
        }


class ProgrammedDispatcher:
    def __init__(
        self, policy: ProgrammedPolicy, handlers: dict[str, Callable[[dict[str, Any]], Any]]
    ):
        self.policy = policy
        self.handlers = handlers

    def dispatch(self, event: dict[str, Any]) -> dict[str, Any]:
        adjudication = self.policy.evaluate(event)
        if adjudication["decision"] != "DIRECT":
            return {"state": "NOT_EXECUTED", "adjudication": adjudication}
        tool = str(adjudication.get("tool", ""))
        if tool not in self.handlers:
            return {
                "state": "DIRECT_RULE_UNRESOLVED_TOOL",
                "adjudication": adjudication,
                "available_tools": sorted(self.handlers),
            }
        result = self.handlers[tool](dict(adjudication.get("arguments", {})))
        return {
            "state": "EXECUTED_BY_USER_PROGRAM",
            "adjudication": adjudication,
            "result": result,
        }

    def dispatch_all(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for adjudication in self.policy.evaluate_all(event):
            if adjudication["decision"] != "DIRECT":
                results.append({"state": "NOT_EXECUTED", "adjudication": adjudication})
                continue
            tool = str(adjudication.get("tool", ""))
            if tool not in self.handlers:
                results.append(
                    {
                        "state": "DIRECT_RULE_UNRESOLVED_TOOL",
                        "adjudication": adjudication,
                        "available_tools": sorted(self.handlers),
                    }
                )
                continue
            try:
                value = self.handlers[tool](dict(adjudication.get("arguments", {})))
                results.append(
                    {
                        "state": "EXECUTED_BY_USER_PROGRAM",
                        "adjudication": adjudication,
                        "result": value,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "state": "EXECUTION_FAILED_PRESERVED",
                        "adjudication": adjudication,
                        "error": str(exc),
                    }
                )
        return results
