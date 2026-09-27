from __future__ import annotations

import numpy as np


def helmert_basis(n: int) -> np.ndarray:
    """Return an n x (n-1) orthonormal basis for the sum-zero subspace."""
    if n < 2:
        raise ValueError("n must be at least 2")
    basis = np.zeros((n, n - 1), dtype=float)
    for k in range(1, n):
        denom = np.sqrt(k * (k + 1.0))
        basis[:k, k - 1] = 1.0 / denom
        basis[k, k - 1] = -k / denom
    return basis


def projector_sum_zero(n: int) -> np.ndarray:
    return np.eye(n, dtype=float) - np.ones((n, n), dtype=float) / n


def validate_basis(basis: np.ndarray, atol: float = 1e-10) -> dict[str, float | bool]:
    b = np.asarray(basis, dtype=float)
    n, q = b.shape
    if q != n - 1:
        raise ValueError("basis must have shape (n, n-1)")
    orth_error = float(np.max(np.abs(b.T @ b - np.eye(q))))
    zero_error = float(np.max(np.abs(np.ones(n) @ b)))
    projector_error = float(np.max(np.abs(b @ b.T - projector_sum_zero(n))))
    return {
        "orthogonality_max_abs": orth_error,
        "zero_sum_max_abs": zero_error,
        "projector_max_abs": projector_error,
        "valid": bool(max(orth_error, zero_error, projector_error) <= atol),
    }
