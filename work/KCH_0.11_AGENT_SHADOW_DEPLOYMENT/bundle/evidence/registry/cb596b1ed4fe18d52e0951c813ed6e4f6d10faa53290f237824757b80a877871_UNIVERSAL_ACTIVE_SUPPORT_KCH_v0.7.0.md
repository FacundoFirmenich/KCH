# Universal active support for KCH v0.7.0

This subsystem applies the logic analogous to QAS at the harness level without
requiring logits.

For any model or organisational system, the harness decomposes the available
support into typed units: evidence, instructions, constraints, tool results,
actions, sensors or data cells.

It estimates two distinct quantities:

1. baseline mass: native relevance, authority or routing weight;
2. counterfactual influence energy: how much removing or perturbing the unit
   changes the decision, output, action or contract.

The active support is the union of:

- units reaching the baseline-mass target;
- units reaching the counterfactual-energy target;
- mandatory invariants.

The harness executes on that localized support and compares it with the full
execution. If decision, contract and the required exact or verified output are
preserved, the localized route is authorized. Otherwise support expands in
ranked batches. When no expansion remains, the system requires full execution
or abstains.

This is universally applicable through black-box counterfactual calls. It is a
new subsystem inspired by QAS logic, not a claim that QAS itself works without
logits. Its name remains descriptive and non-canonical pending author approval.