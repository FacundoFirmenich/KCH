from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np

from .canonical import attach_hash
from .contracts import BlockBundle


@dataclass(frozen=True, slots=True)
class LayerByteReceipt:
    process_id: str
    ordered_blocks: tuple[int, ...]
    layer_1: tuple[tuple[Any, Any], ...]
    layer_2: tuple[tuple[Any, Any], ...]
    layer_3: tuple[tuple[Any, Any], ...]
    transformer_track: tuple[Any, ...]
    transmuter_v02_track: tuple[Any, ...]
    transmuter_v032_track: tuple[Any, ...]
    status: str
    claim_boundary: str

    def to_payload(self) -> dict[str, Any]:
        return attach_hash(asdict(self))

    def numeric_layer(self, layer: int) -> np.ndarray:
        source = {1: self.layer_1, 2: self.layer_2, 3: self.layer_3}.get(layer)
        if source is None:
            raise ValueError("layer must be 1, 2 or 3")
        value = np.asarray(source, dtype=np.float64)
        if not np.all(np.isfinite(value)):
            raise ValueError("layer contains non-finite or non-numeric values")
        return value


def build_layer_byte(blocks: Iterable[BlockBundle]) -> LayerByteReceipt:
    ordered = sorted(tuple(blocks), key=lambda item: item.jurisdiction.block_id)
    if len(ordered) != 8 or tuple(item.jurisdiction.block_id for item in ordered) != tuple(range(1, 9)):
        raise ValueError("an octet requires exactly the ordered blocks 1..8")
    process_ids = {item.jurisdiction.process_id for item in ordered}
    if len(process_ids) != 1:
        raise ValueError("all blocks must belong to one cosignificant process")
    semantic = {
        (
            item.jurisdiction.task,
            item.jurisdiction.operation,
            item.jurisdiction.horizon_delay,
            item.jurisdiction.interference,
            item.jurisdiction.phase,
        )
        for item in ordered
    }
    if len(semantic) != 1:
        raise ValueError("block order cannot conceal multiple semantic jurisdictions")
    return LayerByteReceipt(
        process_id=next(iter(process_ids)),
        ordered_blocks=tuple(range(1, 9)),
        layer_1=tuple((item.values["mu_eq_obsolete"], item.values["gru_current"]) for item in ordered),
        layer_2=tuple((item.values["gru_obsolete"], item.values["mu_qe_current"]) for item in ordered),
        layer_3=tuple((item.values["mu_qe_obsolete"], item.values["mu_eq_current"]) for item in ordered),
        transformer_track=tuple(item.values["transformer"] for item in ordered),
        transmuter_v02_track=tuple(item.values["transmuter_v02"] for item in ordered),
        transmuter_v032_track=tuple(item.values["transmuter_v032"] for item in ordered),
        status="OBSERVED_ORDERED_OCTET",
        claim_boundary="Eight ordered blocks of one process; no irreducibility, emergence or universal antisymmetry is implied by construction.",
    )


def complete_layer1_crossing(receipt: LayerByteReceipt) -> dict[str, Any]:
    x = receipt.numeric_layer(1).reshape(16)
    difference = x[:, None] - x[None, :]
    finite = np.isfinite(difference)
    return attach_hash({
        "schema": "kch.layer1-crossing.v0.1.0",
        "shape": [16, 16],
        "directed_difference": difference.tolist(),
        "finite_cells": int(finite.sum()),
        "diagonal_exact_zero": bool(np.array_equal(np.diag(difference), np.zeros(16))),
        "antisymmetric_numeric_identity": bool(np.allclose(difference, -difference.T, atol=0.0, rtol=0.0)),
        "claim_boundary": "Arithmetic crossing of one observed layer; it is not evidence of a transported antisymmetric law.",
    })

