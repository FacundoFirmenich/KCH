"""Registry-conformant TALM/TALON pre-softmax operators for BIFM v0.12.

The configurations and provenance hashes are frozen from the public
EXACT_ACTION_REGISTRY_v1.0 in FacundoFirmenich/cfl_logitsprocessors.

This module is a transparent reimplementation from the registered fields. It
is NOT claimed to be byte-identical to the historical notebooks. That boundary
is part of every execution receipt.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import torch

REGISTRY_SOURCE = {
    "repository": "FacundoFirmenich/cfl_logitsprocessors",
    "ref": "Ulalito's-Island",
    "path": "preregistrations/2026-07-02-rds-expanded-architecture-v1.0/frozen_snapshot/architecture/EXACT_ACTION_REGISTRY_v1.0.json",
    "blob_sha": "2deeda2ba20edb5138bb9a068178c1a66c55c0bb",
}

TALM_MASS_RIGHT_SOFT = {
    "action_id": "talm_mass_right_soft",
    "operator_group": "TALM",
    "lineage": "directcomp_qwen35_4b_source",
    "configuration_sha256": "8e310bbeba60b256d11246825fda71587dcbe6354d73291b5adb6e2b5ca32872",
    "configuration": {
        "strength": 0.7,
        "temperature": 1.0,
        "tail_fraction": 0.08,
        "mass_tail_fraction": 0.025,
        "left_weight": 0.2,
        "right_weight": 0.8,
        "left_boost": 0.08,
        "right_boost": 0.28,
        "min_tail_tokens": 8,
        "max_tail_tokens": 4096,
        "selection_mode": "mass",
        "side_policy": "right",
        "preserve_top1": True,
        "top1_preserve_momentum": 0.2,
        "robust_eps": 1e-6,
    },
}

TALON_MASS_RIGHT = {
    "action_id": "talon_mass_right",
    "operator_group": "TALON",
    "lineage": "directcomp_qwen35_4b_source",
    "configuration_sha256": "67875f7e54c14e3aa11b7dea3120ee054116b951ebd2507b8f524c1b9e40712a",
    "configuration": {
        "strength": 0.7,
        "temperature": 0.8,
        "head_fraction": 0.12,
        "mass_threshold": 0.92,
        "left_weight": 0.65,
        "right_weight": 1.2,
        "side_policy": "right",
        "selection_mode": "mass",
        "preserve_top1": True,
        "top1_preserve_momentum": 0.2,
        "kl_threshold": 0.0,
        "delta_form": "tanh",
        "absolute_min_tokens": 8,
        "std_method": "median_mad",
        "robust_eps": 1e-6,
    },
}

TALON_MASS_RIGHT_NO_PRESERVE = {
    "action_id": "talon_mass_right_no_preserve_exploratory",
    "operator_group": "TALON",
    "lineage": "directcomp_qwen35_4b_source",
    "configuration_sha256": "4dc71ef7281be381ce41dbff8d987f89c048ec98d4dd8d05c145da8df29bd9f4",
    "configuration": {
        **TALON_MASS_RIGHT["configuration"],
        "preserve_top1": False,
    },
}


@dataclass(frozen=True)
class OperatorTelemetry:
    action_id: str
    operator_group: str
    selected_left: int
    selected_right: int
    robust_scale_mean: float
    delta_l2_mean: float
    delta_linf_mean: float
    changed_global_top1: int
    preserved_global_top1: int
    constant_shift_residual_mean: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _median_mad(x: torch.Tensor, eps: float) -> tuple[torch.Tensor, torch.Tensor]:
    med = x.median(dim=-1, keepdim=True).values
    mad = (x - med).abs().median(dim=-1, keepdim=True).values
    return med, 1.4826 * mad + eps


def _mass_indices(
    probs: torch.Tensor,
    *,
    descending: bool,
    target_mass: float,
    min_tokens: int,
    max_tokens: int,
) -> torch.Tensor:
    """Return a padded boolean selection mask for each row."""
    values, order = torch.sort(probs, dim=-1, descending=descending)
    cumulative = values.cumsum(dim=-1)
    reached = cumulative >= target_mass
    first = reached.float().argmax(dim=-1)
    never = ~reached.any(dim=-1)
    first = torch.where(never, torch.full_like(first, probs.shape[-1] - 1), first)
    counts = (first + 1).clamp(min=min_tokens, max=min(max_tokens, probs.shape[-1]))
    ranks = torch.arange(probs.shape[-1], device=probs.device).unsqueeze(0)
    selected_sorted = ranks < counts.unsqueeze(1)
    mask = torch.zeros_like(selected_sorted, dtype=torch.bool)
    mask.scatter_(1, order, selected_sorted)
    return mask


def _preserve_original_top1(
    base: torch.Tensor,
    transformed: torch.Tensor,
    momentum: float,
) -> torch.Tensor:
    """Restore the original top-1 with a fraction of its original gap."""
    top = base.argmax(dim=-1)
    top2 = torch.topk(base, 2, dim=-1).values
    original_gap = (top2[:, 0] - top2[:, 1]).clamp_min(0.0)
    out = transformed.clone()
    top_mask = torch.nn.functional.one_hot(top, num_classes=base.shape[-1]).bool()
    max_other = out.masked_fill(top_mask, -torch.inf).max(dim=-1).values
    required = max_other + torch.maximum(
        torch.full_like(original_gap, 1e-6), momentum * original_gap
    )
    current = out.gather(1, top.unsqueeze(1)).squeeze(1)
    repaired = torch.maximum(current, required)
    out.scatter_(1, top.unsqueeze(1), repaired.unsqueeze(1))
    return out


def _telemetry(
    registry: dict[str, Any],
    base: torch.Tensor,
    transformed: torch.Tensor,
    left_mask: torch.Tensor,
    right_mask: torch.Tensor,
    scale: torch.Tensor,
) -> OperatorTelemetry:
    delta = transformed - base
    centered = delta - delta.mean(dim=-1, keepdim=True)
    before = base.argmax(dim=-1)
    after = transformed.argmax(dim=-1)
    changed = int((before != after).sum().item())
    return OperatorTelemetry(
        action_id=registry["action_id"],
        operator_group=registry["operator_group"],
        selected_left=int(left_mask.sum(dim=-1).float().mean().item()),
        selected_right=int(right_mask.sum(dim=-1).float().mean().item()),
        robust_scale_mean=float(scale.mean().item()),
        delta_l2_mean=float(delta.norm(dim=-1).mean().item()),
        delta_linf_mean=float(delta.abs().amax(dim=-1).mean().item()),
        changed_global_top1=changed,
        preserved_global_top1=int(base.shape[0] - changed),
        constant_shift_residual_mean=float(centered.norm(dim=-1).mean().item()),
    )


def talm_mass_right_soft(logits: torch.Tensor) -> tuple[torch.Tensor, OperatorTelemetry]:
    cfg = TALM_MASS_RIGHT_SOFT["configuration"]
    base = logits / float(cfg["temperature"])
    probs = torch.softmax(base, dim=-1)
    left = _mass_indices(
        probs,
        descending=False,
        target_mass=float(cfg["mass_tail_fraction"]),
        min_tokens=int(cfg["min_tail_tokens"]),
        max_tokens=int(cfg["max_tail_tokens"]),
    )
    right = _mass_indices(
        probs,
        descending=True,
        target_mass=float(cfg["mass_tail_fraction"]),
        min_tokens=int(cfg["min_tail_tokens"]),
        max_tokens=int(cfg["max_tail_tokens"]),
    )
    med, scale = _median_mad(base, float(cfg["robust_eps"]))
    z = (base - med) / scale
    left_shape = (-z).clamp_min(0.0)
    right_shape = z.clamp_min(0.0)
    left_shape = left_shape / left_shape.amax(dim=-1, keepdim=True).clamp_min(1.0)
    right_shape = right_shape / right_shape.amax(dim=-1, keepdim=True).clamp_min(1.0)
    delta = torch.zeros_like(base)
    delta = delta + left * (
        float(cfg["strength"])
        * float(cfg["left_weight"])
        * float(cfg["left_boost"])
        * (0.25 + 0.75 * left_shape)
    )
    delta = delta + right * (
        float(cfg["strength"])
        * float(cfg["right_weight"])
        * float(cfg["right_boost"])
        * (0.25 + 0.75 * right_shape)
    )
    out = base + delta
    if bool(cfg["preserve_top1"]):
        out = _preserve_original_top1(base, out, float(cfg["top1_preserve_momentum"]))
    return out, _telemetry(TALM_MASS_RIGHT_SOFT, base, out, left, right, scale)


def _talon(logits: torch.Tensor, registry: dict[str, Any]) -> tuple[torch.Tensor, OperatorTelemetry]:
    cfg = registry["configuration"]
    base = logits / float(cfg["temperature"])
    probs = torch.softmax(base, dim=-1)
    vocab = probs.shape[-1]
    max_head = max(int(cfg["absolute_min_tokens"]), int(round(float(cfg["head_fraction"]) * vocab)))
    right = _mass_indices(
        probs,
        descending=True,
        target_mass=float(cfg["mass_threshold"]),
        min_tokens=int(cfg["absolute_min_tokens"]),
        max_tokens=max_head,
    )
    left = torch.zeros_like(right)
    med, scale = _median_mad(base, float(cfg["robust_eps"]))
    z = (base - med) / scale
    if cfg["delta_form"] != "tanh":
        raise ValueError(f"Unsupported TALON delta_form: {cfg['delta_form']}")
    shaped = torch.tanh(z)
    positive = shaped.clamp_min(0.0) * float(cfg["right_weight"])
    negative = shaped.clamp_max(0.0) * float(cfg["left_weight"])
    delta = float(cfg["strength"]) * right * (positive + negative)
    out = base + delta
    if bool(cfg["preserve_top1"]):
        out = _preserve_original_top1(base, out, float(cfg["top1_preserve_momentum"]))
    return out, _telemetry(registry, base, out, left, right, scale)


def talon_mass_right(logits: torch.Tensor) -> tuple[torch.Tensor, OperatorTelemetry]:
    return _talon(logits, TALON_MASS_RIGHT)


def talon_mass_right_no_preserve(logits: torch.Tensor) -> tuple[torch.Tensor, OperatorTelemetry]:
    return _talon(logits, TALON_MASS_RIGHT_NO_PRESERVE)


def temperature_control(logits: torch.Tensor, temperature: float = 0.8) -> torch.Tensor:
    return logits / float(temperature)


def registry_snapshot() -> dict[str, Any]:
    return {
        "source": REGISTRY_SOURCE,
        "implementation_status": "registry-conformant transparent reimplementation; not byte-identical-source claim",
        "operators": [
            TALM_MASS_RIGHT_SOFT,
            TALON_MASS_RIGHT,
            TALON_MASS_RIGHT_NO_PRESERVE,
        ],
    }
