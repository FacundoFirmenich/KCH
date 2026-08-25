from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import torch
from torch import Tensor

from torch_transmuter import TorchCanonicalTransmuter, TransmuterConfig


@dataclass(frozen=True)
class TransmuterV03Config(TransmuterConfig):
    """Configuration for a causal, scale-controlled conformational attention bias."""

    laplacian_orientation: Literal["canonical", "diffusive"] = "diffusive"
    bias_normalization: Literal["none", "row_centered_rms"] = "row_centered_rms"
    bias_rms_eps: float = 1e-6

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.bias_rms_eps <= 0:
            raise ValueError("bias_rms_eps must be positive")


class TorchTransmuterV03(TorchCanonicalTransmuter):
    """Transmuter v0.3 with a causal, row-centred conformational score channel.

    The frozen canonical block is not modified. This subclass preserves its Q4
    posterior, conformational graph, FNL closure and TopoNorm, while preventing the
    Laplacian score term from becoming an uncalibrated diagonal offset. For each
    causal query row, valid conformational scores are centred and RMS-normalised;
    ``lambda_q`` therefore has a stable interpretation relative to dot-product
    attention scores.
    """

    config: TransmuterV03Config

    def __init__(self, config: TransmuterV03Config, dtype=torch.float64):
        super().__init__(config, dtype=dtype)

    @staticmethod
    def _causal_valid_mask(mask: Tensor, causal: bool) -> Tensor:
        length = mask.shape[1]
        valid = mask[:, :, None] & mask[:, None, :]
        if causal:
            triangle = torch.tril(
                torch.ones(length, length, dtype=torch.bool, device=mask.device)
            )
            valid = valid & triangle[None]
        return valid

    def normalize_attention_bias(
        self,
        laplacian: Tensor,
        mask: Tensor,
        *,
        causal: bool,
    ) -> Tensor:
        if self.config.bias_normalization == "none":
            return laplacian
        valid = self._causal_valid_mask(mask, causal)
        weights = valid.to(laplacian)
        count = weights.sum(-1, keepdim=True).clamp_min(1.0)
        mean = (laplacian * weights).sum(-1, keepdim=True) / count
        centered = (laplacian - mean) * weights
        rms = (
            centered.square().sum(-1, keepdim=True) / count
        ).sqrt().clamp_min(self.config.bias_rms_eps)
        return centered / rms

    def attn(self, x: Tensor, mask: Tensor, causal: bool):
        batch, length, dim = x.shape
        heads = self.config.num_heads
        head_dim = dim // heads
        query = (x @ self.w_q).reshape(batch, length, heads, head_dim).transpose(1, 2)
        key = (x @ self.w_k).reshape(batch, length, heads, head_dim).transpose(1, 2)
        value = (x @ self.w_v).reshape(batch, length, heads, head_dim).transpose(1, 2)

        posterior = self.q4_posterior(x)
        raw_laplacian = self.conformational_laplacian(posterior, mask)
        if causal:
            rows = []
            for step in range(length):
                prefix = self.conformational_laplacian(
                    posterior[:, : step + 1], mask[:, : step + 1]
                )[:, step, :]
                rows.append(torch.nn.functional.pad(prefix, (0, length - step - 1)))
            raw_laplacian = torch.stack(rows, 1)
        attention_bias = self.normalize_attention_bias(
            raw_laplacian, mask, causal=causal
        )

        qk_scores = query @ key.transpose(-1, -2) / math.sqrt(head_dim)
        scores = qk_scores + self.config.lambda_q * attention_bias[:, None]
        valid_keys = mask[:, None, None, :]
        if causal:
            valid_keys = valid_keys & torch.tril(
                torch.ones(length, length, dtype=torch.bool, device=x.device)
            )[None, None]
        scores = torch.where(valid_keys, scores, torch.finfo(x.dtype).min)
        scores = torch.where(mask[:, None, :, None], scores, torch.zeros_like(scores))
        output = (
            (torch.softmax(scores, -1) @ value)
            .transpose(1, 2)
            .reshape(batch, length, dim)
            @ self.w_o
        )
        self._last_raw_laplacian = raw_laplacian
        self._last_attention_bias = attention_bias
        self._last_qk_scores = qk_scores
        return output * mask[..., None], posterior, attention_bias

    def forward(self, x: Tensor, attention_mask=None, *, causal: bool = False):
        mask = self._mask(x, attention_mask)
        x = x * mask[..., None]
        attention, posterior, attention_bias = self.attn(x, mask, causal)
        stage_one, log_volume_one = self.topo(
            x + self.config.attention_residual * attention, mask, causal
        )
        fnl_output, dispersion = self.fnl(stage_one)
        output, log_volume_two = self.topo(
            stage_one
            + self.config.fnl_residual * fnl_output * mask[..., None],
            mask,
            causal,
        )
        return output, {
            "q_probabilities": posterior,
            "laplacian_raw": self._last_raw_laplacian,
            "attention_bias": attention_bias,
            "qk_scores": self._last_qk_scores,
            "fnl_rho": self.fnl_rho,
            "fnl_theta": self.fnl_theta,
            "fnl_dispersion_mean": dispersion,
            "toponorm_1_log_volume": log_volume_one,
            "toponorm_2_log_volume": log_volume_two,
        }
