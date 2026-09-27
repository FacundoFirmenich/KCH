"""Canonical TALM and TALON cores extracted from guay-qwen3-5-english-native.ipynb.

No external sampler is defined or imported here.
The notebook config fixes operator temperature to 1.0 so sampling temperature
is applied exactly once by Hugging Face after the logits processor.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Literal
import numpy as np
import torch
import torch.nn.functional as F

try:
    from transformers import LogitsProcessor
except Exception:
    class LogitsProcessor:
        pass

# ============================================================
# 03A. TALON core — Training-Free Adaptive Logit Operator Nexus
# INSIDE the operator. In recent transformers (>=4.43) custom logits
# processors run BEFORE the sampling warpers, so generate() applies the
# 0.8 temperature warper ON TOP of the operator output. Effective sampling
# temperature for TALON rows is therefore ~0.64 vs 0.8 for the baseline.
# matched standard rival ("std_temperature_eff_match", T=0.64) is added in
# cell 05 to deconfound operator structure from plain temperature lowering.
# ============================================================
# Numerical guardrails: use finite/clamped copies for statistics only; never unmask
# model-forbidden non-finite logits in the returned score tensor.
LOGIT_FINITE_CLAMP_MIN = -1.0e4
LOGIT_FINITE_CLAMP_MAX =  1.0e4

SelectionMode = Literal["head", "tail", "mass", "hybrid_head", "hybrid_tail"]
DeltaForm = Literal["tanh", "exp_right"]
SidePolicy = Literal["right", "left", "balanced", "side_inverse"]
StdMethod = Literal["median_mad", "mean_std"]

ENGINE_NAME = "TALON — Training-Free Adaptive Logit Operator Nexus"
ENGINE_SHORT = "TALON"
ENGINE_VERSION = "1.0.0"
OPERATOR_FAMILY_NAME = "TALON"

@dataclass
class OperatorConfig:
    strength: float = 0.75
    temperature: float = 1.0
    head_fraction: float = 0.12
    mass_threshold: float = 0.92
    left_weight: float = 0.65
    right_weight: float = 1.20
    side_policy: SidePolicy = "right"
    selection_mode: SelectionMode = "hybrid_head"
    preserve_top1: bool = True
    top1_preserve_momentum: float = 0.20
    kl_threshold: float = 0.0
    delta_form: DeltaForm = "tanh"
    absolute_min_tokens: int = 8
    std_method: StdMethod = "median_mad"
    robust_eps: float = 1e-6
    debug: bool = True

class AdaptiveLogitProcessor(LogitsProcessor):
    def __init__(self, config=None, **kwargs):
        self.config = config or OperatorConfig(**kwargs)
        self.history: List[Dict[str, Any]] = []
        self.last_diag: Dict[str, Any] = {}

    def reset_history(self):
        self.history = []
        self.last_diag = {}

    def _finite_stat_copy(self, x):
        """Finite copy for selection/statistics; original non-finite logits remain masked in final output."""
        return torch.nan_to_num(
            x.float(),
            nan=0.0,
            posinf=LOGIT_FINITE_CLAMP_MAX,
            neginf=LOGIT_FINITE_CLAMP_MIN,
        ).clamp(LOGIT_FINITE_CLAMP_MIN, LOGIT_FINITE_CLAMP_MAX)

    def _apply_temperature(self, scores):
        return scores if self.config.temperature == 1.0 else scores / self.config.temperature

    def _head_mask(self, scores, k):
        idx = torch.topk(scores, k=k, dim=-1).indices
        mask = torch.zeros_like(scores, dtype=torch.bool)
        mask.scatter_(1, idx, True)
        return mask

    def _tail_mask(self, scores, k):
        idx = torch.topk(-scores, k=k, dim=-1).indices
        mask = torch.zeros_like(scores, dtype=torch.bool)
        mask.scatter_(1, idx, True)
        return mask

    def _mass_mask(self, scores):
        scores = self._finite_stat_copy(scores)
        probs = F.softmax(scores, dim=-1)
        sorted_probs, sorted_idx = torch.sort(probs, dim=-1, descending=True)
        cum = torch.cumsum(sorted_probs, dim=-1)
        selected = cum <= self.config.mass_threshold
        selected[..., 0] = True
        crossing = torch.argmax((cum >= self.config.mass_threshold).to(torch.int64), dim=-1)
        selected.scatter_(1, crossing.unsqueeze(1), True)
        mask = torch.zeros_like(scores, dtype=torch.bool)
        mask.scatter_(1, sorted_idx, selected)
        return mask

    def _selection_mask(self, scores):
        vocab = scores.shape[-1]
        k = max(self.config.absolute_min_tokens, int(vocab * self.config.head_fraction))
        k = max(1, min(vocab, k))
        mode = self.config.selection_mode
        if mode == "head": return self._head_mask(scores, k)
        if mode == "tail": return self._tail_mask(scores, k)
        if mode == "mass": return self._mass_mask(scores)
        if mode == "hybrid_head": return self._head_mask(scores, k) | self._mass_mask(scores)
        if mode == "hybrid_tail": return self._tail_mask(scores, k) | self._mass_mask(scores)
        raise ValueError(mode)

    def _standardize(self, scores, mask):
        stat_scores = self._finite_stat_copy(scores)
        finite_mask = mask & torch.isfinite(scores)
        # If a row's selection is accidentally empty, fall back to all finite logits for that row.
        row_has_selection = finite_mask.any(dim=-1, keepdim=True)
        finite_mask = torch.where(row_has_selection, finite_mask, torch.isfinite(scores))
        masked = torch.where(finite_mask, stat_scores, torch.nan)
        if self.config.std_method == "median_mad":
            center = torch.nanmedian(masked, dim=-1, keepdim=True).values
            scale = torch.nanmedian(torch.abs(masked - center), dim=-1, keepdim=True).values
        else:
            center = torch.nanmean(masked, dim=-1, keepdim=True)
            scale = torch.sqrt(torch.nanmean((masked - center) ** 2, dim=-1, keepdim=True) + self.config.robust_eps)
        center = torch.nan_to_num(center, nan=0.0, posinf=LOGIT_FINITE_CLAMP_MAX, neginf=LOGIT_FINITE_CLAMP_MIN)
        scale = torch.nan_to_num(scale, nan=1.0, posinf=1.0, neginf=1.0).clamp_min(self.config.robust_eps)
        z = torch.clamp((stat_scores - center) / scale, -6.0, 6.0)
        return torch.where(torch.isfinite(scores), z, torch.zeros_like(z))

    def __call__(self, input_ids, scores):
        cfg = self.config
        orig_dtype = scores.dtype
        base = scores.float()
        finite_base = torch.isfinite(base)
        stat_base = self._finite_stat_copy(base)
        original_top1 = torch.argmax(stat_base, dim=-1, keepdim=True)
        work = self._apply_temperature(stat_base)
        mask = self._selection_mask(work) & finite_base
        z = self._standardize(work, mask)

        if cfg.side_policy == "right":
            direction = torch.tanh(z)
            weight = torch.where(z >= 0, torch.tensor(cfg.right_weight, device=z.device), torch.tensor(cfg.left_weight, device=z.device))
        elif cfg.side_policy == "left":
            direction = -torch.tanh(z)
            weight = torch.where(z < 0, torch.tensor(cfg.right_weight, device=z.device), torch.tensor(cfg.left_weight, device=z.device))
        elif cfg.side_policy == "balanced":
            direction = torch.tanh(z)
            weight = torch.full_like(work, (cfg.left_weight + cfg.right_weight) / 2.0)
        elif cfg.side_policy == "side_inverse":
            direction = torch.tanh(z)
            weight = torch.where(z >= 0, torch.tensor(cfg.left_weight, device=z.device), torch.tensor(cfg.right_weight, device=z.device))
        else:
            raise ValueError(cfg.side_policy)

        delta = torch.zeros_like(work)
        if cfg.delta_form == "tanh":
            delta[mask] = cfg.strength * direction[mask] * weight[mask]
        elif cfg.delta_form == "exp_right":
            l_max = torch.max(work, dim=-1, keepdim=True).values
            exp_term = torch.exp(work - l_max)
            pos_mask = mask & (z >= 0)
            delta[pos_mask] = cfg.strength * exp_term[pos_mask] * weight[pos_mask]
        modified = work + delta
        modified = torch.where(torch.isfinite(modified), modified, work)
        modified = torch.where(finite_base, modified, base)

        with torch.no_grad():
            p_orig = F.softmax(torch.where(finite_base, work, torch.tensor(LOGIT_FINITE_CLAMP_MIN, device=work.device, dtype=work.dtype)), dim=-1)
            p_mod = F.softmax(torch.where(finite_base, modified, torch.tensor(LOGIT_FINITE_CLAMP_MIN, device=modified.device, dtype=modified.dtype)), dim=-1)
            kl = torch.sum(p_orig * (torch.log(p_orig + 1e-12) - torch.log(p_mod + 1e-12)), dim=-1)

        kl_clipped = torch.zeros_like(kl, dtype=torch.bool)
        if cfg.kl_threshold > 0:
            alpha = (cfg.kl_threshold / (kl + 1e-12)).clamp(max=1.0)
            kl_clipped = kl > cfg.kl_threshold
            modified = work * (1.0 - alpha.view(-1, 1)) + modified * alpha.view(-1, 1)

        top1_changed_before = torch.argmax(modified, dim=-1, keepdim=True).ne(original_top1)
        if cfg.preserve_top1 and top1_changed_before.any():
            blended = work * cfg.top1_preserve_momentum + modified * (1.0 - cfg.top1_preserve_momentum)
            max_other = blended.clone()
            max_other.scatter_(1, original_top1, -torch.inf)
            required = torch.max(max_other, dim=-1, keepdim=True).values + 1e-4
            blended.scatter_(1, original_top1, required)
            modified = torch.where(top1_changed_before, blended, modified)
        top1_changed_final = torch.argmax(modified, dim=-1, keepdim=True).ne(original_top1)

        self.last_diag = {
            "selection_mode": cfg.selection_mode,
            "side_policy": cfg.side_policy,
            "strength": float(cfg.strength),
            "mask_fraction": float(mask.float().mean().detach().cpu()),
            "mean_abs_delta": float(torch.abs(delta).mean().detach().cpu()),
            "max_abs_delta": float(torch.abs(delta).max().detach().cpu()),
            "kl_mean": float(kl.mean().detach().cpu()),
            "kl_max": float(kl.max().detach().cpu()),
            "kl_clipped_rate": float(kl_clipped.float().mean().detach().cpu()),
            "top1_changed_before_preserve_rate": float(top1_changed_before.float().mean().detach().cpu()),
            "top1_changed_final_rate": float(top1_changed_final.float().mean().detach().cpu()),
        }
        if cfg.debug:
            self.history.append(self.last_diag)
        return modified.to(dtype=orig_dtype)

    def summary(self):
        if not self.history:
            return {}
        keys = ["mask_fraction", "mean_abs_delta", "max_abs_delta", "kl_mean", "kl_max", "kl_clipped_rate", "top1_changed_before_preserve_rate", "top1_changed_final_rate"]
        out = {"calls": len(self.history)}
        for k in keys:
            vals = [h.get(k, np.nan) for h in self.history]
            out[f"mean_{k}"] = float(np.nanmean(vals))
        out["last_selection_mode"] = self.history[-1].get("selection_mode")
        out["last_side_policy"] = self.history[-1].get("side_policy")
        return out

print(f"[OK] {ENGINE_NAME} v{ENGINE_VERSION} loaded.")


# ============================================================

# ---- Preserve TALON symbols before loading TALM core ----
TALONOperatorConfig = OperatorConfig
TALONLogitProcessor = AdaptiveLogitProcessor
TALON_ENGINE_NAME = ENGINE_NAME
TALON_ENGINE_SHORT = ENGINE_SHORT
TALON_OPERATOR_FAMILY_NAME = OPERATOR_FAMILY_NAME


# ============================================================
# 03B. TALM core — Tail-Aware Logit Modulation
# non-empty indices, which crashes `delta[idx] += empty` by broadcasting.
# It now returns correctly-sized zeros. No behavioral change for the
# shipped METHODS (all boosts > 0); this only hardens ablations.
# Note: TALM configs keep operator temperature = 1.0, so there is NO
# temperature stacking with the HF sampling warper here (unlike TALON).
# ============================================================
SelectionMode = Literal["rank", "mass", "hybrid"]
TailSide = Literal["right", "left", "balanced", "side_inverse"]

ENGINE_NAME = "TALM — Tail-Aware Logit Modulation"
ENGINE_SHORT = "TALM"
ENGINE_VERSION = "1.0.0"
OPERATOR_FAMILY_NAME = "TALM"

@dataclass
class OperatorConfig:
    strength: float = 1.0
    temperature: float = 1.0
    tail_fraction: float = 0.08
    mass_tail_fraction: float = 0.025
    left_weight: float = 0.2
    right_weight: float = 0.8
    left_boost: float = 0.08
    right_boost: float = 0.28
    min_tail_tokens: int = 8
    max_tail_tokens: int = 4096
    selection_mode: SelectionMode = "mass"
    side_policy: TailSide = "right"
    preserve_top1: bool = False
    top1_preserve_momentum: float = 0.20
    robust_eps: float = 1e-6
    debug: bool = True

class AdaptiveLogitProcessor(LogitsProcessor):
    def __init__(self, config=None, **kwargs):
        self.config = config or OperatorConfig(**kwargs)
        self.history: List[Dict[str, Any]] = []
        self.last_diag: Dict[str, Any] = {}

    def reset_history(self):
        self.history = []
        self.last_diag = {}

    def _apply_temperature(self, scores):
        return scores if self.config.temperature == 1.0 else scores / self.config.temperature

    def _safe_probs(self, x):
        x = x.float()
        finite = torch.isfinite(x)
        if not finite.any():
            return torch.full_like(x, 1.0 / x.numel())
        min_f = torch.min(x[finite])
        x = torch.where(finite, x, min_f - 1000.0)
        p = F.softmax(x, dim=-1)
        return p / torch.clamp(p.sum(), min=1e-12)

    def _rank_indices(self, x):
        cfg = self.config
        finite = torch.isfinite(x)
        idx = torch.where(finite)[0]
        vals = x[idx]
        _, order_pos = torch.sort(vals, descending=False)
        sorted_idx = idx[order_pos]
        n = int(sorted_idx.numel())
        left_req = cfg.tail_fraction * cfg.left_weight
        right_req = cfg.tail_fraction * cfg.right_weight
        left_count = max(cfg.min_tail_tokens, int(n * left_req)) if left_req > 0 else 0
        right_count = max(cfg.min_tail_tokens, int(n * right_req)) if right_req > 0 else 0
        left_count = min(left_count, cfg.max_tail_tokens, n)
        right_count = min(right_count, cfg.max_tail_tokens, n)
        left = sorted_idx[:left_count]
        right = sorted_idx[n-right_count:] if right_count else torch.empty(0, dtype=torch.long, device=x.device)
        return left, right

    def _mass_indices(self, x):
        cfg = self.config
        p = self._safe_probs(x)
        low_order = torch.argsort(p, descending=False)
        high_order = torch.argsort(p, descending=True)
        def take(order, target):
            if target <= 0:
                return torch.empty(0, dtype=torch.long, device=x.device)
            cum = torch.cumsum(p[order], dim=0)
            threshold = torch.tensor(target, device=x.device, dtype=cum.dtype)
            count = int(torch.searchsorted(cum, threshold).item() + 1)
            count = max(cfg.min_tail_tokens, count)
            count = min(count, cfg.max_tail_tokens, int(order.numel()))
            return order[:count]
        left = take(low_order, cfg.mass_tail_fraction * cfg.left_weight)
        right = take(high_order, cfg.mass_tail_fraction * cfg.right_weight)
        return left, right

    def _select(self, x):
        if self.config.selection_mode == "rank":
            return self._rank_indices(x)
        if self.config.selection_mode == "mass":
            return self._mass_indices(x)
        l1, r1 = self._rank_indices(x)
        l2, r2 = self._mass_indices(x)
        left = torch.unique(torch.cat([l1, l2]))[:self.config.max_tail_tokens]
        right = torch.unique(torch.cat([r1, r2]))[:self.config.max_tail_tokens]
        return left, right

    def _delta_for(self, x, idx, boost, sign=1.0):
        if idx.numel() == 0:
            return torch.zeros(0, device=x.device, dtype=x.dtype)
        if boost == 0:
            return torch.zeros(idx.numel(), device=x.device, dtype=x.dtype)
        vals = x[idx]
        med = torch.median(vals)
        scale = torch.median(torch.abs(vals - med)).clamp_min(self.config.robust_eps)
        z = torch.abs((vals - med) / scale).clamp(max=6.0)
        z = z / torch.clamp(torch.max(z), min=self.config.robust_eps)
        return sign * self.config.strength * boost * z

    def __call__(self, input_ids, scores):
        cfg = self.config
        orig_dtype = scores.dtype
        base = scores.float()
        out_rows = []
        diag_rows = []
        for b in range(base.shape[0]):
            x0 = base[b]
            original_top1 = torch.argmax(x0).view(1)
            x = self._apply_temperature(x0.clone())
            left_idx, right_idx = self._select(x)
            delta = torch.zeros_like(x)
            if cfg.side_policy == "right":
                delta[left_idx] += self._delta_for(x, left_idx, cfg.left_boost, sign=+1.0)
                delta[right_idx] += self._delta_for(x, right_idx, cfg.right_boost, sign=+1.0)
            elif cfg.side_policy == "left":
                delta[left_idx] += self._delta_for(x, left_idx, cfg.left_boost, sign=+1.0)
                delta[right_idx] += self._delta_for(x, right_idx, cfg.right_boost, sign=-0.25)
            elif cfg.side_policy == "balanced":
                delta[left_idx] += self._delta_for(x, left_idx, cfg.left_boost, sign=+1.0)
                delta[right_idx] += self._delta_for(x, right_idx, cfg.right_boost, sign=+1.0)
            elif cfg.side_policy == "side_inverse":
                delta[left_idx] += self._delta_for(x, left_idx, cfg.right_boost, sign=+1.0)
                delta[right_idx] += self._delta_for(x, right_idx, cfg.left_boost, sign=+1.0)
            else:
                raise ValueError(cfg.side_policy)
            modified = x + delta
            with torch.no_grad():
                p0 = F.softmax(x, dim=-1)
                p1 = F.softmax(modified, dim=-1)
                kl = torch.sum(p0 * (torch.log(p0 + 1e-12) - torch.log(p1 + 1e-12)))
            top1_changed_before = torch.argmax(modified).view(1).ne(original_top1)
            if cfg.preserve_top1 and bool(top1_changed_before.item()):
                blended = x * cfg.top1_preserve_momentum + modified * (1.0 - cfg.top1_preserve_momentum)
                max_other = blended.clone(); max_other[original_top1] = -torch.inf
                required = torch.max(max_other) + 1e-4
                blended[original_top1] = required
                modified = blended
            top1_changed_final = torch.argmax(modified).view(1).ne(original_top1)
            mask_count = int(torch.unique(torch.cat([left_idx, right_idx])).numel())
            diag_rows.append({
                "selection_mode": cfg.selection_mode,
                "side_policy": cfg.side_policy,
                "strength": float(cfg.strength),
                "mask_fraction": float(mask_count / max(1, x.numel())),
                "mean_abs_delta": float(torch.abs(delta).mean().detach().cpu()),
                "max_abs_delta": float(torch.abs(delta).max().detach().cpu()),
                "kl_mean": float(kl.detach().cpu()),
                "kl_max": float(kl.detach().cpu()),
                "kl_clipped_rate": 0.0,
                "top1_changed_before_preserve_rate": float(top1_changed_before.float().mean().detach().cpu()),
                "top1_changed_final_rate": float(top1_changed_final.float().mean().detach().cpu()),
            })
            out_rows.append(modified)
        self.last_diag = {k: float(np.mean([d[k] for d in diag_rows])) if isinstance(diag_rows[0].get(k), float) else diag_rows[-1].get(k) for k in diag_rows[0].keys()}
        if cfg.debug:
            self.history.append(self.last_diag)
        return torch.stack(out_rows, dim=0).to(dtype=orig_dtype)

    def summary(self):
        if not self.history:
            return {}
        keys = ["mask_fraction", "mean_abs_delta", "max_abs_delta", "kl_mean", "kl_max", "kl_clipped_rate", "top1_changed_before_preserve_rate", "top1_changed_final_rate"]
        out = {"calls": len(self.history)}
        for k in keys:
            vals = [h.get(k, np.nan) for h in self.history]
            out[f"mean_{k}"] = float(np.nanmean(vals))
        out["last_selection_mode"] = self.history[-1].get("selection_mode")
        out["last_side_policy"] = self.history[-1].get("side_policy")
        return out

print(f"[OK] {ENGINE_NAME} v{ENGINE_VERSION} loaded.")


# ---- Preserve TALM symbols and define combined DIRECTCOMP engine ----
TALMOperatorConfig = OperatorConfig
TALMLogitProcessor = AdaptiveLogitProcessor
TALM_ENGINE_NAME = ENGINE_NAME
TALM_ENGINE_SHORT = ENGINE_SHORT
TALM_OPERATOR_FAMILY_NAME = OPERATOR_FAMILY_NAME

ENGINE_NAME = "DIRECTCOMP — TALM + TALON vs Min-p / p-LESS / Min-k"

__all__ = [
    "TALONOperatorConfig", "TALONLogitProcessor",
    "TALMOperatorConfig", "TALMLogitProcessor",
]
