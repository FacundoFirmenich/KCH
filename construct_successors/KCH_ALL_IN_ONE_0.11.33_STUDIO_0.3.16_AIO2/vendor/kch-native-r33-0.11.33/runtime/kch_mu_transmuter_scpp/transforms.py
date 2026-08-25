from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .canonical import attach_hash


def haar_matrix_8() -> np.ndarray:
    def recursive(n: int) -> np.ndarray:
        if n == 1:
            return np.ones((1, 1), dtype=np.float64)
        half = recursive(n // 2)
        top = np.kron(half, np.asarray([[1.0, 1.0]])) / np.sqrt(2.0)
        bottom = np.kron(np.eye(n // 2), np.asarray([[1.0, -1.0]])) / np.sqrt(2.0)
        return np.vstack((top, bottom))
    return recursive(8)


def dct2_matrix_8() -> np.ndarray:
    n = 8
    result = np.empty((n, n), dtype=np.float64)
    for k in range(n):
        alpha = np.sqrt(1.0 / n) if k == 0 else np.sqrt(2.0 / n)
        for index in range(n):
            result[k, index] = alpha * np.cos(np.pi * (index + 0.5) * k / n)
    return result


@dataclass(frozen=True, slots=True)
class TransformResult:
    method: Literal["HAAR", "DCT_II", "DFT"]
    coefficients: Any
    reconstruction_max_abs_error: float
    energy_input: float
    energy_coefficients: float
    cyclic_justified: bool
    status: str

    def to_payload(self) -> dict[str, Any]:
        return attach_hash({
            "method": self.method,
            "coefficients": self.coefficients,
            "reconstruction_max_abs_error": self.reconstruction_max_abs_error,
            "energy_input": self.energy_input,
            "energy_coefficients": self.energy_coefficients,
            "cyclic_justified": self.cyclic_justified,
            "status": self.status,
        })


def transform_octet(values: Any, method: Literal["HAAR", "DCT_II", "DFT"], *, cyclic_justified: bool = False) -> TransformResult:
    x = np.asarray(values, dtype=np.float64)
    if x.shape[0] != 8 or not np.all(np.isfinite(x)):
        raise ValueError("octet transform requires a finite first dimension of length eight")
    if method == "DFT" and cyclic_justified is not True:
        raise PermissionError("DFT is conditional on an explicit cyclicity justification")
    if method == "HAAR":
        matrix = haar_matrix_8()
        coefficients = np.tensordot(matrix, x, axes=(1, 0))
        reconstructed = np.tensordot(matrix.T, coefficients, axes=(1, 0))
        serial = coefficients.tolist()
    elif method == "DCT_II":
        matrix = dct2_matrix_8()
        coefficients = np.tensordot(matrix, x, axes=(1, 0))
        reconstructed = np.tensordot(matrix.T, coefficients, axes=(1, 0))
        serial = coefficients.tolist()
    elif method == "DFT":
        coefficients = np.fft.fft(x, axis=0, norm="ortho")
        reconstructed = np.fft.ifft(coefficients, axis=0, norm="ortho").real
        serial = {"real": coefficients.real.tolist(), "imag": coefficients.imag.tolist()}
    else:
        raise ValueError(method)
    return TransformResult(
        method=method,
        coefficients=serial,
        reconstruction_max_abs_error=float(np.max(np.abs(reconstructed - x))),
        energy_input=float(np.sum(x * x)),
        energy_coefficients=float(np.sum(np.abs(coefficients) ** 2)),
        cyclic_justified=cyclic_justified,
        status="EXACT_AUDITABLE_TRANSFORM_NOT_A_CLAIM",
    )

