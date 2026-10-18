#!/usr/bin/env python3
"""BIFM v0.12 — Falcon3 × Belebele multilingual TALM/TALON collector.

One language is executed per job. The model is run once per item under four
cyclic answer-order permutations. TALM/TALON are then applied as transparent
pre-softmax interventions to the same frozen logits.

Outputs are item-level telemetry and decisions. Routing, local threshold
selection and confirmatory adjudication are performed only in the separate
summary stage.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from huggingface_hub import HfApi, hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

from talm_talon_ops import (
    TALM_MASS_RIGHT_SOFT,
    TALON_MASS_RIGHT,
    TALON_MASS_RIGHT_NO_PRESERVE,
    registry_snapshot,
    talm_mass_right_soft,
    talon_mass_right,
    talon_mass_right_no_preserve,
    temperature_control,
)

MODEL_ID = "tiiuae/Falcon3-1B-Instruct"
DATASET_ID = "facebook/belebele"
LANG = os.environ["BIFM_LANG"]
SUPPORTED_LANGS = ("eng_Latn", "fra_Latn", "spa_Latn", "por_Latn")
N_ITEMS = 96
DEV_N = 32
CONFIRM_N = 64
MAX_LENGTH = 640
OUT = Path(os.environ.get("BIFM_OUT", f"bifm_v012_{LANG}"))
OUT.mkdir(parents=True, exist_ok=True)

INSTRUCTIONS = {
    "eng_Latn": {
        "instruction": "Read the passage and answer the multiple-choice question. Return only one letter: A, B, C, or D.",
        "passage": "Passage",
        "question": "Question",
        "answer": "Answer",
    },
    "fra_Latn": {
        "instruction": "Lisez le passage et répondez à la question à choix multiple. Répondez uniquement par une lettre : A, B, C ou D.",
        "passage": "Passage",
        "question": "Question",
        "answer": "Réponse",
    },
    "spa_Latn": {
        "instruction": "Lee el pasaje y responde la pregunta de opción múltiple. Devuelve únicamente una letra: A, B, C o D.",
        "passage": "Pasaje",
        "question": "Pregunta",
        "answer": "Respuesta",
    },
    "por_Latn": {
        "instruction": "Leia o trecho e responda à pergunta de múltipla escolha. Responda apenas com uma letra: A, B, C ou D.",
        "passage": "Trecho",
        "question": "Pergunta",
        "answer": "Resposta",
    },
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def load_json_records(path: str) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return [dict(x) for x in obj]
        if isinstance(obj, dict):
            for key in ("data", "records", "examples"):
                if isinstance(obj.get(key), list):
                    return [dict(x) for x in obj[key]]
            return [dict(obj)]
    except json.JSONDecodeError:
        pass
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def item_key(row: dict[str, Any]) -> str:
    return f"{row['link']}|{row['question_number']}"


def prompt_text(row: dict[str, Any], rotation: int) -> tuple[str, list[int]]:
    meta = INSTRUCTIONS[LANG]
    answers = [row[f"mc_answer{i}"] for i in range(1, 5)]
    order = [(j + rotation) % 4 for j in range(4)]
    labels = "ABCD"
    choices = "\n".join(f"{labels[j]}. {answers[order[j]]}" for j in range(4))
    text = (
        f"{meta['instruction']}\n\n"
        f"{meta['passage']}: {row['flores_passage']}\n\n"
        f"{meta['question']}: {row['question']}\n"
        f"{choices}\n{meta['answer']}:"
    )
    return text, order


def render_chat(tokenizer, content: str) -> str:
    try:
        return tokenizer.apply_chat_template(
            [{"role": "user", "content": content}],
            tokenize=False,
            add_generation_prompt=True,
        )
    except (AttributeError, ValueError, TypeError):
        return content


def find_choice_token_ids(tokenizer) -> dict[str, int]:
    ids: dict[str, int] = {}
    for label in "ABCD":
        found = None
        for candidate in (" " + label, label):
            encoded = tokenizer.encode(candidate, add_special_tokens=False)
            if len(encoded) == 1:
                found = int(encoded[0])
                break
        if found is None:
            raise RuntimeError(f"No single-token form found for answer label {label}")
        ids[label] = found
    if len(set(ids.values())) != 4:
        raise RuntimeError(f"Choice token IDs are not distinct: {ids}")
    return ids


def js_divergence(logits_a: torch.Tensor, logits_b: torch.Tensor) -> torch.Tensor:
    log_a = torch.log_softmax(logits_a, dim=-1)
    log_b = torch.log_softmax(logits_b, dim=-1)
    p = log_a.exp()
    q = log_b.exp()
    m = 0.5 * (p + q)
    log_m = torch.log(m.clamp_min(1e-30))
    return 0.5 * ((p * (log_a - log_m)).sum(-1) + (q * (log_b - log_m)).sum(-1))


def topk_overlap(logits_a: torch.Tensor, logits_b: torch.Tensor, k: int) -> torch.Tensor:
    a = torch.topk(logits_a, k, dim=-1).indices
    b = torch.topk(logits_b, k, dim=-1).indices
    values = []
    for ai, bi in zip(a, b):
        values.append(len(set(ai.tolist()).intersection(bi.tolist())) / k)
    return torch.tensor(values, dtype=torch.float32)


def aggregate_choice_scores(scores: torch.Tensor, maps: list[list[int]]) -> torch.Tensor:
    """Map displayed A/B/C/D logits back to answer content and average rotations."""
    out = torch.zeros(4, dtype=torch.float32)
    for rotation in range(4):
        for shown_index, original_index in enumerate(maps[rotation]):
            out[original_index] += scores[rotation, shown_index] / 4.0
    return out


def choice_metrics(choice_logits: torch.Tensor, correct: int) -> dict[str, float | int]:
    probs = torch.softmax(choice_logits, dim=-1)
    pred = int(choice_logits.argmax().item())
    sorted_values, sorted_indices = torch.sort(choice_logits, descending=True)
    rank = int((sorted_indices == correct).nonzero(as_tuple=False)[0, 0].item()) + 1
    top_margin = float((sorted_values[0] - sorted_values[1]).item())
    entropy = float((-(probs * torch.log(probs.clamp_min(1e-30))).sum()).item())
    correct_prob = float(probs[correct].item())
    log_loss = float(-math.log(max(correct_prob, 1e-30)))
    target = torch.zeros(4)
    target[correct] = 1.0
    brier = float(((probs - target) ** 2).mean().item())
    correct_margin = float((choice_logits[correct] - choice_logits[torch.arange(4) != correct].max()).item())
    return {
        "pred": pred,
        "correct": int(pred == correct),
        "correct_prob": correct_prob,
        "log_loss": log_loss,
        "brier": brier,
        "top_margin": top_margin,
        "correct_margin": correct_margin,
        "choice_entropy": entropy,
        "correct_rank": rank,
    }


def main() -> None:
    if LANG not in SUPPORTED_LANGS:
        raise ValueError(f"Unsupported BIFM_LANG={LANG}; expected one of {SUPPORTED_LANGS}")
    started = time.time()
    torch.manual_seed(0)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))

    api = HfApi()
    model_sha = api.model_info(MODEL_ID).sha
    dataset_sha = api.dataset_info(DATASET_ID).sha
    data_file = hf_hub_download(
        repo_id=DATASET_ID,
        repo_type="dataset",
        filename=f"data/{LANG}.json",
        revision=dataset_sha,
    )
    rows = load_json_records(data_file)
    rows = sorted(rows, key=lambda row: sha256_text(item_key(row)))[:N_ITEMS]
    if len(rows) != N_ITEMS:
        raise RuntimeError(f"Expected {N_ITEMS} records for {LANG}, got {len(rows)}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=model_sha)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        revision=model_sha,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    )
    model.eval()
    choice_ids = find_choice_token_ids(tokenizer)

    records: list[dict[str, Any]] = []
    preserve_violations = {"talm": 0, "talon": 0}
    nontrivial_residuals = {"talm": [], "talon": [], "talon_actuator": []}

    with torch.inference_mode():
        for item_index, row in enumerate(rows):
            prompts: list[str] = []
            maps: list[list[int]] = []
            for rotation in range(4):
                raw_prompt, order = prompt_text(row, rotation)
                prompts.append(render_chat(tokenizer, raw_prompt))
                maps.append(order)
            encoded = tokenizer(
                prompts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
            )
            core = model.model(**encoded, use_cache=False, return_dict=True)
            raw_logits = model.lm_head(core.last_hidden_state[:, -1, :]).detach().float().cpu()
            temp_logits = temperature_control(raw_logits, 0.8)
            talm_logits, talm_tel = talm_mass_right_soft(raw_logits)
            talon_logits, talon_tel = talon_mass_right(raw_logits)
            actuator_logits, actuator_tel = talon_mass_right_no_preserve(raw_logits)

            preserve_violations["talm"] += talm_tel.changed_global_top1
            preserve_violations["talon"] += talon_tel.changed_global_top1
            nontrivial_residuals["talm"].append(talm_tel.constant_shift_residual_mean)
            nontrivial_residuals["talon"].append(talon_tel.constant_shift_residual_mean)
            nontrivial_residuals["talon_actuator"].append(actuator_tel.constant_shift_residual_mean)

            method_logits = {
                "baseline": raw_logits,
                "temp08_control": temp_logits,
                "talm_sensor": talm_logits,
                "talon_sensor": talon_logits,
                "talon_actuator": actuator_logits,
            }
            choice_by_method: dict[str, torch.Tensor] = {}
            metrics_by_method: dict[str, dict[str, float | int]] = {}
            correct_index = int(row["correct_answer_num"]) - 1
            for name, full_logits in method_logits.items():
                shown = torch.stack(
                    [full_logits[:, choice_ids[label]] for label in "ABCD"], dim=1
                )
                aggregated = aggregate_choice_scores(shown, maps)
                choice_by_method[name] = aggregated
                metrics_by_method[name] = choice_metrics(aggregated, correct_index)

            baseline_choice_prob = torch.softmax(choice_by_method["baseline"], dim=-1)
            temp_choice_prob = torch.softmax(choice_by_method["temp08_control"], dim=-1)
            talm_choice_prob = torch.softmax(choice_by_method["talm_sensor"], dim=-1)
            talon_choice_prob = torch.softmax(choice_by_method["talon_sensor"], dim=-1)
            actuator_choice_prob = torch.softmax(choice_by_method["talon_actuator"], dim=-1)

            def choice_js(a: torch.Tensor, b: torch.Tensor) -> float:
                m = 0.5 * (a + b)
                return float(
                    0.5
                    * (
                        (a * (torch.log(a.clamp_min(1e-30)) - torch.log(m.clamp_min(1e-30)))).sum()
                        + (b * (torch.log(b.clamp_min(1e-30)) - torch.log(m.clamp_min(1e-30)))).sum()
                    ).item()
                )

            split = "development" if item_index < DEV_N else "confirmatory"
            record: dict[str, Any] = {
                "language": LANG,
                "item_index": item_index,
                "split": split,
                "item_key": item_key(row),
                "item_key_sha256": sha256_text(item_key(row)),
                "correct_index": correct_index,
                "prompt_bundle_sha256": sha256_text("\n---ROTATION---\n".join(prompts)),
                "baseline_margin": metrics_by_method["baseline"]["top_margin"],
                "temp08_margin": metrics_by_method["temp08_control"]["top_margin"],
                "baseline_entropy": metrics_by_method["baseline"]["choice_entropy"],
                "temp08_entropy": metrics_by_method["temp08_control"]["choice_entropy"],
            }
            for method, metrics in metrics_by_method.items():
                for key, value in metrics.items():
                    record[f"{method}_{key}"] = value

            record.update(
                {
                    "talm_full_js_vs_baseline": float(js_divergence(raw_logits, talm_logits).mean().item()),
                    "talm_choice_js_vs_baseline": choice_js(baseline_choice_prob, talm_choice_prob),
                    "talm_top10_overlap": float(topk_overlap(raw_logits, talm_logits, 10).mean().item()),
                    "talm_top50_overlap": float(topk_overlap(raw_logits, talm_logits, 50).mean().item()),
                    "talon_full_js_vs_temp08": float(js_divergence(temp_logits, talon_logits).mean().item()),
                    "talon_choice_js_vs_temp08": choice_js(temp_choice_prob, talon_choice_prob),
                    "talon_top10_overlap": float(topk_overlap(temp_logits, talon_logits, 10).mean().item()),
                    "talon_top50_overlap": float(topk_overlap(temp_logits, talon_logits, 50).mean().item()),
                    "actuator_full_js_vs_temp08": float(js_divergence(temp_logits, actuator_logits).mean().item()),
                    "actuator_choice_js_vs_temp08": choice_js(temp_choice_prob, actuator_choice_prob),
                    "actuator_top10_overlap": float(topk_overlap(temp_logits, actuator_logits, 10).mean().item()),
                    "actuator_top50_overlap": float(topk_overlap(temp_logits, actuator_logits, 50).mean().item()),
                    "actuator_delta_correct_prob": float(
                        metrics_by_method["talon_actuator"]["correct_prob"]
                        - metrics_by_method["temp08_control"]["correct_prob"]
                    ),
                    "actuator_rescue": int(
                        metrics_by_method["temp08_control"]["correct"] == 0
                        and metrics_by_method["talon_actuator"]["correct"] == 1
                    ),
                    "actuator_harm": int(
                        metrics_by_method["temp08_control"]["correct"] == 1
                        and metrics_by_method["talon_actuator"]["correct"] == 0
                    ),
                    "actuator_choice_changed": int(
                        metrics_by_method["temp08_control"]["pred"]
                        != metrics_by_method["talon_actuator"]["pred"]
                    ),
                    "talm_selected_left": talm_tel.selected_left,
                    "talm_selected_right": talm_tel.selected_right,
                    "talm_delta_l2": talm_tel.delta_l2_mean,
                    "talm_delta_linf": talm_tel.delta_linf_mean,
                    "talm_constant_shift_residual": talm_tel.constant_shift_residual_mean,
                    "talon_selected_right": talon_tel.selected_right,
                    "talon_delta_l2": talon_tel.delta_l2_mean,
                    "talon_delta_linf": talon_tel.delta_linf_mean,
                    "talon_constant_shift_residual": talon_tel.constant_shift_residual_mean,
                    "actuator_delta_l2": actuator_tel.delta_l2_mean,
                    "actuator_delta_linf": actuator_tel.delta_linf_mean,
                    "actuator_constant_shift_residual": actuator_tel.constant_shift_residual_mean,
                }
            )
            records.append(record)

    if preserve_violations != {"talm": 0, "talon": 0}:
        raise AssertionError(f"Top-1 preservation failure: {preserve_violations}")
    for name, values in nontrivial_residuals.items():
        if max(values) <= 1e-8:
            raise AssertionError(f"Operator {name} reduced to an effectively constant shift")

    frame = pd.DataFrame(records)
    frame.to_csv(OUT / f"{LANG}_item_records.csv", index=False)
    receipt = {
        "status": "PASS",
        "language": LANG,
        "model": {
            "id": MODEL_ID,
            "revision": model_sha,
            "parameter_count": int(sum(p.numel() for p in model.parameters())),
            "architecture": model.config.model_type,
            "num_hidden_layers": getattr(model.config, "num_hidden_layers", None),
        },
        "dataset": {
            "id": DATASET_ID,
            "revision": dataset_sha,
            "file": f"data/{LANG}.json",
            "n_items": N_ITEMS,
            "selection": "SHA256(link|question_number), first 96",
            "development_n": DEV_N,
            "confirmatory_n": CONFIRM_N,
        },
        "task_wrapper": INSTRUCTIONS[LANG],
        "choice_token_ids": choice_ids,
        "operators": registry_snapshot(),
        "preserve_top1_violations": preserve_violations,
        "operator_nontriviality": {
            key: {
                "min_constant_shift_residual": float(min(values)),
                "mean_constant_shift_residual": float(np.mean(values)),
                "max_constant_shift_residual": float(max(values)),
            }
            for key, values in nontrivial_residuals.items()
        },
        "records": len(records),
        "software": {
            "python": sys.version,
            "torch": torch.__version__,
            "pandas": pd.__version__,
            "platform": platform.platform(),
        },
        "elapsed_seconds": time.time() - started,
        "claim_boundary": [
            "The historical operator configurations are exact registry records; the formulas are a transparent registry-conformant reimplementation, not a byte-identical-source claim.",
            "Preserve arms are sensor probes. The no-preserve TALON arm is an offline actuator ablation and has no execution authority.",
            "The experiment supports local language- and segment-specific claims only.",
        ],
    }
    dump(OUT / f"{LANG}_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
