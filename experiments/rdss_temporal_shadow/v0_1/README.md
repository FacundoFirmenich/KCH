# RDSS Temporal Common-State SHADOW Gate v0.1

TALON mass-right (TMR) is the fixed generation authority. SHADOW probes are
disposable, sample no token, and cannot mutate the active prefix, RNG, cache,
processor state, or active generation path.

[![Open In Kaggle](https://kaggle.com/static/images/open-in-kaggle.svg)](https://kaggle.com/kernels/welcome?src=https://github.com/FacundoFirmenich/KCH/blob/main/experiments/rdss_temporal_shadow/v0_1/RDSS_TEMPORAL_SHADOW_GATE_V0_1.ipynb)

## Verified evidence

### G1a — exact non-interference: PASS

- 10 prompts / 20 paired fixed-TMR and TMR+SHADOW rows.
- Exact generated-token identity.
- Zero identity failures.

### G1b — complete development p01-p06: COMPLETE

- 76 counterfactual rows; 19/19 complete four-action common-state groups.
- Mean automatic utility: TMR `0.41598`, baseline `0.40545`,
  TALM mass-right-soft `0.40545`, TALON mass-left `0.38214`.
- TMR wins 18/19 groups.
- The only residual, `p02@step0` (+0.30 for TALON mass-left), failed both
  locked new-seed replications: seed 28 `0.00`, seed 42 `0.00`.
- Therefore no rescue screen or router was authorized.

Receipts:

- [G1B development complete](./G1B_DEVELOPMENT_COMPLETE_SEED14.json)
- [G1c locked replication spec](./G1C_P02_STEP0_REPLICATION_SPEC.json)
- [G1c replication result](./G1C_P02_STEP0_REPLICATION_RESULT.json)

### G2 — frozen protected reserve p07-p10: SAFETY PASS, NULL EFFECT

The policy was frozen as `always_talon_mass_right` before opening the reserve.

- 8 paired campaign rows; exact non-interference PASS.
- 52 counterfactual rows; 13/13 complete common-state groups.
- Primary endpoint, mean TMR minus baseline utility: **0.000**.
- Contract-pass rate: TMR `2/13`; baseline `2/13`.
- Harmful TMR groups versus baseline: `0/13`.
- TMR is an oracle co-winner in `13/13`, but a strict winner in `0/13`;
  every group has zero oracle headroom over baseline.
- Formal no-harm gate: PASS.
- Performance-uplift claim: **not supported**.
- The reserve is consumed and cannot be used for tuning.

Receipts:

- [Frozen policy](./G2_ALWAYS_TMR_POLICY_FREEZE.json)
- [Protected-reserve result](./G2_PROTECTED_RESERVE_RESULT.json)

## Scientific decision

This gate supports a clean paper claim about exact SHADOW non-interference and a
frozen policy with no reserve harm. It does **not** support a reserve performance
improvement claim: the protected reserve has no action-discriminating headroom.

The active next gate is G3 external validity. The stale split-emission bug is
repaired in the canonical source; the historical G2 receipt remains immutable
and explicitly records the observed label. G3 now has a locked blueprint for
public, objective benchmarks with a new disjoint reserve and nonzero action
headroom. Do not reopen p07-p10 or fit on their outcomes.

G3 specifications:

- [Machine-readable blueprint](./G3_EXTERNAL_VALIDITY_SPEC.json)
- [Execution protocol](./G3_EXTERNAL_VALIDITY_PROTOCOL.md)

## Contract

- TMR is the generation authority.
- TALON mass-left is the primary rescue candidate, but currently disabled.
- TALM mass-right-soft is secondary and currently disabled.
- Baseline is the valid fail-closed comparator.
- TALM-left remains sensor/control-only.
- Post-hoc Z and reserve outcomes never authorize a current action.

## Auditable source

The six files embedded by the Kaggle notebook are also checked in under `config/`,
`src/`, and `upstream/`. The notebook and extracted source carry the same repaired
protected-reserve split emission.
