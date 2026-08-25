from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal


class TokenMasterError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _ratio(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
        raise ValueError(f"{field_name} must lie in [0,1]")
    return float(value)


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    policy_id: str
    weekly_token_budget: int | None = None
    weekly_cost_budget: float | None = None
    reserve_ratio: float = 0.15
    auto_subagents: bool = False
    max_subagents: int = 3
    supports_subagents: bool = True
    supports_sco_separate_chats: bool = True
    response_chat_token_ceiling: dict[str, int | None] = field(
        default_factory=lambda: {"CONCISO": 450, "EXPLICATIVO": 1100, "EXTENSO": None}
    )
    model_profiles: dict[str, str] = field(
        default_factory=lambda: {
            "ECONOMY": "HOST_ECONOMY_PROFILE",
            "BALANCED": "HOST_BALANCED_PROFILE",
            "FRONTIER": "HOST_FRONTIER_PROFILE",
        }
    )

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or self.max_subagents < 0 or self.max_subagents > 16:
            raise ValueError("invalid TokenMaster policy")
        if self.weekly_token_budget is not None and self.weekly_token_budget <= 0:
            raise ValueError("weekly token budget must be positive")
        if self.weekly_cost_budget is not None and self.weekly_cost_budget <= 0:
            raise ValueError("weekly cost budget must be positive")
        _ratio(self.reserve_ratio, "reserve_ratio")
        if set(self.response_chat_token_ceiling) != {"CONCISO", "EXPLICATIVO", "EXTENSO"}:
            raise ValueError("response modes must be CONCISO, EXPLICATIVO and EXTENSO")
        if set(self.model_profiles) != {"ECONOMY", "BALANCED", "FRONTIER"}:
            raise ValueError("model profiles must map ECONOMY, BALANCED and FRONTIER")


@dataclass(frozen=True, slots=True)
class UsageRecord:
    provider: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost: float | None
    occurred_at: str
    source: str
    record_id: str = ""

    def __post_init__(self) -> None:
        counts = (self.input_tokens, self.cached_input_tokens, self.output_tokens, self.reasoning_tokens)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
            raise ValueError("usage token counts must be non-negative integers")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input cannot exceed input tokens")
        if self.cost is not None and self.cost < 0:
            raise ValueError("cost cannot be negative")
        datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.reasoning_tokens


@dataclass(frozen=True, slots=True)
class TaskProfile:
    task_id: str
    title: str
    ambiguity: float
    risk: float
    reversibility: float
    coupling: float
    semantic_judgment: float
    deterministic_volume: float
    parallel_fraction: float
    independent_units: int
    estimated_input_tokens: int | None = None
    estimated_output_tokens: int | None = None
    modality: Literal["TEXT", "AUDIO_TRANSCRIPT"] = "TEXT"
    transcript_confidence: float | None = None
    response_mode: Literal["CONCISO", "EXPLICATIVO", "EXTENSO"] = "EXPLICATIVO"
    requested_topology: Literal["AUTO", "SINGLE_CHAT", "SCO_SEPARATE_CHATS", "SUBAGENTS"] = "AUTO"
    ordered_full_read_required: bool = False
    live_process_monitoring_required: bool = False
    high_stakes_claim_adjudication: bool = False

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.title.strip() or self.independent_units < 1:
            raise ValueError("task identity and at least one unit are required")
        for name in (
            "ambiguity", "risk", "reversibility", "coupling", "semantic_judgment",
            "deterministic_volume", "parallel_fraction",
        ):
            _ratio(getattr(self, name), name)
        for name in ("estimated_input_tokens", "estimated_output_tokens"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or null")
        if self.modality == "AUDIO_TRANSCRIPT":
            if self.transcript_confidence is None:
                raise ValueError("audio transcripts require a confidence value")
            _ratio(self.transcript_confidence, "transcript_confidence")


class TokenMaster:
    SCHEMA = "kch.tokenmaster.v0.1.0"

    def __init__(self, state_root: str | Path, policy: BudgetPolicy) -> None:
        self.state_root = Path(state_root).resolve(strict=False)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.policy = policy
        self.database = self.state_root / "tokenmaster.sqlite3"
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
                CREATE TABLE IF NOT EXISTS usage_records(
                    record_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, provider TEXT NOT NULL,
                    model TEXT NOT NULL, input_tokens INTEGER NOT NULL, cached_input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL, reasoning_tokens INTEGER NOT NULL, cost REAL,
                    source TEXT NOT NULL, payload_sha256 TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plans(
                    plan_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    decision_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL
                );
                """
            )

    def ingest_usage(self, record: UsageRecord) -> dict[str, Any]:
        core = asdict(record)
        record_id = record.record_id or f"USE-{sha256_json(core)[:20]}"
        payload_hash = sha256_json(core)
        with self._connect() as db:
            existing = db.execute("SELECT payload_sha256 FROM usage_records WHERE record_id=?", (record_id,)).fetchone()
            if existing and existing["payload_sha256"] != payload_hash:
                raise TokenMasterError("usage record_id collision with different payload")
            db.execute(
                "INSERT OR IGNORE INTO usage_records VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    record_id, record.occurred_at, record.provider, record.model,
                    record.input_tokens, record.cached_input_tokens, record.output_tokens,
                    record.reasoning_tokens, record.cost, record.source, payload_hash,
                ),
            )
        return {
            "schema": "kch.tokenmaster.usage-receipt.v0.1.0",
            "record_id": record_id,
            "payload_sha256": payload_hash,
            "actual_provider_usage": True,
            "estimated": False,
        }

    @staticmethod
    def _week_bounds(moment: datetime) -> tuple[datetime, datetime]:
        start = moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        start = start.fromordinal(start.toordinal() - start.weekday()).replace(tzinfo=UTC)
        return start, start + timedelta(days=7)

    def budget_status(self, *, at: datetime | None = None) -> dict[str, Any]:
        moment = at or datetime.now(UTC)
        start, end = self._week_bounds(moment)
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM usage_records WHERE occurred_at>=? AND occurred_at<?",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        tokens = sum(row["input_tokens"] + row["output_tokens"] + row["reasoning_tokens"] for row in rows)
        known_costs = [row["cost"] for row in rows if row["cost"] is not None]
        cost = float(sum(known_costs)) if known_costs else 0.0
        token_budget = self.policy.weekly_token_budget
        cost_budget = self.policy.weekly_cost_budget
        return {
            "schema": "kch.tokenmaster.budget-status.v0.1.0",
            "window_start": start.isoformat().replace("+00:00", "Z"),
            "window_end": end.isoformat().replace("+00:00", "Z"),
            "actual_records": len(rows),
            "tokens_used": tokens,
            "tokens_budget": token_budget,
            "tokens_remaining": None if token_budget is None else max(token_budget - tokens, 0),
            "token_remaining_ratio": None if token_budget is None else max(token_budget - tokens, 0) / token_budget,
            "cost_used_known": cost,
            "cost_records_complete": len(known_costs) == len(rows),
            "cost_budget": cost_budget,
            "cost_remaining": None if cost_budget is None else max(cost_budget - cost, 0.0),
            "status": "NOT_ESTIMABLE" if token_budget is None and cost_budget is None else "ESTIMABLE_FROM_INGESTED_RECEIPTS",
            "provider_dashboard_queried": False,
            "claim_boundary": "Only explicitly ingested provider receipts are counted; missing accounts or sessions are not inferred.",
        }

    @staticmethod
    def estimate_text(text: str, *, content_kind: Literal["PROSE", "CODE", "TRANSCRIPT"] = "PROSE") -> dict[str, Any]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        characters = len(text)
        if content_kind == "CODE":
            lower = math.ceil(characters / 4.0)
            upper = math.ceil(characters / 2.0)
        else:
            lower = math.ceil(characters / 5.0)
            upper = math.ceil(characters / 2.5)
        return {
            "schema": "kch.tokenmaster.token-range.v0.1.0",
            "characters": characters,
            "lower_bound": lower,
            "upper_bound": upper,
            "content_kind": content_kind,
            "exact": False,
            "method": "CONSERVATIVE_CHARACTER_RANGE_NOT_PROVIDER_TOKENIZER",
            "billing_usable": False,
        }

    @staticmethod
    def _complexity(profile: TaskProfile) -> float:
        ambiguity = profile.ambiguity
        if profile.modality == "AUDIO_TRANSCRIPT" and profile.transcript_confidence is not None:
            ambiguity = min(1.0, ambiguity + (1.0 - profile.transcript_confidence) * 0.35)
        return (
            0.22 * ambiguity
            + 0.22 * profile.risk
            + 0.14 * (1.0 - profile.reversibility)
            + 0.18 * profile.coupling
            + 0.18 * profile.semantic_judgment
            + 0.06 * profile.deterministic_volume
        )

    def _layer(self, ordinal: int, role: str, model: str, reasoning: str, work: list[str]) -> dict[str, Any]:
        return {
            "ordinal": ordinal,
            "role": role,
            "model_profile": model,
            "mapped_host_profile": self.policy.model_profiles[model],
            "reasoning": reasoning,
            "work": work,
        }

    def _layers(self, profile: TaskProfile, complexity: float) -> tuple[str, list[dict[str, Any]]]:
        if complexity < 0.28 and profile.deterministic_volume < 0.45:
            return "SINGLE", [
                self._layer(1, "DIRECT_EXECUTION", "ECONOMY", "LOW", ["bounded execution", "proportional verification"])
            ]
        if profile.ambiguity >= 0.65 and profile.risk < 0.55 and profile.coupling < 0.65:
            return "LOW_TO_HIGH", [
                self._layer(1, "CHEAP_DISCOVERY", "ECONOMY", "LOW", ["inventory", "locate evidence", "do not adjudicate"]),
                self._layer(2, "SEMANTIC_SYNTHESIS", "FRONTIER", "HIGH", ["resolve ambiguity", "adjudicate", "freeze plan"]),
            ]
        if complexity >= 0.62 and profile.deterministic_volume >= 0.40:
            return "INTERLEAVED", [
                self._layer(1, "ARCHITECT_AND_FREEZE", "FRONTIER", "HIGH", ["recover objective", "define contracts and gates"]),
                self._layer(2, "DETERMINISTIC_BUILD", "BALANCED", "MEDIUM", ["implement", "batch tools", "run exhaustive bounded tests"]),
                self._layer(3, "INDEPENDENT_ADJUDICATION", "FRONTIER", "HIGH", ["interpret adverse evidence", "enforce claim ceiling", "close materially"]),
            ]
        if profile.deterministic_volume >= 0.60:
            return "HIGH_TO_LOW", [
                self._layer(1, "FREEZE_SCOPE", "FRONTIER" if complexity >= 0.5 else "BALANCED", "HIGH" if complexity >= 0.5 else "MEDIUM", ["define exact scope", "freeze invariants"]),
                self._layer(2, "BULK_EXECUTION", "ECONOMY", "LOW", ["mechanical processing", "hashing", "structured receipts"]),
            ]
        return "SINGLE", [
            self._layer(1, "BALANCED_EXECUTION", "BALANCED", "MEDIUM", ["implement", "test", "explain"])
        ]

    def _topology(self, profile: TaskProfile, budget: dict[str, Any]) -> dict[str, Any]:
        remaining = budget["token_remaining_ratio"]
        genuinely_parallel = (
            profile.independent_units >= 2
            and profile.parallel_fraction >= 0.55
            and profile.coupling <= 0.55
            and not profile.ordered_full_read_required
            and not profile.live_process_monitoring_required
        )
        budget_allows = remaining is None or remaining > max(self.policy.reserve_ratio, 0.20)
        recommended_agents = min(profile.independent_units, self.policy.max_subagents) if genuinely_parallel and budget_allows else 0
        if remaining is not None and remaining <= 0.25:
            recommended_agents = 0
        requested = profile.requested_topology
        if requested == "SINGLE_CHAT":
            topology = "SINGLE_CHAT"
        elif requested == "SCO_SEPARATE_CHATS":
            topology = "SCO_SEPARATE_CHATS" if self.policy.supports_sco_separate_chats else "SINGLE_CHAT_DEGRADED"
        elif requested == "SUBAGENTS":
            topology = "SUBAGENTS" if recommended_agents and self.policy.supports_subagents else "SINGLE_CHAT_DEGRADED"
        elif recommended_agents and self.policy.supports_subagents:
            topology = "SUBAGENTS"
        elif genuinely_parallel and self.policy.supports_sco_separate_chats:
            topology = "SCO_SEPARATE_CHATS"
        else:
            topology = "SINGLE_CHAT"
        automatic = topology == "SUBAGENTS" and self.policy.auto_subagents
        return {
            "topology": topology,
            "recommended_subagents": recommended_agents if topology == "SUBAGENTS" else 0,
            "automatic_launch_authorized": automatic,
            "launch_requires_user_or_session_policy": not automatic,
            "rationale": {
                "genuinely_parallel": genuinely_parallel,
                "coupling": profile.coupling,
                "ordered_full_read_required": profile.ordered_full_read_required,
                "live_process_monitoring_required": profile.live_process_monitoring_required,
                "budget_allows": budget_allows,
            },
            "contracts": [
                "bounded independent objective",
                "explicit input provenance",
                "no shared mutable target unless serialized",
                "receipt with evidence boundary",
                "orchestrator adjudicates without merging chat identities",
            ],
        }

    def _continuity(self, profile: TaskProfile, budget: dict[str, Any]) -> dict[str, Any]:
        remaining = budget["token_remaining_ratio"]
        context_threshold = 0.70 if profile.ordered_full_read_required or profile.risk >= 0.75 else 0.80
        if remaining is not None and remaining <= 0.15:
            cadence = "MATERIAL_EVENTS_PLUS_EARLY_HANDOFF_AT_60_PERCENT_CONTEXT"
        elif profile.coupling >= 0.70 or profile.live_process_monitoring_required:
            cadence = "EVERY_MATERIAL_GATE_AND_BEFORE_LONG_RUNNING_PROCESS"
        else:
            cadence = "MATERIAL_EVENTS_ONLY"
        return {
            "checkpoint_cadence": cadence,
            "context_transfer_threshold": context_threshold,
            "preserve_native_source_boundary": True,
            "never_replace_ordered_read_with_summary": profile.ordered_full_read_required,
            "live_process_terminal_monitoring": profile.live_process_monitoring_required,
            "new_chat_trigger": "context threshold, provider limit, or completed jurisdiction boundary",
            "generation_cost_control": "update structured deltas; do not regenerate settled full documents without material change",
        }

    def plan(self, profile: TaskProfile) -> dict[str, Any]:
        budget = self.budget_status()
        complexity = self._complexity(profile)
        order, layers = self._layers(profile, complexity)
        topology = self._topology(profile, budget)
        if budget["token_remaining_ratio"] is not None and budget["token_remaining_ratio"] <= self.policy.reserve_ratio:
            for layer in layers:
                if layer["role"] not in {"ARCHITECT_AND_FREEZE", "INDEPENDENT_ADJUDICATION"}:
                    layer["model_profile"] = "ECONOMY"
                    layer["mapped_host_profile"] = self.policy.model_profiles["ECONOMY"]
                    layer["reasoning"] = "LOW"
        response_ceiling = self.policy.response_chat_token_ceiling[profile.response_mode]
        decision = {
            "schema": "kch.tokenmaster.execution-plan.v0.1.0",
            "task": asdict(profile),
            "complexity_score": round(complexity, 6),
            "stratification_order": order,
            "layers": layers[:3],
            "topology": topology,
            "budget": budget,
            "continuity": self._continuity(profile, budget),
            "response_contract": {
                "mode": profile.response_mode,
                "chat_token_ceiling": response_ceiling,
                "outputs_constrained_by_chat_mode": False,
                "always_substantive_and_explanatory": True,
                "execution_log_in_chat_by_default": False,
            },
            "efficiency_rules": [
                "reuse verified manifests, hashes and checkpoints",
                "search locates; ordered reading still reaches EOF when required",
                "batch safe independent tool calls",
                "do not spawn agents when coordination overhead exceeds parallel gain",
                "reserve frontier reasoning for architecture and adjudication",
                "preserve adverse evidence and claim boundaries",
            ],
            "active_model_observed": False,
            "active_reasoning_observed": False,
            "recommendation_is_authority": False,
        }
        decision_hash = sha256_json(decision)
        plan_id = f"PLAN-{decision_hash[:20]}"
        plan = {**decision, "plan_id": plan_id, "decision_sha256": decision_hash, "created_at": utc_now()}
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO plans VALUES(?,?,?,?,?)",
                (plan_id, profile.task_id, plan["created_at"], decision_hash, canonical_json(plan)),
            )
        return plan

    @staticmethod
    def user_brief(plan: dict[str, Any]) -> str:
        layers = "; ".join(
            f"{item['ordinal']} {item['role']} ({item['model_profile']}/{item['reasoning']})"
            for item in plan["layers"]
        )
        topology = plan["topology"]
        budget = plan["budget"]
        budget_text = (
            "cuota semanal no estimable con los recibos disponibles"
            if budget["status"] == "NOT_ESTIMABLE"
            else f"saldo semanal estimado {budget['token_remaining_ratio']:.1%}"
        )
        return (
            f"TokenMaster propone {plan['stratification_order']} en {len(plan['layers'])} capa(s): {layers}. "
            f"Topología: {topology['topology']}; subagentes recomendados: {topology['recommended_subagents']}; "
            f"lanzamiento automático: {'sí' if topology['automatic_launch_authorized'] else 'no'}. {budget_text}."
        )
