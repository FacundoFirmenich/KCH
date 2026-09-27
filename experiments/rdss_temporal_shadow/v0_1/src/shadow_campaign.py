#!/usr/bin/env python3
"""Prospective common-state SHADOW campaign for the historical v0.4 lineage.

The default generation branch is always TALON mass-right.  At configured
checkpoints, candidate operators are applied to cloned logits only.  Optional
counterfactual continuations run only on an authorized development split or an
explicitly frozen protected reserve, always from the exact TMR prefix captured
at a checkpoint.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, Iterable, Mapping, Sequence

import numpy as np
import torch
from transformers import LogitsProcessorList, StoppingCriteriaList


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream"
if str(UPSTREAM) not in sys.path:
    sys.path.insert(0, str(UPSTREAM))

import cfldr_plus_v0_4_repaired as v04  # noqa: E402


DEFAULT_ACTION = "talon_mass_right"
RESCUE_ACTIONS = (
    "talon_mass_left",
    "talm_mass_right_soft",
    "baseline",
)
BRANCH_ACTIONS = (DEFAULT_ACTION,) + RESCUE_ACTIONS
CHECKPOINTS = (0, 16, 32, 64)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256(canonical_json(list(parts)).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    atomic_text(path, "".join(canonical_json(dict(row)) + "\n" for row in rows))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def raw_state_features(scores: torch.Tensor) -> Dict[str, float]:
    logits = scores.detach().float()
    probabilities = torch.softmax(logits, dim=-1)
    top_values, _ = torch.topk(probabilities, k=min(2, probabilities.shape[-1]), dim=-1)
    entropy = -torch.sum(
        probabilities * torch.log(torch.clamp(probabilities, min=1e-12)), dim=-1
    )
    vocab_norm = math.log(max(2, probabilities.shape[-1]))
    top1 = float(top_values[:, 0].mean().cpu())
    top2 = float(top_values[:, 1].mean().cpu()) if top_values.shape[-1] > 1 else 0.0
    return {
        "raw_entropy_normalized": float((entropy / vocab_norm).mean().cpu()),
        "raw_top1_probability": top1,
        "raw_top2_probability": top2,
        "raw_top1_top2_margin": top1 - top2,
    }


class TMRCommonStateShadowProcessor(v04.LogitsProcessor):
    """Generate with persistent TMR while probing fresh operators on clones."""

    def __init__(
        self,
        prompt_spec: v04.PromptSpec,
        checkpoints: Sequence[int] = CHECKPOINTS,
    ) -> None:
        self.prompt_spec = prompt_spec
        self.checkpoints = tuple(sorted(set(int(x) for x in checkpoints if int(x) >= 0)))
        self.default_processor = v04.ProjectedOperatorProcessor(DEFAULT_ACTION)
        self.step_index = 0
        self.trace: list[dict[str, Any]] = []

    def _capture(self, input_ids: torch.Tensor, scores: torch.Tensor) -> None:
        fingerprints: dict[str, dict[str, float]] = {}
        for action in BRANCH_ACTIONS:
            _, fp = v04.apply_action_once(action, input_ids, scores.clone())
            fingerprints[action] = fp

        event = {
            "step": self.step_index,
            "normalized_position": float(
                self.step_index / max(1, self.prompt_spec.max_new_tokens)
            ),
            "default_action": DEFAULT_ACTION,
            "probe_actions": list(RESCUE_ACTIONS),
            "prefix_token_ids": input_ids[0].detach().cpu().tolist(),
            "state": raw_state_features(scores),
            "fingerprints": fingerprints,
            "probe_sampled_tokens": False,
            "probe_mutated_generation_state": False,
        }
        self.trace.append(event)

    def __call__(self, input_ids: torch.Tensor, scores: torch.Tensor) -> torch.Tensor:
        if self.step_index in self.checkpoints:
            self._capture(input_ids, scores)
        output = self.default_processor(input_ids, scores)
        self.step_index += 1
        return output

    def summary(self) -> Dict[str, Any]:
        return {
            "mode": "SHADOW_ONLY",
            "generation_action": DEFAULT_ACTION,
            "checkpoints_requested": list(self.checkpoints),
            "checkpoints_observed": [event["step"] for event in self.trace],
            "trace": self.trace,
            "default_processor": self.default_processor.summary(),
        }


def generation_kwargs(tokenizer: Any, spec: v04.PromptSpec, stopping: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "max_new_tokens": spec.max_new_tokens,
        "do_sample": True,
        "temperature": v04.BASE_TEMPERATURE,
        "top_p": v04.BASE_TOP_P,
        "repetition_penalty": v04.REPETITION_PENALTY,
        "no_repeat_ngram_size": v04.NO_REPEAT_NGRAM_SIZE,
        "use_cache": True,
        "renormalize_logits": True,
        "pad_token_id": int(tokenizer.pad_token_id),
        "stopping_criteria": stopping,
    }
    if tokenizer.eos_token_id is not None:
        kwargs["eos_token_id"] = int(tokenizer.eos_token_id)
    return kwargs


def generate_shadow_one(
    tokenizer: Any,
    model: Any,
    device: Any,
    spec: v04.PromptSpec,
    seed: int,
) -> dict[str, Any]:
    v04.set_seed(seed)
    prompt_text, inputs, prompt_length = v04.encode_prompt(tokenizer, spec, device)
    processor = TMRCommonStateShadowProcessor(spec)
    stopping = StoppingCriteriaList([
        v04.ContractStoppingCriteria(
            tokenizer, prompt_length, spec.id, spec.answer_prefill
        )
    ])
    kwargs = generation_kwargs(tokenizer, spec, stopping)

    started = time.time()
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            logits_processor=LogitsProcessorList([processor]),
            **kwargs,
        )
    elapsed = time.time() - started

    new_ids = generated[0, prompt_length:].detach().cpu().tolist()
    continuation = tokenizer.decode(
        new_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    answer = (spec.answer_prefill + continuation).strip()
    validation = v04.validate_answer(spec.id, answer)
    summary = processor.summary()

    return {
        "prompt_id": spec.id,
        "task_type": spec.task_type,
        "concept_name": spec.concept_name,
        "router_profile": spec.router_profile,
        "prompt": prompt_text,
        "prompt_length": int(prompt_length),
        "seed": int(seed),
        "method": "rdss_shadow_tmr",
        "generation_action": DEFAULT_ACTION,
        "status": "ok",
        "answer_text": answer,
        "continuation_text": continuation,
        "generated_token_ids_json": canonical_json(new_ids),
        "new_token_count": len(new_ids),
        "contract_pass": bool(validation["contract_pass"]),
        "semantic_score": float(validation["semantic_score"]),
        "automatic_utility": (
            0.70 * float(validation["contract_pass"])
            + 0.30 * float(validation["semantic_score"])
        ),
        "generation_seconds": float(elapsed),
        "shadow_trace_json": canonical_json(summary["trace"]),
        "shadow_checkpoint_count": len(summary["trace"]),
        "shadow_mode": "SHADOW_ONLY",
        "method_config_hash": v04.METHOD_CONFIG_HASH,
        "prompt_suite_hash": v04.PROMPT_SUITE_HASH,
    }


def generate_fixed_one(
    tokenizer: Any,
    model: Any,
    device: Any,
    spec: v04.PromptSpec,
    seed: int,
) -> dict[str, Any]:
    """Generate the exact fixed-TMR control while retaining sampled token IDs."""
    v04.set_seed(seed)
    _, inputs, prompt_length = v04.encode_prompt(tokenizer, spec, device)
    processor = v04.ProjectedOperatorProcessor(DEFAULT_ACTION)
    stopping = StoppingCriteriaList([
        v04.ContractStoppingCriteria(
            tokenizer, prompt_length, spec.id, spec.answer_prefill
        )
    ])
    kwargs = generation_kwargs(tokenizer, spec, stopping)
    started = time.time()
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            logits_processor=LogitsProcessorList([processor]),
            **kwargs,
        )
    elapsed = time.time() - started
    token_ids = generated[0, prompt_length:].detach().cpu().tolist()
    continuation = tokenizer.decode(
        token_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    answer = (spec.answer_prefill + continuation).strip()
    validation = v04.validate_answer(spec.id, answer)
    return {
        "prompt_id": spec.id,
        "seed": int(seed),
        "method": "fixed_tmr",
        "generation_action": DEFAULT_ACTION,
        "status": "ok",
        "answer_text": answer,
        "continuation_text": continuation,
        "generated_token_ids_json": canonical_json(token_ids),
        "new_token_count": len(token_ids),
        "contract_pass": bool(validation["contract_pass"]),
        "semantic_score": float(validation["semantic_score"]),
        "automatic_utility": (
            0.70 * float(validation["contract_pass"])
            + 0.30 * float(validation["semantic_score"])
        ),
        "generation_seconds": float(elapsed),
        "method_config_hash": v04.METHOD_CONFIG_HASH,
        "prompt_suite_hash": v04.PROMPT_SUITE_HASH,
    }


def counterfactual_rollout(
    *,
    tokenizer: Any,
    model: Any,
    device: Any,
    spec: v04.PromptSpec,
    original_prompt_length: int,
    checkpoint_event: Mapping[str, Any],
    action: str,
    branch_seed: int,
) -> dict[str, Any]:
    prefix_ids = list(checkpoint_event["prefix_token_ids"])
    generated_before = len(prefix_ids) - int(original_prompt_length)
    remaining = max(1, int(spec.max_new_tokens) - generated_before)
    input_ids = torch.tensor([prefix_ids], dtype=torch.long, device=device)
    attention_mask = torch.ones_like(input_ids)

    processor = None
    if action != "baseline":
        processor = v04.ProjectedOperatorProcessor(action)
    processors = LogitsProcessorList([processor]) if processor is not None else None
    stopping = StoppingCriteriaList([
        v04.ContractStoppingCriteria(
            tokenizer, original_prompt_length, spec.id, spec.answer_prefill
        )
    ])
    kwargs = generation_kwargs(tokenizer, spec, stopping)
    kwargs["max_new_tokens"] = remaining

    v04.set_seed(branch_seed)
    with torch.inference_mode():
        generated = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            logits_processor=processors,
            **kwargs,
        )

    all_new_ids = generated[0, original_prompt_length:].detach().cpu().tolist()
    continuation = tokenizer.decode(
        all_new_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    answer = (spec.answer_prefill + continuation).strip()
    validation = v04.validate_answer(spec.id, answer)
    return {
        "prompt_id": spec.id,
        "checkpoint_step": int(checkpoint_event["step"]),
        "action": action,
        "branch_seed": int(branch_seed),
        "tokens_before_branch": int(generated_before),
        "answer_text": answer,
        "contract_pass": bool(validation["contract_pass"]),
        "semantic_score": float(validation["semantic_score"]),
        "automatic_utility": (
            0.70 * float(validation["contract_pass"])
            + 0.30 * float(validation["semantic_score"])
        ),
        "state_json": canonical_json(checkpoint_event),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=14)
    parser.add_argument("--output-root", type=Path, default=Path("/kaggle/working"))
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--campaign-prompt-ids",
        default="",
        help="Optional comma-separated exact prompt IDs to execute; empty means the full campaign.",
    )
    parser.add_argument("--counterfactuals", action="store_true")
    parser.add_argument(
        "--development-prompt-ids",
        default="p01,p02,p03,p04,p05,p06",
        help="Comma-separated counterfactual authorization set.",
    )
    parser.add_argument("--protected-reserve", action="store_true")
    parser.add_argument("--freeze-id", default="")
    parser.add_argument("--expected-method-config-hash", default="")
    parser.add_argument("--expected-prompt-suite-hash", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    development_ids = {
        item.strip() for item in args.development_prompt_ids.split(",") if item.strip()
    }
    reserve_ids = {"p07", "p08", "p09", "p10"}
    if args.protected_reserve:
        if args.freeze_id != "rdss-v0.1-g2-always-tmr-2026-09-27":
            raise ValueError("Protected reserve requires the locked G2 freeze ID.")
        if development_ids != reserve_ids:
            raise ValueError("Protected reserve authorization must be exactly p07-p10.")
        if args.expected_method_config_hash != v04.METHOD_CONFIG_HASH:
            raise ValueError("Method-config hash does not match the freeze.")
        if args.expected_prompt_suite_hash != v04.PROMPT_SUITE_HASH:
            raise ValueError("Prompt-suite hash does not match the freeze.")
    elif development_ids & reserve_ids:
        raise ValueError("Reserve prompt IDs require --protected-reserve and frozen hashes.")
    prompts = list(v04.PROMPTS)
    campaign_ids = {
        item.strip() for item in args.campaign_prompt_ids.split(",") if item.strip()
    }
    if campaign_ids:
        known_ids = {spec.id for spec in prompts}
        unknown_ids = sorted(campaign_ids - known_ids)
        if unknown_ids:
            raise ValueError("Unknown campaign prompt IDs: " + ", ".join(unknown_ids))
        prompts = [spec for spec in prompts if spec.id in campaign_ids]
    if args.limit is not None:
        prompts = prompts[: max(0, args.limit)]

    output = args.output_root / f"RDSS_TEMPORAL_SHADOW_V0_1_SEED_{args.seed}"
    reserve_marker = output / "RESERVE_CONSUMED.json"
    if args.protected_reserve and reserve_marker.exists():
        raise RuntimeError("Protected reserve already consumed for this output root.")
    output.mkdir(parents=True, exist_ok=True)
    tokenizer, model, device = v04.load_model_and_tokenizer(v04.MODEL_ID)

    rows: list[dict[str, Any]] = []
    rollouts: list[dict[str, Any]] = []
    identity_failures: list[str] = []

    for spec in prompts:
        fixed = generate_fixed_one(tokenizer, model, device, spec, args.seed)
        shadow = generate_shadow_one(tokenizer, model, device, spec, args.seed)

        identical = (
            fixed["generated_token_ids_json"] == shadow["generated_token_ids_json"]
        )
        fixed["non_interference_identity"] = bool(identical)
        shadow["non_interference_identity"] = bool(identical)
        rows.extend([fixed, shadow])
        if not identical:
            identity_failures.append(spec.id)

        if args.counterfactuals:
            if spec.id not in development_ids:
                continue
            trace = json.loads(shadow["shadow_trace_json"])
            for event in trace:
                branch_seed = stable_seed(
                    "rdss-shadow-v0.1", spec.id, args.seed, event["step"]
                )
                for action in BRANCH_ACTIONS:
                    result = counterfactual_rollout(
                        tokenizer=tokenizer,
                        model=model,
                        device=device,
                        spec=spec,
                        original_prompt_length=int(shadow["prompt_length"]),
                        checkpoint_event=event,
                        action=action,
                        branch_seed=branch_seed,
                    )
                    result["source_seed"] = int(args.seed)
                    result["split"] = (
                        "protected_reserve" if args.protected_reserve else "development"
                    )
                    rollouts.append(result)

        write_jsonl(output / "campaign_rows.jsonl", rows)
        if rollouts:
            write_jsonl(output / "counterfactual_rollouts.jsonl", rollouts)

    write_csv(output / "campaign_rows.csv", rows)
    if rollouts:
        write_csv(output / "counterfactual_rollouts.csv", rollouts)

    manifest = {
        "gate": "RDSS Temporal Common-State SHADOW Gate",
        "version": "0.1.0",
        "scientific_state": (
            "NON_INTERFERENCE_FAILED"
            if identity_failures
            else (
                "G2_PROTECTED_RESERVE_COMPLETE"
                if args.protected_reserve
                else ("G1B_DEVELOPMENT_COMPLETE" if args.counterfactuals else "G1A_COMPLETE")
            )
        ),
        "seed": int(args.seed),
        "model": v04.MODEL_ID,
        "operator_lineage": "historical_v04_common_projection",
        "default_action": DEFAULT_ACTION,
        "prompts": [spec.id for spec in prompts],
        "campaign_prompt_ids_filter": sorted(campaign_ids),
        "development_prompt_ids": sorted(development_ids),
        "counterfactuals_enabled": bool(args.counterfactuals),
        "protected_reserve_evaluation": bool(args.protected_reserve),
        "freeze_id": args.freeze_id if args.protected_reserve else None,
        "expected_method_config_hash": args.expected_method_config_hash or None,
        "expected_prompt_suite_hash": args.expected_prompt_suite_hash or None,
        "non_interference_identity_pass": not identity_failures,
        "identity_failures": identity_failures,
        "campaign_rows": len(rows),
        "counterfactual_rows": len(rollouts),
        "method_config_hash": v04.METHOD_CONFIG_HASH,
        "prompt_suite_hash": v04.PROMPT_SUITE_HASH,
    }
    atomic_text(output / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))

    if identity_failures:
        raise RuntimeError(
            "SHADOW violated non-interference for: " + ", ".join(identity_failures)
        )
    if args.protected_reserve:
        atomic_text(
            reserve_marker,
            json.dumps(
                {
                    "freeze_id": args.freeze_id,
                    "method_config_hash": v04.METHOD_CONFIG_HASH,
                    "prompt_suite_hash": v04.PROMPT_SUITE_HASH,
                    "policy": "always_talon_mass_right",
                    "reserve_consumed": True,
                },
                indent=2,
                sort_keys=True,
            ),
        )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
