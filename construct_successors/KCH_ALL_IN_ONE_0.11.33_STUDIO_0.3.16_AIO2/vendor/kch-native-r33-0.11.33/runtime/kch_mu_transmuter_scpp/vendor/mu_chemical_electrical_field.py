"""Endocrine-field chemical-electrical μ cell.

The external signal is encoded once as a global chemical field.  It is broadcast
without acquiring authority by itself and is received heterogeneously through a
target-specific receptor map.  Electrical feedback remains secondary and the
electrical state has no direct external-drive bypass.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn


@dataclass(frozen=True)
class ChemicalElectricalFieldConfig:
    dim: int = 8
    chemical_dim: int = 8
    global_dim: int = 4
    q_types: int = 4
    nodes: int = 4
    electrical_feedback_gain: float = 0.1
    seed: int = 101

    def __post_init__(self) -> None:
        if min(self.dim, self.chemical_dim, self.global_dim, self.nodes) < 1:
            raise ValueError("state dimensions and nodes must be positive")
        if self.q_types != 4:
            raise ValueError("chemical-electrical field μ requires Q4")
        if self.dim != self.chemical_dim:
            raise ValueError("dim and chemical_dim must match")
        if not 0.0 <= self.electrical_feedback_gain <= 1.0:
            raise ValueError("electrical_feedback_gain must lie in [0, 1]")


class ChemicalElectricalFieldMu(nn.Module):
    """Chemical-field-first μ with global influence and local reception."""

    def __init__(
        self,
        config: ChemicalElectricalFieldConfig = ChemicalElectricalFieldConfig(),
        dtype: torch.dtype = torch.float64,
    ) -> None:
        super().__init__()
        self.c = config
        generator = torch.Generator().manual_seed(config.seed)
        dim = config.dim
        chemical_dim = config.chemical_dim
        global_dim = config.global_dim

        def linear(input_dim: int, output_dim: int) -> nn.Linear:
            layer = nn.Linear(input_dim, output_dim, dtype=dtype)
            nn.init.xavier_uniform_(layer.weight, generator=generator)
            nn.init.zeros_(layer.bias)
            return layer

        feature_dim = 2 * dim + chemical_dim + global_dim
        receptor_input_dim = dim + chemical_dim + global_dim + config.nodes
        self.electrical_feedback = linear(feature_dim, chemical_dim)
        self.receptor = linear(receptor_input_dim, chemical_dim)
        self.chemical_kinetics = linear(2 * chemical_dim + global_dim, chemical_dim)
        self.raw_reuptake = nn.Parameter(torch.zeros(chemical_dim, dtype=dtype))
        self.raw_receptor_threshold = nn.Parameter(
            torch.zeros(chemical_dim, dtype=dtype)
        )
        self.raw_field_scale = nn.Parameter(torch.zeros(chemical_dim, dtype=dtype))
        self.q_logits = linear(feature_dim, 4)
        self.conductance = linear(feature_dim, 4 * dim)
        self.q_close = linear(4 * dim, dim)
        self.node = linear(2 * dim + global_dim, dim)
        self.global_update = linear(chemical_dim + global_dim, global_dim)

    def forward(
        self,
        e: Tensor,
        z: Tensor | None = None,
        h: Tensor | None = None,
        chemical_field: Tensor | None = None,
        *,
        field_clamped: bool = False,
        receptor_homogenized: bool = False,
        electrical_feedback_clamped: bool = False,
    ):
        if e.ndim != 3 or e.shape[-1] != self.c.dim or not torch.isfinite(e).all():
            raise ValueError("e must be finite B,N,D")
        batch, nodes, dim = e.shape
        if nodes != self.c.nodes:
            raise ValueError("node count does not match the frozen receptor map")
        chemical_dim = self.c.chemical_dim
        global_dim = self.c.global_dim
        if z is None:
            z = torch.zeros(
                batch,
                nodes,
                nodes,
                chemical_dim,
                dtype=e.dtype,
                device=e.device,
            )
        if h is None:
            h = torch.zeros(batch, global_dim, dtype=e.dtype, device=e.device)
        if chemical_field is None:
            chemical_field = torch.zeros(
                batch, chemical_dim, dtype=e.dtype, device=e.device
            )
        if z.shape != (batch, nodes, nodes, chemical_dim):
            raise ValueError("z shape mismatch")
        if h.shape != (batch, global_dim):
            raise ValueError("h shape mismatch")
        if chemical_field.shape != (batch, chemical_dim):
            raise ValueError("chemical_field must be B,K")

        pre = e[:, :, None, :].expand(-1, -1, nodes, -1)
        post = e[:, None, :, :].expand(-1, nodes, -1, -1)
        global_pair = h[:, None, None, :].expand(-1, nodes, nodes, -1)
        chemical = torch.sigmoid(z)

        target_identity = torch.eye(
            nodes, dtype=e.dtype, device=e.device
        )[None, None, :, :].expand(batch, nodes, -1, -1)
        if receptor_homogenized:
            target_identity = torch.full_like(target_identity, 1.0 / nodes)
        receptor_logits = self.receptor(
            torch.cat((post, chemical, global_pair, target_identity), dim=-1)
        )
        receptor_gate = torch.sigmoid(
            receptor_logits + self.raw_receptor_threshold[None, None, None, :]
        )
        field_scale = torch.nn.functional.softplus(self.raw_field_scale)[
            None, None, None, :
        ]
        field_carrier = torch.tanh(
            chemical_field[:, None, None, :] * field_scale
        ).expand(-1, nodes, nodes, -1)
        if field_clamped:
            field_carrier = torch.zeros_like(field_carrier)
        received_field = receptor_gate * field_carrier

        feedback = torch.tanh(
            self.electrical_feedback(
                torch.cat((pre, post, chemical, global_pair), dim=-1)
            )
        )
        if electrical_feedback_clamped:
            feedback = torch.zeros_like(feedback)
        primary_increment = torch.tanh(
            self.chemical_kinetics(
                torch.cat((chemical, received_field, global_pair), dim=-1)
            )
        )
        reuptake = torch.sigmoid(self.raw_reuptake)[None, None, None, :]
        z_next = (
            (1.0 - reuptake) * z
            + primary_increment
            + self.c.electrical_feedback_gain * feedback
        )
        chemical_next = torch.sigmoid(z_next)
        features = torch.cat((pre, post, chemical_next, global_pair), dim=-1)
        posterior = torch.softmax(self.q_logits(features), dim=-1)
        currents = self.conductance(features).reshape(
            batch, nodes, nodes, 4, dim
        )
        typed = (posterior[..., None] * currents).reshape(
            batch, nodes, nodes, 4 * dim
        )
        self_edge = torch.eye(nodes, dtype=torch.bool, device=e.device)[
            None, :, :, None
        ]
        typed = typed.masked_fill(self_edge, 0)
        chemical_visible = chemical_next.masked_fill(self_edge, 0)
        posterior = posterior.masked_fill(self_edge, 0)
        receptor_visible = receptor_gate.masked_fill(self_edge, 0)
        received_visible = received_field.masked_fill(self_edge, 0)
        message = self.q_close(typed).sum(1)
        chemical_global = chemical_visible.sum((1, 2)) / max(
            nodes * (nodes - 1), 1
        )
        h_next = torch.tanh(
            self.global_update(torch.cat((chemical_global, h), dim=-1))
        )
        e_next = torch.tanh(
            self.node(
                torch.cat(
                    (e, message, h_next[:, None, :].expand(-1, nodes, -1)),
                    dim=-1,
                )
            )
        )
        return e_next, z_next, h_next, {
            "chemical": chemical_visible,
            "q_probabilities": posterior,
            "typed_currents": typed,
            "receptor_gate": receptor_visible,
            "received_field": received_visible,
            "electrical_feedback": feedback.masked_fill(self_edge, 0),
            "chemical_primary_increment": primary_increment.masked_fill(
                self_edge, 0
            ),
        }
