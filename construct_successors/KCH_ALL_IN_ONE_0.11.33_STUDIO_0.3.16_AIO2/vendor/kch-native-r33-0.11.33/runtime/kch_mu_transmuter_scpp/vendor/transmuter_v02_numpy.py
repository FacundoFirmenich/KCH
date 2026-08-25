"""Canonical CFL Transmuter v0.2 — executable NumPy reference.

This module advances the spectral-conformational Transmuter while preserving
its architectural identity:

    QK^T / sqrt(d_h) + lambda_q * L_Q  -> attention
    attention residual -> TopoNorm -> FNL residual -> TopoNorm

It is a forward/reference implementation. It deliberately does not pretend to
provide automatic differentiation; the same equations are intended to be
ported to a training backend after their invariants are frozen and tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

Array = np.ndarray


def _softmax(x: Array, axis: int = -1) -> Array:
    z = x - np.max(x, axis=axis, keepdims=True)
    ez = np.exp(z)
    return ez / np.sum(ez, axis=axis, keepdims=True)


def _xavier(rng: np.random.Generator, fan_in: int, fan_out: int) -> Array:
    bound = np.sqrt(6.0 / (fan_in + fan_out))
    return rng.uniform(-bound, bound, size=(fan_in, fan_out))


@dataclass(frozen=True)
class TransmuterConfig:
    dim: int
    num_heads: int = 4
    lambda_q: float = 0.3
    tau_q: float = 0.75
    q_temperature: float = 1.0
    laplacian_orientation: Literal["canonical", "diffusive"] = "canonical"
    n_maps: int = 3
    rho_max: float = 0.85
    theta_min: float = np.pi / 8
    theta_gap: float = np.pi / 12
    fnl_closure_strength: float = 0.2
    attention_residual: float = 0.2
    fnl_residual: float = 0.2
    toponorm_shrinkage: float = 0.05
    toponorm_eps: float = 1e-6
    seed: int = 101

    def __post_init__(self) -> None:
        if self.dim < 2:
            raise ValueError("dim must be >= 2")
        if self.dim % self.num_heads != 0:
            raise ValueError("dim must be divisible by num_heads")
        if self.n_maps < 2:
            raise ValueError("FNL requires at least two maps")
        if not (0.0 < self.rho_max < 1.0):
            raise ValueError("rho_max must be strictly between 0 and 1")
        if self.tau_q <= 0.0 or self.q_temperature <= 0.0:
            raise ValueError("Q4 temperatures must be positive")
        if not (0.0 <= self.toponorm_shrinkage < 1.0):
            raise ValueError("toponorm_shrinkage must be in [0, 1)")
        upper = np.pi / 2 - self.theta_gap
        if not (0.0 < self.theta_min < upper):
            raise ValueError("invalid obliquity interval")


@dataclass
class TopoDiagnostics:
    log_volume_before: Array
    log_volume_after: Array
    effective_rank: Array
    normalized_gap: Array


@dataclass
class TransmuterDiagnostics:
    q_probabilities: Array
    q_usage: Array
    q_entropy: float
    laplacian: Array
    laplacian_symmetry_error: float
    laplacian_extreme_eigenvalue: Array
    fnl_rho: Array
    fnl_theta: Array
    fnl_obliquity_margin: float
    fnl_dispersion_mean: float
    toponorm_1: TopoDiagnostics
    toponorm_2: TopoDiagnostics


class CanonicalTransmuter:
    """Spectral-conformational Transmuter with FNL and stable TopoNorm."""

    # Coordinates encode the two canonical axes:
    # constituent/differential and principal/transmutational.
    Q4_COORDS = np.asarray(
        [
            [1.0, 1.0],    # 1
            [-1.0, 1.0],   # -1
            [1.0, -1.0],   # +0
            [-1.0, -1.0],  # 0
        ],
        dtype=np.float64,
    )

    def __init__(self, config: TransmuterConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        d = config.dim

        self.w_q = _xavier(self.rng, d, d)
        self.w_k = _xavier(self.rng, d, d)
        self.w_v = _xavier(self.rng, d, d)
        self.w_o = _xavier(self.rng, d, d)

        # Q4 is categorical. +0 is not replaced by a small real number.
        self.w_q4 = _xavier(self.rng, d, 4)
        self.b_q4 = np.zeros(4, dtype=np.float64)

        self.fnl_rho = self.rng.uniform(
            0.2 * config.rho_max,
            0.8 * config.rho_max,
            size=config.n_maps,
        )
        self.fnl_theta = self._initial_oblique_angles()
        self.fnl_translation = self.rng.normal(
            0.0, 0.05, size=(config.n_maps, d)
        )

    def _initial_oblique_angles(self) -> Array:
        c = self.config
        low_end = np.pi / 2 - c.theta_gap
        high_start = np.pi / 2 + c.theta_gap
        high_end = np.pi - c.theta_min
        angles = np.empty(c.n_maps, dtype=np.float64)
        for m in range(c.n_maps):
            if m % 2 == 0:
                angles[m] = self.rng.uniform(c.theta_min, low_end)
            else:
                angles[m] = self.rng.uniform(high_start, high_end)
        return angles

    def q4_posterior(self, x: Array) -> Array:
        self._validate_x(x)
        logits = (x @ self.w_q4 + self.b_q4) / self.config.q_temperature
        return _softmax(logits, axis=-1)

    def conformational_laplacian(self, probabilities: Array) -> Array:
        """Build a normalized Q4 Laplacian for every batch item.

        Distance combines Hellinger geometry on the full posterior with the two
        typed Q4 axes. The canonical orientation is D-A, matching the inherited
        implementation. The diffusive A-D orientation is exposed for frozen
        ablation rather than silently changing the sign convention.
        """

        if probabilities.ndim != 3 or probabilities.shape[-1] != 4:
            raise ValueError("probabilities must have shape (B, N, 4)")

        sqrt_p = np.sqrt(np.clip(probabilities, 0.0, 1.0))
        ds = sqrt_p[:, :, None, :] - sqrt_p[:, None, :, :]
        hellinger = 0.5 * np.sum(ds * ds, axis=-1)

        axes = probabilities @ self.Q4_COORDS
        da = np.abs(axes[:, :, None, :] - axes[:, None, :, :]) / 2.0
        typed_axis_distance = 0.5 * np.mean(da, axis=-1)
        distance = hellinger + typed_axis_distance

        adjacency = np.exp(-distance / self.config.tau_q)
        n = adjacency.shape[-1]
        adjacency *= 1.0 - np.eye(n, dtype=adjacency.dtype)[None, :, :]
        degree = np.sum(adjacency, axis=-1)
        inv_sqrt_degree = 1.0 / np.sqrt(np.maximum(degree, 1e-12))
        normalized_adjacency = (
            inv_sqrt_degree[:, :, None]
            * adjacency
            * inv_sqrt_degree[:, None, :]
        )
        identity = np.eye(n, dtype=adjacency.dtype)[None, :, :]
        laplacian = identity - normalized_adjacency
        if self.config.laplacian_orientation == "diffusive":
            laplacian = -laplacian
        return 0.5 * (laplacian + np.swapaxes(laplacian, -1, -2))

    def spectral_attention(
        self, x: Array
    ) -> tuple[Array, Array, Array, Array, float, Array]:
        self._validate_x(x)
        b, n, d = x.shape
        h = self.config.num_heads
        dh = d // h

        q = (x @ self.w_q).reshape(b, n, h, dh).transpose(0, 2, 1, 3)
        k = (x @ self.w_k).reshape(b, n, h, dh).transpose(0, 2, 1, 3)
        v = (x @ self.w_v).reshape(b, n, h, dh).transpose(0, 2, 1, 3)

        q_probabilities = self.q4_posterior(x)
        laplacian = self.conformational_laplacian(q_probabilities)
        scores = (q @ np.swapaxes(k, -1, -2)) / np.sqrt(dh)
        scores = scores + self.config.lambda_q * laplacian[:, None, :, :]
        weights = _softmax(scores, axis=-1)
        attended = weights @ v
        attended = attended.transpose(0, 2, 1, 3).reshape(b, n, d) @ self.w_o

        symmetry_error = float(
            np.max(np.abs(laplacian - np.swapaxes(laplacian, -1, -2)))
        )
        eig = np.linalg.eigvalsh(laplacian)
        if self.config.laplacian_orientation == "canonical":
            extreme = eig[:, 0]
        else:
            extreme = eig[:, -1]
        return attended, q_probabilities, laplacian, weights, symmetry_error, extreme

    def _rotation(self, map_index: int) -> Array:
        d = self.config.dim
        a = (2 * map_index) % d
        b = (2 * map_index + 1) % d
        if a == b:
            b = (b + 1) % d
        theta = self.fnl_theta[map_index]
        c, s = np.cos(theta), np.sin(theta)
        rotation = np.eye(d, dtype=np.float64)
        rotation[a, a] = c
        rotation[a, b] = -s
        rotation[b, a] = s
        rotation[b, b] = c
        return rotation

    def fractal_nested_layer(self, x: Array) -> tuple[Array, float]:
        self._validate_x(x)
        mapped = []
        for m in range(self.config.n_maps):
            rotation = self._rotation(m)
            y = self.fnl_rho[m] * (x @ rotation.T) + self.fnl_translation[m]
            mapped.append(y)
        stack = np.stack(mapped, axis=0)
        center = np.mean(stack, axis=0)
        dispersion = np.sqrt(np.mean((stack - center) ** 2, axis=0) + 1e-12)

        # Nonlinear bounded closure; unlike the inherited linear interpolation,
        # this cannot be reduced to one affine map when dispersion is nonzero.
        relative_dispersion = dispersion / (1.0 + dispersion)
        correction = np.tanh(x - center) * (1.0 + relative_dispersion)
        closed = center + self.config.fnl_closure_strength * correction
        return closed, float(np.mean(dispersion))

    def topological_normalize(self, x: Array) -> tuple[Array, TopoDiagnostics]:
        """Normalize centered covariance volume through a stable log spectrum.

        The centroid and covariance orientation are preserved. Only one global
        scale per batch item is changed; this avoids determinant underflow and
        remains finite when sequence length is smaller than feature dimension.
        """

        self._validate_x(x)
        _, n, d = x.shape
        mean = np.mean(x, axis=1, keepdims=True)
        centered = x - mean
        denom = max(n - 1, 1)
        covariance = np.swapaxes(centered, -1, -2) @ centered / denom
        trace_scale = np.trace(covariance, axis1=-2, axis2=-1) / d
        eye = np.eye(d, dtype=x.dtype)[None, :, :]
        shrink = self.config.toponorm_shrinkage
        covariance_reg = (
            (1.0 - shrink) * covariance
            + shrink * trace_scale[:, None, None] * eye
            + self.config.toponorm_eps * eye
        )
        eig = np.maximum(np.linalg.eigvalsh(covariance_reg), self.config.toponorm_eps)
        log_volume_before = 0.5 * np.mean(np.log(eig), axis=-1)
        scale = np.exp(log_volume_before)[:, None, None]
        normalized = mean + centered / scale

        centered_after = normalized - np.mean(normalized, axis=1, keepdims=True)
        cov_after = np.swapaxes(centered_after, -1, -2) @ centered_after / denom
        trace_after = np.trace(cov_after, axis1=-2, axis2=-1) / d
        cov_after_reg = (
            (1.0 - shrink) * cov_after
            + shrink * trace_after[:, None, None] * eye
            + self.config.toponorm_eps * eye
        )
        eig_after = np.maximum(
            np.linalg.eigvalsh(cov_after_reg), self.config.toponorm_eps
        )
        log_volume_after = 0.5 * np.mean(np.log(eig_after), axis=-1)

        p = eig_after / np.sum(eig_after, axis=-1, keepdims=True)
        entropy = -np.sum(p * np.log(np.maximum(p, 1e-12)), axis=-1)
        effective_rank = np.exp(entropy)
        if d > 1:
            gap = eig_after[:, -1] - eig_after[:, -2]
        else:  # guarded by config, kept for numerical completeness
            gap = np.zeros(eig_after.shape[0])
        normalized_gap = gap / np.maximum(eig_after[:, -1], 1e-12)

        diagnostics = TopoDiagnostics(
            log_volume_before=log_volume_before,
            log_volume_after=log_volume_after,
            effective_rank=effective_rank,
            normalized_gap=normalized_gap,
        )
        return normalized, diagnostics

    def forward(self, x: Array) -> tuple[Array, TransmuterDiagnostics]:
        self._validate_x(x)
        x = np.asarray(x, dtype=np.float64)

        attn, q_probs, laplacian, _, symmetry_error, extreme = self.spectral_attention(x)
        state_1 = x + self.config.attention_residual * attn
        state_1, topo_1 = self.topological_normalize(state_1)

        fractal, dispersion_mean = self.fractal_nested_layer(state_1)
        state_2 = state_1 + self.config.fnl_residual * fractal
        output, topo_2 = self.topological_normalize(state_2)

        q_usage = np.mean(q_probs, axis=(0, 1))
        q_entropy = float(
            -np.mean(np.sum(q_probs * np.log(np.maximum(q_probs, 1e-12)), axis=-1))
        )
        margin = float(
            np.min(
                np.minimum(
                    np.abs(self.fnl_theta - self.config.theta_min),
                    np.abs(np.abs(self.fnl_theta - np.pi / 2) - self.config.theta_gap),
                )
            )
        )

        diagnostics = TransmuterDiagnostics(
            q_probabilities=q_probs,
            q_usage=q_usage,
            q_entropy=q_entropy,
            laplacian=laplacian,
            laplacian_symmetry_error=symmetry_error,
            laplacian_extreme_eigenvalue=extreme,
            fnl_rho=self.fnl_rho.copy(),
            fnl_theta=self.fnl_theta.copy(),
            fnl_obliquity_margin=margin,
            fnl_dispersion_mean=dispersion_mean,
            toponorm_1=topo_1,
            toponorm_2=topo_2,
        )
        return output, diagnostics

    def _validate_x(self, x: Array) -> None:
        if not isinstance(x, np.ndarray):
            raise TypeError("x must be a NumPy array")
        if x.ndim != 3:
            raise ValueError("x must have shape (batch, sequence, dim)")
        if x.shape[-1] != self.config.dim:
            raise ValueError(
                f"last dimension must be {self.config.dim}, got {x.shape[-1]}"
            )
        if x.shape[1] < 2:
            raise ValueError("sequence length must be >= 2")
        if not np.all(np.isfinite(x)):
            raise ValueError("x contains non-finite values")


__all__ = [
    "CanonicalTransmuter",
    "TopoDiagnostics",
    "TransmuterConfig",
    "TransmuterDiagnostics",
]
