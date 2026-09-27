#!/usr/bin/env python3
"""
CFLDR Plus v0.4 — repaired Qwen3.5-4B-Base evaluator.

Purpose
-------
A separate repaired campaign that corrects the defects observed in v0.3:

- no universal 192-token cap;
- repaired p01-p10 suite;
- answer-channel prefill instead of visible scratchpad;
- contract-aware stopping criteria;
- only four active static operator branches;
- no external sampler;
- one sampling temperature;
- common top-1 projection outside TALM/TALON;
- prerouter without a global TALON family prior;
- inline routing with two-confirmation switching, one switch maximum,
  late-generation lock, dwell and cooldown;
- automatic contract/semantic validation saved per row;
- post-hoc Z_PH and automatic oracle kept separate from Human Eval;
- robust atomic checkpoints and resume.

The only user-editable experimental variable in the Kaggle notebook is SEED.
"""

from __future__ import annotations

import argparse
import ast
import csv
from collections import Counter
import dataclasses
import difflib
import hashlib
import itertools
import json
import math
import os
import random
import re
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

try:
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        LogitsProcessor,
        LogitsProcessorList,
        StoppingCriteria,
        StoppingCriteriaList,
    )
    TRANSFORMERS_AVAILABLE = True
except Exception:
    TRANSFORMERS_AVAILABLE = False
    AutoModelForCausalLM = None
    AutoTokenizer = None
    BitsAndBytesConfig = None

    class LogitsProcessor:
        pass

    class LogitsProcessorList(list):
        def __call__(self, input_ids, scores):
            output = scores
            for processor in self:
                output = processor(input_ids, output)
            return output

    class StoppingCriteria:
        pass

    class StoppingCriteriaList(list):
        def __call__(self, input_ids, scores, **kwargs):
            return any(
                criterion(input_ids, scores, **kwargs)
                for criterion in self
            )

from canonical_talm_talon import (
    TALONOperatorConfig,
    TALONLogitProcessor,
    TALMOperatorConfig,
    TALMLogitProcessor,
)


# =====================================================================
# Configuration
# =====================================================================

MODEL_ID = "Qwen/Qwen3.5-4B-Base"
MODEL_LABEL = "Qwen35_4B_BASE_ENNative_CFLDR_PLUS_V04_REPAIRED"
ENGINE_NAME = "CFLDR Plus"
ENGINE_VERSION = "0.4.0"
SUITE_VERSION = "CFLDR_PLUS_REPAIRED_P01_P10_v4"
BASE_TEMPERATURE = 0.85
BASE_TOP_P = 0.95
CONTROL_SEED_OFFSET = 100000
SAVE_EVERY = 20
USE_4BIT = True
REQUIRE_CUDA = True
ATTN_IMPLEMENTATION = "eager"
NO_REPEAT_NGRAM_SIZE = 0
REPETITION_PENALTY = 1.0
ROUTER_POLICY_VERSION = "CFLDR_PLUS_MECHANISTIC_POLICY_v0.4_FROZEN"
Z_PH_NAME = "Z_PH"

ACTIVE_STATIC_ACTIONS = (
    "talm_mass_right_soft",
    "talm_mass_left_soft",
    "talon_mass_right",
    "talon_mass_left",
)
ROUTER_CANDIDATES = ("baseline",) + ACTIVE_STATIC_ACTIONS
METHOD_ORDER = (
    "baseline",
    "baseline_control",
    "talm_mass_right_soft",
    "talm_mass_left_soft",
    "talon_mass_right",
    "talon_mass_left",
    "cfldr_plus_preroute",
    "cfldr_plus_inline",
)


# =====================================================================
# General utilities
# =====================================================================

def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def cuda_cleanup() -> None:
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass


def softmax_np(logits: np.ndarray) -> np.ndarray:
    x = np.asarray(logits, dtype=np.float64).reshape(-1)
    x = x - np.max(x)
    e = np.exp(x)
    return e / max(float(e.sum()), 1e-300)


def entropy_np(probabilities: np.ndarray) -> float:
    p = np.asarray(probabilities, dtype=np.float64)
    return float(-np.sum(p * np.log(p + 1e-300)))


def distinct_n(ids: Sequence[int], n: int) -> float:
    if len(ids) < n:
        return 0.0
    grams = [tuple(ids[i:i+n]) for i in range(len(ids)-n+1)]
    return len(set(grams)) / len(grams)


def repetition_rate(ids: Sequence[int], n: int) -> float:
    return 1.0 - distinct_n(ids, n) if len(ids) >= n else 0.0


def token_entropy(ids: Sequence[int]) -> float:
    if not ids:
        return 0.0
    _, counts = np.unique(np.asarray(ids), return_counts=True)
    p = counts / counts.sum()
    return float(-(p * np.log(np.clip(p, 1e-12, 1.0))).sum())


def sequence_distance(a: str, b: str) -> float:
    return 1.0 - difflib.SequenceMatcher(None, a or "", b or "").ratio()


def jaccard_distance(a: str, b: str) -> float:
    sa = set((a or "").lower().split())
    sb = set((b or "").lower().split())
    if not sa and not sb:
        return 0.0
    return 1.0 - len(sa & sb) / max(1, len(sa | sb))


def safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def atomic_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows)
    atomic_write_text(path, text)


def atomic_write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if not rows:
        temporary.write_text("", encoding="utf-8")
    else:
        fields = sorted({key for row in rows for key in row.keys()})
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    temporary.replace(path)


# =====================================================================
# Repaired prompt suite and exact answers
# =====================================================================

@dataclass(frozen=True)
class PromptSpec:
    id: str
    task_type: str
    concept_name: str
    task: str
    answer_prefill: str
    max_new_tokens: int
    router_profile: str


def all_topological_orders() -> List[Tuple[str, ...]]:
    nodes = tuple("PQRSTUV")
    prerequisites = {
        "P": set(),
        "Q": {"P"},
        "R": {"P"},
        "S": {"Q", "R"},
        "T": {"R"},
        "U": {"S", "T"},
        "V": {"Q"},
    }
    prerequisites = {k: v for k, v in prerequisites.items() if k in nodes}

    output: List[Tuple[str, ...]] = []

    def visit(prefix: Tuple[str, ...], remaining: set[str]) -> None:
        if not remaining:
            output.append(prefix)
            return
        available = sorted(
            node for node in remaining
            if prerequisites[node].issubset(set(prefix))
        )
        for node in available:
            visit(prefix + (node,), remaining - {node})

    visit(tuple(), set(nodes))
    return sorted(output)


TOPO_ORDERS = all_topological_orders()
assert len(TOPO_ORDERS) == 21
TOPO_FIRST10 = TOPO_ORDERS[:10]

FSM_INPUTS = [
    "START", "PAUSE", "RESUME", "FAULT", "RESET", "START",
    "STOP", "FAULT", "RESET", "START", "PAUSE", "STOP",
]
FSM_RULES = {
    "IDLE": {"START": "ACTIVE", "FAULT": "ERROR"},
    "ACTIVE": {"PAUSE": "SUSPENDED", "FAULT": "ERROR", "STOP": "IDLE"},
    "SUSPENDED": {"RESUME": "ACTIVE", "STOP": "IDLE", "FAULT": "ERROR"},
    "ERROR": {"RESET": "IDLE"},
}
FSM_TRACE: List[Tuple[int, str, str, str]] = []
_state = "IDLE"
for _index, _input in enumerate(FSM_INPUTS, 1):
    _next = FSM_RULES.get(_state, {}).get(_input, _state)
    FSM_TRACE.append((_index, _input, _state, _next))
    _state = _next

GRID_MOVES = [
    "NORTH", "EAST", "EAST", "SOUTH", "SOUTH", "WEST",
    "NORTH", "EAST", "NORTH", "WEST", "WEST", "SOUTH",
]
GRID_TRACE: List[Tuple[int, str, Tuple[int, int], Tuple[int, int], str]] = []
_pos = (2, 2)
for _index, _direction in enumerate(GRID_MOVES, 1):
    dr, dc = {
        "NORTH": (-1, 0),
        "SOUTH": (1, 0),
        "EAST": (0, 1),
        "WEST": (0, -1),
    }[_direction]
    candidate = (_pos[0] + dr, _pos[1] + dc)
    if 1 <= candidate[0] <= 3 and 1 <= candidate[1] <= 3:
        after, status = candidate, "EXECUTED"
    else:
        after, status = _pos, "REJECTED"
    GRID_TRACE.append((_index, _direction, _pos, after, status))
    _pos = after

PROMPTS: List[PromptSpec] = [
    PromptSpec(
        "p01", "strict_json", "Strict JSON extraction with type validation",
        """Extract the fields below and return a JSON object with exactly these keys:
`coolant_temp_celsius`, `crew_onboard`, `avg_radiation_mSv`.
Use numbers, not strings. Output only the JSON object.

Text:
Station log: ambient pressure 1013.25 hPa. Crew aboard: 9 individuals.
Primary coolant loop peak temperature 847°C at 0338Z.
Average radiation dose over 72h: 4.7 mSv. Fuel cell bank 3 offline.

Required object:
{"coolant_temp_celsius": 847, "crew_onboard": 9, "avg_radiation_mSv": 4.7}""",
        "{", 72, "strict",
    ),
    PromptSpec(
        "p02", "lexical_constraint", "Realistic lexical veto with proportional routing",
        """Write one sentence recommending how to reroute traffic from Hub B to Hubs A and C.
Do not use the standalone words `the` or `is`.

Hub A has 30% spare capacity. Hub C has 15% spare capacity.
Reroute B's load proportionally to spare capacity.
Correct split: A:C = 8:3.

Output one sentence only, with no list and no commentary.""",
        "", 72, "strict",
    ),
    PromptSpec(
        "p03", "insufficiency", "Insufficient data with exact missing-variable list",
        """Determine whether a thermal throttle event will occur after N3 fails.

Facts:
- Nodes are N1, N2, N3, N4.
- N1 runs at 70% load.
- N3 fails and offloads its tasks equally to N2 and N4.
- Thermal throttle occurs above 90% load.

The problem is insufficient. After the supplied prefix, output exactly a numbered list
containing these three missing items, one per line:
1. Task load of N2 before offload
2. Task load of N4 before offload
3. Task load of N3 at failure, or total offloaded load

Do not add a conclusion or explanation.""",
        "INSUFFICIENT DATA:\n", 112, "formal",
    ),
    PromptSpec(
        "p04", "compression", "Three simple sentences without subordination",
        """Describe how a central bank contracts the money supply through open market operations.
Output exactly three simple declarative sentences.
Do not use semicolons, bullets, numbering, dependent-clause markers, or coordinate clauses.
A valid semantic structure is: securities are sold; reserves decline; money supply declines.""",
        "", 96, "strict",
    ),
    PromptSpec(
        "p05", "structured_paths", "Deterministic tree leaf-to-root paths",
        """Given this tree:
Root
├── A
│   ├── A1
│   └── A2
│       └── A2a
├── B
│   ├── B1
│   ├── B2
│   └── B3
└── C
    └── C1
        ├── C1a
        └── C1b

Output exactly seven leaf-to-root paths in this order:
A1, A2a, B1, B2, B3, C1a, C1b.
Format every line as `Leaf -> Parent -> ... -> Root`.
No bullets, numbering, or commentary.""",
        "A1 ->", 160, "structured",
    ),
    PromptSpec(
        "p06", "sequential_trace", "Finite state machine exact trace",
        """States: IDLE, ACTIVE, SUSPENDED, ERROR.
Transitions:
IDLE: START->ACTIVE, FAULT->ERROR, else->IDLE
ACTIVE: PAUSE->SUSPENDED, FAULT->ERROR, STOP->IDLE, else->ACTIVE
SUSPENDED: RESUME->ACTIVE, STOP->IDLE, FAULT->ERROR, else->SUSPENDED
ERROR: RESET->IDLE, else->ERROR

Initial state: IDLE.
Inputs: START, PAUSE, RESUME, FAULT, RESET, START, STOP, FAULT, RESET, START, PAUSE, STOP.

Output exactly twelve lines:
`Step K: Input=X | Prior=Y -> Next=Z`
No commentary.""",
        "Step 1:", 320, "sequential",
    ),
    PromptSpec(
        "p07", "combinatorial", "Topological ordering with bounded output",
        """Tasks: P, Q, R, S, T, U, V.
Dependencies:
P: none
Q: P
R: P
S: Q and R
T: R
U: S and T
V: Q

List the first ten lexicographic valid topological orders, one comma-separated order per line.
Then output exactly `... and 11 more.`
Finally output exactly `Total: 21`.
No commentary.""",
        "", 384, "combinatorial",
    ),
    PromptSpec(
        "p08", "formal_reasoning", "Closed-option fallacy identification",
        """Choose one name from:
[Affirming the consequent, Denying the antecedent, Circular reasoning, Slippery slope]

Argument:
1. All systems with rapid entropy increase show temperature rise.
2. System X shows temperature rise.
3. Therefore, System X is undergoing rapid entropy increase.

After the supplied prefix, write only the selected name.
On the next line, write one sentence explaining why.
No additional text.""",
        "FALLACY: ", 96, "formal",
    ),
    PromptSpec(
        "p09", "code_schema", "Pseudocode-only summation algorithm",
        """Write pseudocode to compute:
S = sum from i=1 to n of k^i / (1 - k^(i+1))
for positive integer n and real k in (0,1).
Round the result to six decimal places.

The opening pseudocode fence is already supplied.
Write only pseudocode, no comments, and close the code fence.""",
        "```pseudocode\n", 176, "code",
    ),
    PromptSpec(
        "p10", "sequential_trace", "Grid movement trace with boundary rejection",
        """Grid 3x3, rows and columns 1..3. Start at (2,2).
NORTH=row-1, SOUTH=row+1, EAST=col+1, WEST=col-1.
Reject moves outside the grid and keep the prior position.

Moves:
NORTH, EAST, EAST, SOUTH, SOUTH, WEST, NORTH, EAST, NORTH, WEST, WEST, SOUTH.

Output exactly twelve lines:
`Move N: DIR | (r,c) -> (r2,c2) | STATUS`
STATUS must be EXECUTED or REJECTED.
No commentary.""",
        "Move 1:", 320, "sequential",
    ),
]

PROMPT_BY_ID = {prompt.id: prompt for prompt in PROMPTS}
PROMPT_SUITE_HASH = stable_hash([asdict(prompt) for prompt in PROMPTS])


def build_prompt(spec: PromptSpec) -> str:
    return (
        "You are completing a machine-scored answer channel.\n"
        "Do not reveal analysis, scratch work, planning, or chain-of-thought.\n"
        "Do not repeat the task. Continue directly from the supplied answer prefix.\n"
        "The continuation will be scored only as the final answer.\n\n"
        f"TASK:\n{spec.task}\n\n"
        "ANSWER CHANNEL:\n"
        f"{spec.answer_prefill}"
    )


# =====================================================================
# Validators and completion detectors
# =====================================================================

def nonempty_lines(text: str) -> List[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def sentence_count(text: str) -> int:
    return len([
        part for part in re.split(r"(?<=[.!?])\s+", text.strip())
        if part.strip()
    ])


def reasoning_leakage(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "we need", "let's", "i need", "to solve", "first,", "analysis:",
        "reasoning:", "<think>", "step-by-step", "i will",
    )
    return any(marker in lowered for marker in markers)


def validate_answer(prompt_id: str, answer: str) -> Dict[str, Any]:
    answer = answer.strip()
    details: Dict[str, Any] = {}
    contract = False
    semantic = 0.0

    if prompt_id == "p01":
        try:
            obj = json.loads(answer)
            contract = (
                list(obj.keys()) == [
                    "coolant_temp_celsius",
                    "crew_onboard",
                    "avg_radiation_mSv",
                ]
                and type(obj["crew_onboard"]) is int
                and isinstance(obj["coolant_temp_celsius"], (int, float))
                and isinstance(obj["avg_radiation_mSv"], (int, float))
            )
            correct = (
                obj.get("coolant_temp_celsius") == 847
                and obj.get("crew_onboard") == 9
                and abs(float(obj.get("avg_radiation_mSv", -999)) - 4.7) < 1e-9
            )
            semantic = 1.0 if correct else sum([
                obj.get("coolant_temp_celsius") == 847,
                obj.get("crew_onboard") == 9,
                abs(float(obj.get("avg_radiation_mSv", -999)) - 4.7) < 1e-9,
            ]) / 3.0
            contract = contract and correct
        except Exception as exc:
            details["parse_error"] = repr(exc)

    elif prompt_id == "p02":
        banned = re.findall(r"\b(?:the|is)\b", answer, flags=re.I)
        one_sentence = sentence_count(answer) == 1
        no_list = not bool(re.search(r"(^|\n)\s*(?:[-*•]|\d+[.)])\s+", answer))
        contract = not banned and one_sentence and no_list
        split = bool(
            re.search(r"\b8\s*[:/]\s*3\b", answer)
            or (
                (
                    re.search(r"\b8\b", answer)
                    or re.search(r"\beight\b", answer, flags=re.I)
                )
                and (
                    re.search(r"\b3\b", answer)
                    or re.search(r"\bthree\b", answer, flags=re.I)
                )
                and "hub a" in answer.lower()
                and "hub c" in answer.lower()
            )
            or (
                re.search(r"72(?:\.7+)?\s*%", answer)
                and re.search(r"27(?:\.2+)?\s*%", answer)
            )
        )
        semantic = 1.0 if split else 0.0
        contract = contract and split
        details["banned_words"] = banned

    elif prompt_id == "p03":
        lines = nonempty_lines(answer)
        prefix_ok = answer.startswith("INSUFFICIENT DATA:")
        numbered = lines[1:] if prefix_ok and lines else []
        exact_three = len(numbered) == 3 and all(
            re.match(rf"^{index}[.)]\s+", line)
            for index, line in enumerate(numbered, 1)
        )
        low = answer.lower()
        coverage = sum([
            "n2" in low and ("load" in low or "task" in low),
            "n4" in low and ("load" in low or "task" in low),
            "n3" in low and ("load" in low or "offload" in low),
        ])
        semantic = coverage / 3.0
        contract = prefix_ok and exact_three and coverage == 3

    elif prompt_id == "p04":
        count = sentence_count(answer)
        banned = re.findall(
            r"\b(?:which|that|because|although|when|while|if|and|or|but)\b",
            answer,
            flags=re.I,
        )
        no_semicolon = ";" not in answer
        no_list = not bool(re.search(r"(^|\n)\s*(?:[-*•]|\d+[.)])\s+", answer))
        low = answer.lower()
        concepts = sum([
            "sell" in low and ("security" in low or "securities" in low),
            "reserve" in low and any(word in low for word in ("fall", "decline", "decrease", "contract")),
            "money supply" in low and any(word in low for word in ("fall", "decline", "decrease", "contract")),
        ])
        semantic = concepts / 3.0
        contract = count == 3 and not banned and no_semicolon and no_list and concepts == 3
        details.update({"sentence_count": count, "banned_markers": banned})

    elif prompt_id == "p05":
        expected = [
            "A1 -> A -> Root",
            "A2a -> A2 -> A -> Root",
            "B1 -> B -> Root",
            "B2 -> B -> Root",
            "B3 -> B -> Root",
            "C1a -> C1 -> C -> Root",
            "C1b -> C1 -> C -> Root",
        ]
        lines = nonempty_lines(answer)
        matches = sum(
            line.replace("→", "->") == target
            for line, target in itertools.zip_longest(lines, expected, fillvalue="")
        )
        semantic = matches / len(expected)
        contract = lines == expected

    elif prompt_id == "p06":
        pattern = re.compile(
            r"^Step\s+(\d+):\s*Input=([A-Z]+)\s*\|\s*Prior=([A-Z]+)\s*->\s*Next=([A-Z]+)$"
        )
        parsed = []
        for line in nonempty_lines(answer):
            match = pattern.match(line)
            if match:
                parsed.append((
                    int(match.group(1)),
                    match.group(2),
                    match.group(3),
                    match.group(4),
                ))
        correct_prefix = 0
        for observed, expected in zip(parsed, FSM_TRACE):
            if observed == expected:
                correct_prefix += 1
            else:
                break
        semantic = correct_prefix / len(FSM_TRACE)
        contract = parsed == FSM_TRACE and len(nonempty_lines(answer)) == 12

    elif prompt_id == "p07":
        lines = nonempty_lines(answer)
        order_lines = lines[:10]
        parsed_orders = [
            tuple(part.strip() for part in line.split(","))
            for line in order_lines
        ]
        correct_orders = sum(
            observed == expected
            for observed, expected in itertools.zip_longest(
                parsed_orders, TOPO_FIRST10, fillvalue=tuple()
            )
        )
        more_ok = len(lines) >= 11 and lines[10] == "... and 11 more."
        total_ok = len(lines) >= 12 and lines[11] == "Total: 21"
        semantic = (correct_orders + int(more_ok) + int(total_ok)) / 12.0
        contract = (
            len(lines) == 12
            and correct_orders == 10
            and more_ok
            and total_ok
        )

    elif prompt_id == "p08":
        lines = nonempty_lines(answer)
        first_ok = (
            len(lines) >= 1
            and lines[0].lower() == "fallacy: affirming the consequent"
        )
        explanation_ok = (
            len(lines) == 2
            and "temperature rise" in lines[1].lower()
            and (
                "does not" in lines[1].lower()
                or "not imply" in lines[1].lower()
                or "could have" in lines[1].lower()
            )
        )
        semantic = (int(first_ok) + int(explanation_ok)) / 2.0
        contract = first_ok and explanation_ok

    elif prompt_id == "p09":
        code_match = re.fullmatch(
            r"```pseudocode\s*\n(.*?)\n```",
            answer,
            flags=re.S | re.I,
        )
        contract = code_match is not None
        body = code_match.group(1) if code_match else answer
        low = body.lower()
        concepts = sum([
            bool(re.search(r"\bfor\b|\bwhile\b", low)),
            "1" in low and "n" in low,
            "k" in low and ("^" in body or "power" in low),
            "/" in body or "divide" in low,
            "round" in low and "6" in body,
        ])
        semantic = concepts / 5.0
        contract = contract and concepts == 5 and "#" not in body and "//" not in body

    elif prompt_id == "p10":
        pattern = re.compile(
            r"^Move\s+(\d+):\s*([A-Z]+)\s*\|\s*"
            r"\((\d+),(\d+)\)\s*->\s*\((\d+),(\d+)\)\s*\|\s*"
            r"(EXECUTED|REJECTED)$"
        )
        parsed = []
        for line in nonempty_lines(answer):
            match = pattern.match(line)
            if match:
                parsed.append((
                    int(match.group(1)),
                    match.group(2),
                    (int(match.group(3)), int(match.group(4))),
                    (int(match.group(5)), int(match.group(6))),
                    match.group(7),
                ))
        correct_prefix = 0
        for observed, expected in zip(parsed, GRID_TRACE):
            if observed == expected:
                correct_prefix += 1
            else:
                break
        semantic = correct_prefix / len(GRID_TRACE)
        contract = parsed == GRID_TRACE and len(nonempty_lines(answer)) == 12

    else:
        raise KeyError(prompt_id)

    return {
        "contract_pass": bool(contract),
        "semantic_score": float(semantic),
        "reasoning_leakage": reasoning_leakage(answer),
        "details": details,
    }


def answer_is_complete(prompt_id: str, answer: str) -> bool:
    text = answer.strip()
    lines = nonempty_lines(text)

    if prompt_id == "p01":
        if not text.endswith("}"):
            return False
        try:
            json.loads(text)
            return True
        except Exception:
            return False
    if prompt_id == "p02":
        return sentence_count(text) >= 1 and text.endswith((".", "!", "?"))
    if prompt_id == "p03":
        return len(lines) >= 4 and all(
            re.match(rf"^{index}[.)]\s+", lines[index])
            for index in range(1, 4)
        )
    if prompt_id == "p04":
        return sentence_count(text) >= 3
    if prompt_id == "p05":
        return len(lines) >= 7 and lines[-1].endswith("Root")
    if prompt_id == "p06":
        return any(line.startswith("Step 12:") for line in lines)
    if prompt_id == "p07":
        return any(line == "Total: 21" for line in lines)
    if prompt_id == "p08":
        return len(lines) >= 2 and lines[1].endswith((".", "!", "?"))
    if prompt_id == "p09":
        return text.count("```") >= 2 and text.endswith("```")
    if prompt_id == "p10":
        return any(line.startswith("Move 12:") for line in lines)
    return False


class ContractStoppingCriteria(StoppingCriteria):
    def __init__(
        self,
        tokenizer,
        prompt_length: int,
        prompt_id: str,
        answer_prefill: str,
    ) -> None:
        self.tokenizer = tokenizer
        self.prompt_length = prompt_length
        self.prompt_id = prompt_id
        self.answer_prefill = answer_prefill

    def __call__(self, input_ids, scores, **kwargs) -> bool:
        generated = input_ids[0, self.prompt_length:].detach().cpu().tolist()
        continuation = self.tokenizer.decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        return answer_is_complete(
            self.prompt_id,
            self.answer_prefill + continuation,
        )


# =====================================================================
# TALM/TALON configuration and common projection
# =====================================================================

TALON_METHODS = {
    "talon_mass_right": TALONOperatorConfig(
        strength=0.70,
        temperature=1.0,
        mass_threshold=0.92,
        selection_mode="mass",
        side_policy="right",
        preserve_top1=False,
        debug=True,
    ),
    "talon_mass_left": TALONOperatorConfig(
        strength=0.70,
        temperature=1.0,
        mass_threshold=0.92,
        selection_mode="mass",
        side_policy="left",
        preserve_top1=False,
        debug=True,
    ),
}
TALM_METHODS = {
    "talm_mass_right_soft": TALMOperatorConfig(
        strength=0.70,
        temperature=1.0,
        tail_fraction=0.08,
        mass_tail_fraction=0.025,
        left_weight=0.20,
        right_weight=0.80,
        left_boost=0.08,
        right_boost=0.28,
        selection_mode="mass",
        side_policy="right",
        preserve_top1=False,
        debug=True,
    ),
    "talm_mass_left_soft": TALMOperatorConfig(
        strength=0.70,
        temperature=1.0,
        tail_fraction=0.08,
        mass_tail_fraction=0.025,
        left_weight=0.80,
        right_weight=0.20,
        left_boost=0.08,
        right_boost=0.28,
        selection_mode="mass",
        side_policy="left",
        preserve_top1=False,
        debug=True,
    ),
}
STATIC_CONFIGS = {**TALM_METHODS, **TALON_METHODS}
METHOD_CONFIG_HASH = stable_hash({
    "talon": {name: asdict(config) for name, config in TALON_METHODS.items()},
    "talm": {name: asdict(config) for name, config in TALM_METHODS.items()},
    "common_projection": True,
    "single_temperature": True,
    "methods": METHOD_ORDER,
})


def project_top1(base_scores: torch.Tensor, transformed: torch.Tensor) -> torch.Tensor:
    base = base_scores.float()
    output = transformed.float().clone()
    top = torch.argmax(base, dim=-1, keepdim=True)
    other = output.clone()
    other.scatter_(1, top, -torch.inf)
    required = torch.max(other, dim=-1, keepdim=True).values + 1e-5
    current = output.gather(1, top)
    output.scatter_(1, top, torch.maximum(current, required))
    return output.to(dtype=transformed.dtype)


def raw_processor_for_action(action: str):
    if action in TALON_METHODS:
        return TALONLogitProcessor(TALON_METHODS[action])
    if action in TALM_METHODS:
        return TALMLogitProcessor(TALM_METHODS[action])
    if action == "baseline":
        return None
    raise KeyError(action)


class ProjectedOperatorProcessor(LogitsProcessor):
    """Run a canonical operator without its internal projection, then apply one common projection."""

    def __init__(self, action: str) -> None:
        self.action = action
        self.raw_processor = raw_processor_for_action(action)
        self.calls = 0
        self.pre_projection_flips = 0
        self.post_projection_flips = 0
        self.mask_fraction_sum = 0.0
        self.kl_sum = 0.0

    def __call__(self, input_ids, scores):
        self.calls += 1
        transformed = self.raw_processor(input_ids, scores.clone())
        base_top = torch.argmax(scores, dim=-1)
        transformed_top = torch.argmax(transformed, dim=-1)
        self.pre_projection_flips += int(
            transformed_top.ne(base_top).sum().detach().cpu()
        )
        projected = project_top1(scores, transformed)
        projected_top = torch.argmax(projected, dim=-1)
        self.post_projection_flips += int(
            projected_top.ne(base_top).sum().detach().cpu()
        )
        summary = self.raw_processor.summary()
        self.mask_fraction_sum += float(summary.get("mean_mask_fraction", 0.0))
        self.kl_sum += float(summary.get("mean_kl_mean", 0.0))
        return projected

    def summary(self) -> Dict[str, Any]:
        denominator = max(self.calls, 1)
        raw = self.raw_processor.summary()
        return {
            "selected_action": self.action,
            "calls": self.calls,
            "pre_projection_top1_flips": self.pre_projection_flips,
            "post_projection_top1_flips": self.post_projection_flips,
            "mean_mask_fraction": self.mask_fraction_sum / denominator,
            "mean_kl_mean": self.kl_sum / denominator,
            **{f"raw_{key}": value for key, value in raw.items()},
        }

    def reset_history(self) -> None:
        self.__init__(self.action)


# =====================================================================
# Mechanistic router
# =====================================================================

ROUTER_CONFIG = {
    "practical_delta": 0.06,
    "initial_operator_margin": 0.06,
    "risk_aversion": 0.35,
    "route_every": 8,
    "min_dwell_steps": 16,
    "cooldown_steps": 16,
    "switch_margin": 0.12,
    "switch_confirmations": 2,
    "max_switches": 1,
    "lock_after_fraction": 0.70,
}

PROFILE_PRIORS: Dict[str, Dict[str, float]] = {
    # These priors encode task jurisdiction only. They do not contain any
    # output from the repaired suite and are frozen before execution.
    "strict": {
        "baseline": 0.00,
        "talm_mass_right_soft": 0.07,
        "talm_mass_left_soft": -0.01,
        "talon_mass_right": 0.13,
        "talon_mass_left": -0.04,
    },
    "formal": {
        "baseline": 0.00,
        "talm_mass_right_soft": 0.11,
        "talm_mass_left_soft": 0.02,
        "talon_mass_right": 0.09,
        "talon_mass_left": -0.01,
    },
    "structured": {
        "baseline": 0.00,
        "talm_mass_right_soft": 0.12,
        "talm_mass_left_soft": 0.03,
        "talon_mass_right": 0.06,
        "talon_mass_left": 0.00,
    },
    "sequential": {
        "baseline": 0.00,
        "talm_mass_right_soft": 0.07,
        "talm_mass_left_soft": -0.01,
        "talon_mass_right": 0.14,
        "talon_mass_left": -0.03,
    },
    "combinatorial": {
        "baseline": 0.00,
        "talm_mass_right_soft": 0.14,
        "talm_mass_left_soft": 0.05,
        "talon_mass_right": 0.05,
        "talon_mass_left": 0.06,
    },
    "code": {
        "baseline": 0.00,
        "talm_mass_right_soft": 0.06,
        "talm_mass_left_soft": -0.02,
        "talon_mass_right": 0.15,
        "talon_mass_left": -0.03,
    },
}

# Each operator is calibrated against its own mechanistic regime. Comparing
# every branch with one common TV target was the source of the v0.3 collapse.
ACTION_SIGNATURES = {
    "talm_mass_right_soft": {
        "tv": 0.010,
        "tv_scale": 0.012,
        "delta_h": -0.007,
        "delta_h_scale": 0.020,
        "minimum_activity": 0.002,
    },
    "talm_mass_left_soft": {
        "tv": 0.003,
        "tv_scale": 0.006,
        "delta_h": 0.002,
        "delta_h_scale": 0.015,
        "minimum_activity": 0.0005,
    },
    "talon_mass_right": {
        "tv": 0.190,
        "tv_scale": 0.080,
        "delta_h": -0.220,
        "delta_h_scale": 0.120,
        "minimum_activity": 0.030,
    },
    "talon_mass_left": {
        "tv": 0.190,
        "tv_scale": 0.080,
        "delta_h": 0.020,
        "delta_h_scale": 0.080,
        "minimum_activity": 0.030,
    },
}

ROUTER_POLICY_HASH = stable_hash({
    "version": ROUTER_POLICY_VERSION,
    "config": ROUTER_CONFIG,
    "priors": PROFILE_PRIORS,
    "action_signatures": ACTION_SIGNATURES,
})


def fingerprint(base_scores: torch.Tensor, transformed: torch.Tensor) -> Dict[str, float]:
    base = base_scores.float()
    altered = transformed.float()
    p0 = torch.softmax(base, dim=-1)
    p1 = torch.softmax(altered, dim=-1)
    kl = torch.sum(
        p0 * (
            torch.log(torch.clamp(p0, min=1e-12))
            - torch.log(torch.clamp(p1, min=1e-12))
        ),
        dim=-1,
    )
    tv = 0.5 * torch.sum(torch.abs(p0 - p1), dim=-1)
    h0 = -torch.sum(p0 * torch.log(torch.clamp(p0, min=1e-12)), dim=-1)
    h1 = -torch.sum(p1 * torch.log(torch.clamp(p1, min=1e-12)), dim=-1)
    order0 = torch.argsort(base, dim=-1, descending=True)
    order1 = torch.argsort(altered, dim=-1, descending=True)
    k = min(10, base.shape[-1])
    overlap = len(
        set(order0[0, :k].detach().cpu().tolist())
        & set(order1[0, :k].detach().cpu().tolist())
    ) / float(k)
    return {
        "kl": float(kl.mean().detach().cpu()),
        "tv": float(tv.mean().detach().cpu()),
        "delta_entropy": float((h1 - h0).mean().detach().cpu()),
        "mask_fraction": float(
            (torch.abs(altered - base) > 1e-12).float().mean().detach().cpu()
        ),
        "top1_preflip": float(
            torch.argmax(base, dim=-1)
            .ne(torch.argmax(altered, dim=-1))
            .float().mean()
            .detach().cpu()
        ),
        "top10_overlap": float(overlap),
        "base_entropy_normalized": float(
            (h0 / math.log(max(base.shape[-1], 2))).mean().detach().cpu()
        ),
    }


def apply_action_once(action: str, input_ids: torch.Tensor, scores: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
    if action == "baseline":
        return scores.clone(), {
            "kl": 0.0,
            "tv": 0.0,
            "delta_entropy": 0.0,
            "mask_fraction": 0.0,
            "top1_preflip": 0.0,
            "top10_overlap": 1.0,
            "base_entropy_normalized": float(
                entropy_np(
                    softmax_np(scores[0].detach().float().cpu().numpy())
                ) / math.log(max(scores.shape[-1], 2))
            ),
        }
    processor = raw_processor_for_action(action)
    transformed = processor(input_ids, scores.clone())
    return transformed, fingerprint(scores, transformed)


def score_action(action: str, profile: str, fp: Dict[str, float]) -> float:
    prior = PROFILE_PRIORS[profile][action]
    if action == "baseline":
        return 0.34 + prior

    signature = ACTION_SIGNATURES[action]
    tv_closeness = math.exp(
        -abs(fp["tv"] - signature["tv"]) / signature["tv_scale"]
    )
    entropy_closeness = math.exp(
        -abs(fp["delta_entropy"] - signature["delta_h"])
        / signature["delta_h_scale"]
    )
    activity = min(
        fp["mask_fraction"] / max(signature["minimum_activity"] * 8.0, 0.02),
        1.0,
    )
    fidelity = fp["top10_overlap"]
    preflip_risk = fp["top1_preflip"]

    inactivity_penalty = (
        0.40
        if fp["tv"] < signature["minimum_activity"]
        else 0.0
    )
    signature_deviation = (
        abs(fp["tv"] - signature["tv"]) / signature["tv_scale"]
    )
    out_of_regime_penalty = max(0.0, signature_deviation - 3.0) * 0.10

    return (
        0.12
        + prior
        + 0.22 * tv_closeness
        + 0.16 * entropy_closeness
        + 0.10 * activity
        + 0.12 * fidelity
        - ROUTER_CONFIG["risk_aversion"] * preflip_risk
        - inactivity_penalty
        - out_of_regime_penalty
    )


def route_snapshot(
    prompt_spec: PromptSpec,
    input_ids: torch.Tensor,
    base_scores: torch.Tensor,
) -> Dict[str, Any]:
    profile = prompt_spec.router_profile
    scores: Dict[str, float] = {}
    fingerprints: Dict[str, Dict[str, float]] = {}
    for action in ROUTER_CANDIDATES:
        transformed, fp = apply_action_once(action, input_ids, base_scores)
        fingerprints[action] = fp
        scores[action] = score_action(action, profile, fp)
        del transformed

    chosen = max(scores, key=scores.get)
    baseline_score = scores["baseline"]
    margin = scores[chosen] - baseline_score
    abstained = chosen != "baseline" and margin < ROUTER_CONFIG["practical_delta"]
    if abstained:
        chosen = "baseline"

    return {
        "profile": profile,
        "chosen_action": chosen,
        "abstained": abstained,
        "margin_vs_baseline": float(margin),
        "scores": scores,
        "fingerprints": fingerprints,
    }


class CFLDRPlusInlineProcessor(LogitsProcessor):
    def __init__(self, prompt_spec: PromptSpec) -> None:
        self.prompt_spec = prompt_spec
        self.current_action = "baseline"
        self.step_index = 0
        self.steps_in_action = 0
        self.cooldown_remaining = 0
        self.switches = 0
        self.pending_action: Optional[str] = None
        self.pending_confirmations = 0
        self.route_trace: List[Dict[str, Any]] = []
        self.action_counts: Dict[str, int] = {}
        self.pre_projection_flips = 0
        self.post_projection_flips = 0

    def __call__(self, input_ids, scores):
        step = self.step_index
        previous = self.current_action
        lock_late = (
            step >= int(self.prompt_spec.max_new_tokens * ROUTER_CONFIG["lock_after_fraction"])
        )
        route_due = (
            step == 0
            or (
                not lock_late
                and step % ROUTER_CONFIG["route_every"] == 0
                and self.steps_in_action >= ROUTER_CONFIG["min_dwell_steps"]
                and self.cooldown_remaining == 0
                and self.switches < ROUTER_CONFIG["max_switches"]
            )
        )

        reason = "hold"
        snapshot = None
        selected = previous

        if route_due:
            snapshot = route_snapshot(self.prompt_spec, input_ids, scores)
            candidate = snapshot["chosen_action"]

            if step == 0:
                selected = candidate
                reason = "initial_route"
                self.pending_action = None
                self.pending_confirmations = 0
            else:
                current_score = snapshot["scores"].get(previous, snapshot["scores"]["baseline"])
                candidate_score = snapshot["scores"].get(candidate, snapshot["scores"]["baseline"])
                has_margin = (
                    candidate != previous
                    and candidate_score > current_score + ROUTER_CONFIG["switch_margin"]
                )
                if has_margin:
                    if self.pending_action == candidate:
                        self.pending_confirmations += 1
                    else:
                        self.pending_action = candidate
                        self.pending_confirmations = 1
                    if self.pending_confirmations >= ROUTER_CONFIG["switch_confirmations"]:
                        selected = candidate
                        self.switches += 1
                        self.steps_in_action = 0
                        self.cooldown_remaining = ROUTER_CONFIG["cooldown_steps"]
                        self.pending_action = None
                        self.pending_confirmations = 0
                        reason = "confirmed_switch"
                    else:
                        reason = "switch_pending_confirmation"
                else:
                    self.pending_action = None
                    self.pending_confirmations = 0
                    reason = "hysteresis_hold"

            self.route_trace.append({
                "step": int(step),
                "previous_action": previous,
                "candidate_action": snapshot["chosen_action"],
                "selected_action": selected,
                "reason": reason,
                "scores": snapshot["scores"],
                "margin_vs_baseline": snapshot["margin_vs_baseline"],
            })

        if selected != previous and step > 0:
            self.steps_in_action = 0
        else:
            self.steps_in_action += 1
            self.cooldown_remaining = max(0, self.cooldown_remaining - 1)

        self.current_action = selected
        self.action_counts[selected] = self.action_counts.get(selected, 0) + 1

        transformed = scores.clone()
        if selected != "baseline":
            raw = raw_processor_for_action(selected)
            transformed = raw(input_ids, scores.clone())

        base_top = torch.argmax(scores, dim=-1)
        transformed_top = torch.argmax(transformed, dim=-1)
        self.pre_projection_flips += int(
            transformed_top.ne(base_top).sum().detach().cpu()
        )
        projected = project_top1(scores, transformed)
        projected_top = torch.argmax(projected, dim=-1)
        self.post_projection_flips += int(
            projected_top.ne(base_top).sum().detach().cpu()
        )

        self.step_index += 1
        return projected

    def summary(self) -> Dict[str, Any]:
        return {
            "selected_action": self.current_action,
            "calls": self.step_index,
            "switch_count": self.switches,
            "action_counts": self.action_counts,
            "route_trace": self.route_trace,
            "pre_projection_top1_flips": self.pre_projection_flips,
            "post_projection_top1_flips": self.post_projection_flips,
        }


# =====================================================================
# Model loading and prompt encoding
# =====================================================================

def load_model_and_tokenizer(model_id: str):
    if not TRANSFORMERS_AVAILABLE:
        raise RuntimeError(
            "transformers is not installed. Run the Kaggle bootstrap cell first."
        )
    if REQUIRE_CUDA and not torch.cuda.is_available():
        raise RuntimeError("CUDA is required. Enable a Kaggle GPU.")

    quantization = BitsAndBytesConfig(
        load_in_4bit=USE_4BIT,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        trust_remote_code=True,
        use_fast=True,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    kwargs = dict(
        pretrained_model_name_or_path=model_id,
        trust_remote_code=True,
        quantization_config=quantization,
        device_map={"": 0},
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    try:
        model = AutoModelForCausalLM.from_pretrained(
            attn_implementation=ATTN_IMPLEMENTATION,
            **kwargs,
        )
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(**kwargs)

    model.eval()
    meta_parameters = [
        name for name, parameter in model.named_parameters()
        if getattr(parameter, "is_meta", False)
    ]
    if meta_parameters:
        raise RuntimeError(
            f"Model contains meta tensors after load: {meta_parameters[:10]}"
        )

    input_device = next(
        parameter.device for parameter in model.parameters()
        if parameter.device.type != "meta"
    )
    return tokenizer, model, input_device


def encode_prompt(tokenizer, spec: PromptSpec, device: torch.device):
    text = build_prompt(spec)
    encoded = tokenizer(
        text,
        return_tensors="pt",
        add_special_tokens=True,
    )
    encoded = {
        key: value.to(device)
        for key, value in encoded.items()
        if torch.is_tensor(value)
    }
    prompt_length = int(encoded["input_ids"].shape[-1])
    return text, encoded, prompt_length


# =====================================================================
# Generation and diagnostics
# =====================================================================

def generation_method_family(method: str) -> str:
    if method in TALM_METHODS:
        return "TALM"
    if method in TALON_METHODS:
        return "TALON"
    if method == "baseline":
        return "baseline"
    if method == "baseline_control":
        return "stochastic_control"
    if method == "cfldr_plus_preroute":
        return "CFLDR_PLUS_PREROUTE"
    if method == "cfldr_plus_inline":
        return "CFLDR_PLUS_INLINE"
    raise KeyError(method)


def generate_one(
    tokenizer,
    model,
    device,
    spec: PromptSpec,
    seed: int,
    method: str,
) -> Dict[str, Any]:
    effective_seed = seed + CONTROL_SEED_OFFSET if method == "baseline_control" else seed
    set_seed(effective_seed)

    prompt_text, inputs, prompt_length = encode_prompt(tokenizer, spec, device)
    method_family = generation_method_family(method)

    processor = None
    preroute = None
    selected_action = None

    if method in STATIC_CONFIGS:
        processor = ProjectedOperatorProcessor(method)
        selected_action = method
    elif method == "cfldr_plus_preroute":
        with torch.inference_mode():
            first = model(**inputs).logits[:, -1, :]
        preroute = route_snapshot(spec, inputs["input_ids"], first)
        selected_action = preroute["chosen_action"]
        if selected_action != "baseline":
            processor = ProjectedOperatorProcessor(selected_action)
        del first
    elif method == "cfldr_plus_inline":
        processor = CFLDRPlusInlineProcessor(spec)
        selected_action = "dynamic"
    elif method not in {"baseline", "baseline_control"}:
        raise KeyError(method)

    logits_processors = (
        LogitsProcessorList([processor])
        if processor is not None
        else None
    )
    stopping = StoppingCriteriaList([
        ContractStoppingCriteria(
            tokenizer,
            prompt_length,
            spec.id,
            spec.answer_prefill,
        )
    ])

    kwargs = {
        "max_new_tokens": spec.max_new_tokens,
        "do_sample": True,
        "temperature": BASE_TEMPERATURE,
        "top_p": BASE_TOP_P,
        "repetition_penalty": REPETITION_PENALTY,
        "no_repeat_ngram_size": NO_REPEAT_NGRAM_SIZE,
        "use_cache": True,
        "renormalize_logits": True,
        "pad_token_id": int(tokenizer.pad_token_id),
        "stopping_criteria": stopping,
    }
    if tokenizer.eos_token_id is not None:
        kwargs["eos_token_id"] = int(tokenizer.eos_token_id)

    started = time.time()
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            logits_processor=logits_processors,
            **kwargs,
        )
    elapsed = time.time() - started

    new_ids = generated[0, prompt_length:].detach().cpu().tolist()
    continuation = tokenizer.decode(
        new_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    answer = (spec.answer_prefill + continuation).strip()
    validation = validate_answer(spec.id, answer)
    completion = answer_is_complete(spec.id, answer)
    diag = processor.summary() if processor is not None else {}

    answer_ids = tokenizer(
        answer,
        add_special_tokens=False,
    )["input_ids"]

    row = {
        "project": f"CFLDR_PLUS_V04_REPAIRED_SEED_{seed}",
        "engine": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "suite_version": SUITE_VERSION,
        "model": MODEL_ID,
        "model_label": MODEL_LABEL,
        "prompt_id": spec.id,
        "task_type": spec.task_type,
        "concept_name": spec.concept_name,
        "router_profile": spec.router_profile,
        "prompt": prompt_text,
        "answer_prefill": spec.answer_prefill,
        "prompt_hash": stable_hash(asdict(spec)),
        "prompt_suite_hash": PROMPT_SUITE_HASH,
        "method_config_hash": METHOD_CONFIG_HASH,
        "router_policy_hash": ROUTER_POLICY_HASH,
        "seed": int(seed),
        "effective_seed": int(effective_seed),
        "method": method,
        "method_family": method_family,
        "selected_action": selected_action,
        "status": "ok",
        "continuation_text": continuation,
        "answer_text": answer,
        "new_token_count": len(new_ids),
        "answer_token_count": len(answer_ids),
        "max_new_tokens": spec.max_new_tokens,
        "hit_max_new_tokens": len(new_ids) >= spec.max_new_tokens,
        "contract_completion_detected": bool(completion),
        "contract_pass": bool(validation["contract_pass"]),
        "semantic_score": float(validation["semantic_score"]),
        "automatic_utility": (
            0.70 * float(validation["contract_pass"])
            + 0.30 * float(validation["semantic_score"])
        ),
        "reasoning_leakage": bool(validation["reasoning_leakage"]),
        "validator_details_json": safe_json(validation["details"]),
        "distinct_1": distinct_n(answer_ids, 1),
        "distinct_2": distinct_n(answer_ids, 2),
        "token_entropy": token_entropy(answer_ids),
        "bigram_repetition_rate": repetition_rate(answer_ids, 2),
        "trigram_repetition_rate": repetition_rate(answer_ids, 3),
        "generation_seconds": elapsed,
        "generation_temperature": BASE_TEMPERATURE,
        "generation_top_p": BASE_TOP_P,
        "external_sampler_connected": False,
        "z_ph_post_hoc_only": True,
        "preroute_snapshot_json": safe_json(preroute) if preroute else None,
    }
    for key, value in diag.items():
        if isinstance(value, (dict, list)):
            row[f"diag_{key}_json"] = safe_json(value)
        else:
            row[f"diag_{key}"] = value

    del generated, inputs
    cuda_cleanup()
    return row


# =====================================================================
# Checkpoint, resume, analysis and Z_PH
# =====================================================================

def row_key(row: Mapping[str, Any]) -> Optional[Tuple[str, int, int, str, str]]:
    try:
        return (
            str(row["prompt_id"]),
            int(row["seed"]),
            int(row["effective_seed"]),
            str(row["method"]),
            str(row["suite_version"]),
        )
    except Exception:
        return None


def load_resume_rows(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    loaded: List[Dict[str, Any]] = []
    for path in paths:
        if not path or not path.exists():
            continue
        if path.suffix.lower() == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    loaded.append(json.loads(line))
        elif path.suffix.lower() == ".csv":
            loaded.extend(pd.read_csv(path).to_dict("records"))
    dedup: Dict[Tuple[str, int, int, str, str], Dict[str, Any]] = {}
    for row in loaded:
        key = row_key(row)
        if key is None:
            continue
        if str(row.get("status", "")).lower() != "ok":
            continue
        dedup[key] = row
    return list(dedup.values())


def checkpoint(
    rows: Sequence[Mapping[str, Any]],
    run_dir: Path,
    project_name: str,
    planned_rows: int,
    reason: str,
    seed: int,
) -> Dict[str, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    jsonl = run_dir / f"{project_name}_checkpoint.jsonl"
    csv_path = run_dir / f"{project_name}_checkpoint.csv"
    manifest_path = run_dir / f"{project_name}_manifest.json"
    sha_path = run_dir / "SHA256SUMS.txt"
    zip_path = run_dir.parent / f"{project_name}_latest_checkpoint_bundle.zip"

    atomic_write_jsonl(jsonl, rows)
    atomic_write_csv(csv_path, rows)

    manifest = {
        "project": project_name,
        "engine": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "suite_version": SUITE_VERSION,
        "model": MODEL_ID,
        "seed": seed,
        "n_rows": len(rows),
        "planned_rows": planned_rows,
        "reason": reason,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prompt_suite_hash": PROMPT_SUITE_HASH,
        "method_config_hash": METHOD_CONFIG_HASH,
        "router_policy_hash": ROUTER_POLICY_HASH,
        "checkpoint_schema_version": "CFLDR_PLUS_REPAIRED_CHECKPOINT_v0.4",
        "external_sampler_connected": False,
        "z_ph_post_hoc_only": True,
        "checkpoint_jsonl_sha256": sha256_file(jsonl),
        "checkpoint_csv_sha256": sha256_file(csv_path),
    }
    atomic_write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2),
    )
    atomic_write_text(
        sha_path,
        "\n".join(
            f"{sha256_file(path)}  {path.name}"
            for path in (jsonl, csv_path, manifest_path)
        ) + "\n",
    )

    temporary_zip = zip_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in (jsonl, csv_path, manifest_path, sha_path):
            archive.write(path, arcname=path.name)
    temporary_zip.replace(zip_path)
    return {
        "jsonl": jsonl,
        "csv": csv_path,
        "manifest": manifest_path,
        "sha256": sha_path,
        "zip": zip_path,
    }


def paired_against_baseline(df: pd.DataFrame) -> pd.DataFrame:
    base = df[df["method"].eq("baseline")].set_index(["prompt_id", "seed"])
    control = df[df["method"].eq("baseline_control")].set_index(["prompt_id", "seed"])
    output = []
    for _, row in df[~df["method"].isin(["baseline", "baseline_control"])].iterrows():
        key = (row["prompt_id"], row["seed"])
        if key not in base.index or key not in control.index:
            continue
        b = base.loc[key]
        c = control.loc[key]
        distance = sequence_distance(str(b["answer_text"]), str(row["answer_text"]))
        control_distance = sequence_distance(str(b["answer_text"]), str(c["answer_text"]))
        output.append({
            "prompt_id": row["prompt_id"],
            "seed": row["seed"],
            "method": row["method"],
            "method_family": row["method_family"],
            "sequence_distance": distance,
            "control_distance": control_distance,
            "distance_ratio_vs_control": (
                distance / control_distance
                if control_distance > 1e-12 else np.nan
            ),
            "jaccard_distance": jaccard_distance(
                str(b["answer_text"]), str(row["answer_text"])
            ),
            "contract_delta": float(row["contract_pass"]) - float(b["contract_pass"]),
            "semantic_delta": float(row["semantic_score"]) - float(b["semantic_score"]),
            "automatic_utility_delta": float(row["automatic_utility"]) - float(b["automatic_utility"]),
            "distinct_2_delta": float(row["distinct_2"]) - float(b["distinct_2"]),
            "token_entropy_delta": float(row["token_entropy"]) - float(b["token_entropy"]),
        })
    return pd.DataFrame(output)


def automatic_oracle(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    static_methods = {
        "baseline",
        "talm_mass_right_soft",
        "talm_mass_left_soft",
        "talon_mass_right",
        "talon_mass_left",
    }
    records = []
    for (prompt_id, seed), group in df.groupby(["prompt_id", "seed"]):
        static = group[group["method"].isin(static_methods)]
        if static.empty:
            continue
        oracle_value = float(static["automatic_utility"].max())
        oracle_actions = static[
            np.isclose(static["automatic_utility"], oracle_value)
        ]["method"].tolist()
        for router_method in ("cfldr_plus_preroute", "cfldr_plus_inline"):
            router_row = group[group["method"].eq(router_method)]
            if router_row.empty:
                continue
            rr = router_row.iloc[0]
            records.append({
                "prompt_id": prompt_id,
                "seed": seed,
                "router_method": router_method,
                "router_action": rr.get("selected_action"),
                "router_utility": float(rr["automatic_utility"]),
                "oracle_utility": oracle_value,
                "oracle_actions": "|".join(oracle_actions),
                "regret": oracle_value - float(rr["automatic_utility"]),
                "oracle_hit": bool(
                    np.isclose(float(rr["automatic_utility"]), oracle_value)
                ),
            })
    detail = pd.DataFrame(records)
    if detail.empty:
        return detail, pd.DataFrame()
    summary = (
        detail.groupby("router_method")
        .agg(
            n=("prompt_id", "count"),
            mean_router_utility=("router_utility", "mean"),
            mean_oracle_utility=("oracle_utility", "mean"),
            mean_regret=("regret", "mean"),
            oracle_hit_rate=("oracle_hit", "mean"),
        )
        .reset_index()
    )
    return detail, summary


def create_blind_pairs(df: pd.DataFrame, output_dir: Path, seed: int) -> Tuple[Path, Path]:
    rng = random.Random(seed + 777777)
    pairs = []
    key = []
    for (prompt_id, original_seed), group in df.groupby(["prompt_id", "seed"]):
        by_method = {row["method"]: row for _, row in group.iterrows()}
        for router_method in ("cfldr_plus_preroute", "cfldr_plus_inline"):
            if router_method not in by_method:
                continue
            for comparator in (
                "baseline",
                "talm_mass_right_soft",
                "talm_mass_left_soft",
                "talon_mass_right",
                "talon_mass_left",
            ):
                if comparator not in by_method:
                    continue
                pair_id = stable_hash(
                    [prompt_id, original_seed, router_method, comparator]
                )[:16]
                left_first = rng.random() < 0.5
                a_method = router_method if left_first else comparator
                b_method = comparator if left_first else router_method
                pairs.append({
                    "pair_id": pair_id,
                    "prompt_id": prompt_id,
                    "seed": original_seed,
                    "candidate_A": by_method[a_method]["answer_text"],
                    "candidate_B": by_method[b_method]["answer_text"],
                    "winner": "",
                    "confidence": "",
                    "format_A": "",
                    "format_B": "",
                    "content_A": "",
                    "content_B": "",
                    "notes": "",
                })
                key.append({
                    "pair_id": pair_id,
                    "method_A": a_method,
                    "method_B": b_method,
                })
    pairs_path = output_dir / "blind_human_eval_pairs.csv"
    key_path = output_dir / "blind_human_eval_hidden_key.csv"
    atomic_write_csv(pairs_path, pairs)
    atomic_write_csv(key_path, key)
    return pairs_path, key_path


def run_analysis(rows: Sequence[Mapping[str, Any]], run_dir: Path, seed: int) -> Dict[str, Path]:
    df = pd.DataFrame(rows)
    ok = df[df["status"].astype(str).str.lower().eq("ok")].copy()

    method_summary = (
        ok.groupby(["method_family", "method"], dropna=False)
        .agg(
            n=("prompt_id", "count"),
            contract_pass_rate=("contract_pass", "mean"),
            semantic_score=("semantic_score", "mean"),
            automatic_utility=("automatic_utility", "mean"),
            completion_rate=("contract_completion_detected", "mean"),
            cap_rate=("hit_max_new_tokens", "mean"),
            reasoning_leakage_rate=("reasoning_leakage", "mean"),
            mean_new_tokens=("new_token_count", "mean"),
            mean_distinct_2=("distinct_2", "mean"),
            mean_token_entropy=("token_entropy", "mean"),
        )
        .reset_index()
    )
    method_summary_path = run_dir / "method_summary.csv"
    method_summary.to_csv(method_summary_path, index=False, encoding="utf-8-sig")

    prompt_method = (
        ok.groupby(["prompt_id", "method"], dropna=False)
        .agg(
            contract_pass=("contract_pass", "mean"),
            semantic_score=("semantic_score", "mean"),
            automatic_utility=("automatic_utility", "mean"),
            completion=("contract_completion_detected", "mean"),
            cap_rate=("hit_max_new_tokens", "mean"),
        )
        .reset_index()
    )
    prompt_method_path = run_dir / "prompt_method_summary.csv"
    prompt_method.to_csv(prompt_method_path, index=False, encoding="utf-8-sig")

    paired = paired_against_baseline(ok)
    paired_path = run_dir / "z_ph_paired_against_baseline.csv"
    paired.to_csv(paired_path, index=False, encoding="utf-8-sig")

    oracle_detail, oracle_summary = automatic_oracle(ok)
    oracle_detail_path = run_dir / "automatic_oracle_detail.csv"
    oracle_summary_path = run_dir / "automatic_oracle_summary.csv"
    oracle_detail.to_csv(oracle_detail_path, index=False, encoding="utf-8-sig")
    oracle_summary.to_csv(oracle_summary_path, index=False, encoding="utf-8-sig")

    router_rows = ok[
        ok["method"].isin(["cfldr_plus_preroute", "cfldr_plus_inline"])
    ].copy()
    router_summary = []
    for _, row in router_rows.iterrows():
        trace = []
        counts = {}
        if row.get("diag_route_trace_json"):
            try:
                trace = json.loads(row["diag_route_trace_json"])
            except Exception:
                pass
        if row.get("diag_action_counts_json"):
            try:
                counts = json.loads(row["diag_action_counts_json"])
            except Exception:
                pass
        router_summary.append({
            "prompt_id": row["prompt_id"],
            "seed": row["seed"],
            "method": row["method"],
            "selected_action": row.get("selected_action"),
            "final_action": row.get("diag_selected_action"),
            "switch_count": row.get("diag_switch_count", 0),
            "pre_projection_flips": row.get("diag_pre_projection_top1_flips", 0),
            "post_projection_flips": row.get("diag_post_projection_top1_flips", 0),
            "route_events": len(trace),
            "action_counts_json": safe_json(counts),
            "route_trace_json": safe_json(trace),
            "contract_pass": row["contract_pass"],
            "semantic_score": row["semantic_score"],
        })
    router_summary_path = run_dir / "router_trace_summary.csv"
    atomic_write_csv(router_summary_path, router_summary)

    pairs_path, key_path = create_blind_pairs(ok, run_dir, seed)

    report_lines = [
        "# CFLDR Plus v0.4 repaired — automatic report",
        "",
        f"- Rows: {len(ok)}",
        f"- Contract pass rate: {ok['contract_pass'].mean():.3f}",
        f"- Completion rate: {ok['contract_completion_detected'].mean():.3f}",
        f"- Cap rate: {ok['hit_max_new_tokens'].mean():.3f}",
        f"- Reasoning leakage rate: {ok['reasoning_leakage'].mean():.3f}",
        "",
        "## Method summary",
        "",
        method_summary.to_markdown(index=False),
        "",
        "## Automatic oracle",
        "",
        (
            oracle_summary.to_markdown(index=False)
            if not oracle_summary.empty
            else "Oracle unavailable."
        ),
        "",
        "Automatic utility is a validator proxy, not Human Eval.",
        "Z_PH is post hoc only and never participates in routing.",
    ]
    report_path = run_dir / "automatic_report.md"
    atomic_write_text(report_path, "\n".join(report_lines))

    return {
        "method_summary": method_summary_path,
        "prompt_method_summary": prompt_method_path,
        "z_ph": paired_path,
        "oracle_detail": oracle_detail_path,
        "oracle_summary": oracle_summary_path,
        "router_summary": router_summary_path,
        "blind_pairs": pairs_path,
        "blind_key": key_path,
        "report": report_path,
    }


# =====================================================================
# Self-tests
# =====================================================================

def exact_answers() -> Dict[str, str]:
    return {
        "p01": '{"coolant_temp_celsius": 847, "crew_onboard": 9, "avg_radiation_mSv": 4.7}',
        "p02": "Route eight shares toward Hub A for every three shares toward Hub C.",
        "p03": (
            "INSUFFICIENT DATA:\n"
            "1. Task load of N2 before offload\n"
            "2. Task load of N4 before offload\n"
            "3. Task load of N3 at failure, or total offloaded load"
        ),
        "p04": (
            "The central bank sells securities. "
            "Commercial bank reserves decline. "
            "The money supply contracts."
        ),
        "p05": "\n".join([
            "A1 -> A -> Root",
            "A2a -> A2 -> A -> Root",
            "B1 -> B -> Root",
            "B2 -> B -> Root",
            "B3 -> B -> Root",
            "C1a -> C1 -> C -> Root",
            "C1b -> C1 -> C -> Root",
        ]),
        "p06": "\n".join(
            f"Step {i}: Input={inp} | Prior={prior} -> Next={nxt}"
            for i, inp, prior, nxt in FSM_TRACE
        ),
        "p07": "\n".join([
            ",".join(order) for order in TOPO_FIRST10
        ] + ["... and 11 more.", "Total: 21"]),
        "p08": (
            "FALLACY: Affirming the consequent\n"
            "Temperature rise does not imply rapid entropy increase because other causes can produce it."
        ),
        "p09": (
            "```pseudocode\n"
            "S <- 0\n"
            "FOR i <- 1 TO n\n"
            "    S <- S + k^i / (1 - k^(i + 1))\n"
            "END FOR\n"
            "RETURN ROUND(S, 6)\n"
            "```"
        ),
        "p10": "\n".join(
            f"Move {i}: {direction} | ({before[0]},{before[1]}) -> "
            f"({after[0]},{after[1]}) | {status}"
            for i, direction, before, after, status in GRID_TRACE
        ),
    }


def self_test() -> None:
    answers = exact_answers()
    for prompt_id, answer in answers.items():
        result = validate_answer(prompt_id, answer)
        assert result["contract_pass"], (prompt_id, result)
        assert abs(result["semantic_score"] - 1.0) < 1e-12
        assert answer_is_complete(prompt_id, answer)

    for prompt in PROMPTS:
        built = build_prompt(prompt)
        assert built.endswith(prompt.answer_prefill)
        assert prompt.max_new_tokens > 0

    # Projection test with a forced argmax flip.
    base = torch.tensor([[3.0, 2.0, 1.0]])
    altered = torch.tensor([[1.0, 4.0, 0.0]])
    projected = project_top1(base, altered)
    assert int(torch.argmax(projected, dim=-1)) == 0

    # Atomic checkpoint test.
    import tempfile
    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        rows = [{
            "prompt_id": "p01",
            "seed": 14,
            "effective_seed": 14,
            "method": "baseline",
            "suite_version": SUITE_VERSION,
            "status": "ok",
        }]
        paths = checkpoint(
            rows,
            temp / "run",
            "smoke",
            80,
            "self_test",
            14,
        )
        assert all(path.exists() for path in paths.values())
        loaded = load_resume_rows([paths["jsonl"], paths["csv"]])
        assert len(loaded) == 1

    # Router must not be a fixed family prior: synthetic snapshots should
    # be able to select baseline or either family.
    assert set(ROUTER_CANDIDATES) == {
        "baseline",
        "talm_mass_right_soft",
        "talm_mass_left_soft",
        "talon_mass_right",
        "talon_mass_left",
    }

    print("SELF-TESTS PASSED")


# =====================================================================
# Main execution
# =====================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=14)
    parser.add_argument("--output-root", type=Path, default=Path("/kaggle/working"))
    parser.add_argument("--resume-jsonl", type=Path)
    parser.add_argument("--resume-csv", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    seed = int(args.seed)
    project_name = (
        f"CFLDR_PLUS_Qwen35_4B_BASE_REPAIRED_V04_"
        f"SEED_{seed}_4BIT"
    )
    run_dir = args.output_root / project_name
    run_dir.mkdir(parents=True, exist_ok=True)

    tokenizer, model, device = load_model_and_tokenizer(MODEL_ID)

    # Mandatory real model smoke test.
    smoke_spec = PromptSpec(
        "smoke", "smoke", "smoke",
        "Output only OK.", "", 8, "strict"
    )
    smoke_text = "Output only OK.\nANSWER CHANNEL:\n"
    smoke_inputs = tokenizer(
        smoke_text,
        return_tensors="pt",
        add_special_tokens=True,
    )
    smoke_inputs = {
        key: value.to(device)
        for key, value in smoke_inputs.items()
        if torch.is_tensor(value)
    }
    with torch.inference_mode():
        smoke_output = model.generate(
            **smoke_inputs,
            max_new_tokens=8,
            do_sample=False,
            pad_token_id=int(tokenizer.pad_token_id),
        )
    if smoke_output.shape[-1] <= smoke_inputs["input_ids"].shape[-1]:
        raise RuntimeError("Real model smoke test produced no tokens.")
    del smoke_output, smoke_inputs
    cuda_cleanup()

    resume_paths = [
        path for path in (args.resume_jsonl, args.resume_csv)
        if path is not None
    ]
    rows = load_resume_rows(resume_paths)
    dedup = {row_key(row): row for row in rows if row_key(row) is not None}
    rows = list(dedup.values())
    done = set(dedup.keys())

    planned: List[Tuple[PromptSpec, str]] = [
        (prompt, method)
        for prompt in PROMPTS
        for method in METHOD_ORDER
    ]
    planned_rows = len(planned)
    if planned_rows != 80:
        raise RuntimeError(f"Unexpected plan size: {planned_rows}")

    new_rows = 0
    started = time.time()

    for prompt, method in planned:
        effective_seed = (
            seed + CONTROL_SEED_OFFSET
            if method == "baseline_control"
            else seed
        )
        key = (
            prompt.id,
            seed,
            effective_seed,
            method,
            SUITE_VERSION,
        )
        if key in done:
            continue
        if args.limit is not None and new_rows >= args.limit:
            break

        try:
            row = generate_one(
                tokenizer,
                model,
                device,
                prompt,
                seed,
                method,
            )
        except Exception as exc:
            row = {
                "project": project_name,
                "engine": ENGINE_NAME,
                "engine_version": ENGINE_VERSION,
                "suite_version": SUITE_VERSION,
                "model": MODEL_ID,
                "prompt_id": prompt.id,
                "seed": seed,
                "effective_seed": effective_seed,
                "method": method,
                "method_family": generation_method_family(method),
                "status": "error",
                "error_type": type(exc).__name__,
                "error_message": repr(exc),
                "prompt_suite_hash": PROMPT_SUITE_HASH,
                "method_config_hash": METHOD_CONFIG_HASH,
                "router_policy_hash": ROUTER_POLICY_HASH,
            }
            if "cuda" in str(exc).lower() or "out of memory" in str(exc).lower():
                checkpoint(
                    rows,
                    run_dir,
                    project_name,
                    planned_rows,
                    "fatal_gpu_error",
                    seed,
                )
                raise

        rows.append(row)
        done.add(key)
        new_rows += 1

        if len(rows) % SAVE_EVERY == 0:
            checkpoint(
                rows,
                run_dir,
                project_name,
                planned_rows,
                f"auto_rows_{len(rows)}",
                seed,
            )

        if len(rows) % 10 == 0:
            elapsed = (time.time() - started) / 60.0
            print(
                f"{len(rows)}/{planned_rows} rows | "
                f"new={new_rows} | elapsed={elapsed:.1f} min"
            )

    checkpoint(
        rows,
        run_dir,
        project_name,
        planned_rows,
        "final_or_pause",
        seed,
    )

    outputs = run_analysis(rows, run_dir, seed)

    final_manifest = {
        "project": project_name,
        "engine": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "suite_version": SUITE_VERSION,
        "seed": seed,
        "model": MODEL_ID,
        "planned_rows": planned_rows,
        "completed_rows": len(rows),
        "status_counts": Counter(
            str(row.get("status", "unknown")) for row in rows
        ),
        "prompt_suite_hash": PROMPT_SUITE_HASH,
        "method_config_hash": METHOD_CONFIG_HASH,
        "router_policy_hash": ROUTER_POLICY_HASH,
        "single_temperature": True,
        "common_top1_projection": True,
        "external_sampler_connected": False,
        "z_ph_post_hoc_only": True,
        "analysis_files": {
            key: str(path) for key, path in outputs.items()
        },
    }
    manifest_path = run_dir / "final_manifest.json"
    atomic_write_text(
        manifest_path,
        json.dumps(final_manifest, ensure_ascii=False, indent=2, default=str),
    )

    final_zip = args.output_root / f"{project_name}_FINAL_BUNDLE.zip"
    temporary_zip = final_zip.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(run_dir.parent))
    temporary_zip.replace(final_zip)

    print("Run directory:", run_dir)
    print("Final bundle:", final_zip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
