from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from .core import BudgetPolicy, TaskProfile, TokenMaster, UsageRecord


TASK_PROFILE_ALIASES = {
    "deterministic_workload": "deterministic_volume",
    "requires_ordered_full_read": "ordered_full_read_required",
    "requires_live_process_monitoring": "live_process_monitoring_required",
    "high_stakes": "high_stakes_claim_adjudication",
}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def load_task_profile(path: Path) -> TaskProfile:
    raw = load_object(path)
    normalized: dict[str, Any] = {}
    for name, value in raw.items():
        target = TASK_PROFILE_ALIASES.get(name, name)
        if target in normalized:
            raise ValueError(f"duplicate task-profile field after alias normalization: {target}")
        normalized[target] = value
    allowed = {item.name for item in fields(TaskProfile)}
    unknown = sorted(set(normalized) - allowed)
    if unknown:
        raise ValueError(f"unknown task-profile fields: {', '.join(unknown)}")
    return TaskProfile(**normalized)


def emit(value: object, output: Path | None) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tokenmaster")
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--policy-id", default="tokenmaster-default")
    parser.add_argument("--weekly-token-budget", type=int)
    parser.add_argument("--weekly-cost-budget", type=float)
    parser.add_argument("--auto-subagents", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    budget = sub.add_parser("budget")
    budget.add_argument("--output", type=Path)
    usage = sub.add_parser("ingest-usage")
    usage.add_argument("record", type=Path)
    usage.add_argument("--output", type=Path)
    plan = sub.add_parser("plan")
    plan.add_argument("task", type=Path)
    plan.add_argument("--output", type=Path)
    plan.add_argument("--brief", action="store_true")
    estimate = sub.add_parser("estimate")
    estimate.add_argument("text")
    estimate.add_argument("--kind", choices=["PROSE", "CODE", "TRANSCRIPT"], default="PROSE")
    estimate.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    policy = BudgetPolicy(
        policy_id=args.policy_id,
        weekly_token_budget=args.weekly_token_budget,
        weekly_cost_budget=args.weekly_cost_budget,
        auto_subagents=args.auto_subagents,
    )
    engine = TokenMaster(args.state_root, policy)
    if args.command == "budget":
        result: object = engine.budget_status()
    elif args.command == "ingest-usage":
        result = engine.ingest_usage(UsageRecord(**load_object(args.record)))
    elif args.command == "plan":
        plan = engine.plan(load_task_profile(args.task))
        result = {"plan": plan, "brief": engine.user_brief(plan)} if args.brief else plan
    else:
        result = engine.estimate_text(args.text, content_kind=args.kind)
    emit(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
