# Adverse history — BIFM v0.10

## AH-010-001 — Top-1 dramatically overstates invisibility

The Qwen lattice shows that large top-1 collision regions can collapse under ranking, quantized-probability or vocabulary-level operators. Top-1 results must never be presented as behaviorally exhaustive.

## AH-010-002 — null frontier entries are grid bounds

A null entry means no nonzero tested epsilon remained invisible. It implies a tested-grid upper bound below 0.05, not a proof that the continuous frontier is zero.

## AH-010-003 — right censoring remains

Entries equal to 2.00 are lower bounds at the largest tested grid value. They are not exact continuous frontier estimates.

## AH-010-004 — nominal scale is not realized effect

The earlier OLMo scale-3 result had negligible post-layer displacement, while layer-14 ablation produced approximately 70% displacement. Raw intervention scale is not comparable across architecture, layer or intervention family.

## AH-010-005 — architecture-induced intervention symmetry

OLMo2 post-feedforward RMSNorm approximately cancels positive MLP scaling. The earlier weak scaling result therefore partly reflected the realization map collapsing distinct control commands. Future benchmarks must quotient intervention controls by architecture-induced symmetries or report realized effects explicitly.

## AH-010-006 — tiny negative JS values are floating-point error

Several development-search JS values were negative by approximately 1e-8 although true Jensen–Shannon divergence is nonnegative. They were far below the preregistered floor and did not affect selection. Raw values remain in receipts; future presentation code should clamp only for display.

## AH-010-007 — one deterministic observation sample is not a population estimate

The contraction result is exact for the frozen nested samples, but no population-level sampling claim follows. Multiple independently hashed real-data samples remain necessary.

## AH-010-008 — the operator lattice is engineered, not ontologically unique

The cumulative signatures are valid declared refinements. They are not claimed to be the unique or cognitively privileged hierarchy of behavior.
