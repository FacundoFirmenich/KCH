from __future__ import annotations

import numpy as np


def helmert_basis(n: int) -> np.ndarray:
    if n < 2:
        raise ValueError("n must be at least two")
    b = np.zeros((n, n - 1), dtype=float)
    for k in range(1, n):
        denom = np.sqrt(k * (k + 1.0))
        b[:k, k - 1] = 1.0 / denom
        b[k, k - 1] = -k / denom
    return b


def sum_zero_projector(n: int) -> np.ndarray:
    return np.eye(n, dtype=float) - np.ones((n, n), dtype=float) / n


def validate_basis(b: np.ndarray, atol: float = 1e-10) -> dict[str, float | bool]:
    b = np.asarray(b, dtype=float)
    n, q = b.shape
    if q != n - 1:
        raise ValueError(f"expected (J,J-1), got {b.shape}")
    e1 = float(np.max(np.abs(b.T @ b - np.eye(q))))
    e2 = float(np.max(np.abs(np.ones(n) @ b)))
    e3 = float(np.max(np.abs(b @ b.T - sum_zero_projector(n))))
    return {
        "orthogonality_max_abs": e1,
        "zero_sum_max_abs": e2,
        "projector_max_abs": e3,
        "valid": bool(max(e1, e2, e3) <= atol),
    }
