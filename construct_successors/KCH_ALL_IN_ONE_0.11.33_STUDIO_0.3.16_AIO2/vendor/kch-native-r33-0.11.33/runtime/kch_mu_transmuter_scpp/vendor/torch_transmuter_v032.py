from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from torch_transmuter_v03 import TorchTransmuterV03, TransmuterV03Config


@dataclass(frozen=True)
class TransmuterV032Config(TransmuterV03Config):
    """Configuration for the gradient-safe v0.3.2 normalization."""


class TorchTransmuterV032(TorchTransmuterV03):
    """Gradient-safe correction of the v0.3 causal RMS normalization.

    v0.3 evaluated ``sqrt(mean(square)).clamp_min(eps)``. A causal row with one
    valid token has exactly zero centred variance, so autograd encounters the
    singular derivative of ``sqrt(0)`` before the clamp can protect it. v0.3.2
    uses ``sqrt(mean(square) + eps**2)`` and preserves the intended forward scale.
    """

    config: TransmuterV032Config

    def __init__(self, config: TransmuterV032Config, dtype=torch.float64):
        super().__init__(config, dtype=dtype)

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
        mean_square = centered.square().sum(-1, keepdim=True) / count
        rms = (mean_square + self.config.bias_rms_eps**2).sqrt()
        return centered / rms
