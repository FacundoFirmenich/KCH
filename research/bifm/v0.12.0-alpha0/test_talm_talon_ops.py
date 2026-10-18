#!/usr/bin/env python3
"""Deterministic invariants for BIFM v0.12 TALM/TALON reimplementation."""
from __future__ import annotations

import torch

from talm_talon_ops import (
    talm_mass_right_soft,
    talon_mass_right,
    talon_mass_right_no_preserve,
    temperature_control,
)


def main() -> None:
    torch.manual_seed(20261018)
    logits = torch.randn(8, 2048)
    base_top = logits.argmax(dim=-1)
    temp = temperature_control(logits, 0.8)
    temp_top = temp.argmax(dim=-1)
    assert torch.equal(base_top, temp_top)

    talm, talm_tel = talm_mass_right_soft(logits)
    talon, talon_tel = talon_mass_right(logits)
    actuator, actuator_tel = talon_mass_right_no_preserve(logits)

    assert torch.equal(talm.argmax(dim=-1), base_top)
    assert torch.equal(talon.argmax(dim=-1), temp_top)
    assert talm_tel.changed_global_top1 == 0
    assert talon_tel.changed_global_top1 == 0
    assert talm_tel.constant_shift_residual_mean > 1e-6
    assert talon_tel.constant_shift_residual_mean > 1e-6
    assert actuator_tel.constant_shift_residual_mean > 1e-6
    assert not torch.allclose(talm, logits)
    assert not torch.allclose(talon, temp)
    assert not torch.allclose(actuator, temp)
    assert talm_tel.selected_left >= 8
    assert talm_tel.selected_right >= 8
    assert talon_tel.selected_right >= 8

    # Softmax invariance audit: the transformed distribution must differ from
    # its matched control, not merely by an all-token constant.
    assert not torch.allclose(torch.softmax(talm, -1), torch.softmax(logits, -1))
    assert not torch.allclose(torch.softmax(talon, -1), torch.softmax(temp, -1))
    assert not torch.allclose(torch.softmax(actuator, -1), torch.softmax(temp, -1))
    print("PASS: TALM/TALON operator invariants and nontriviality")


if __name__ == "__main__":
    main()
