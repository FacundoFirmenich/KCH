# RDSS Temporal Common-State SHADOW Gate v0.1

TALON mass-right is the fixed generation authority. SHADOW probes are disposable,
sample no token, and cannot mutate the active prefix, RNG, cache, or processor state.

[![Open In Kaggle](https://kaggle.com/static/images/open-in-kaggle.svg)](https://kaggle.com/kernels/welcome?src=https://github.com/FacundoFirmenich/KCH/blob/main/experiments/rdss_temporal_shadow/v0_1/RDSS_TEMPORAL_SHADOW_GATE_V0_1.ipynb)

## Current evidence state

- GitHub Actions scientific preflight: **PASS**
- Workflow run: https://github.com/FacundoFirmenich/KCH/actions/runs/36271895877
- Notebook commit: `869c9dc4d372220514813be7f8ac9064e2f4f668`
- Workflow commit: `1e49c1cb56a33b66f8fd23febb77e2cc016b1606`
- Prospective state: `GPU_PENDING`
- Protected reserve touched: **no**

## Execution order

1. Open the notebook through the Kaggle badge.
2. Run G1a with `RUN_DEVELOPMENT_COUNTERFACTUALS = False`.
3. Require exact token identity between fixed TMR and TMR+SHADOW.
4. Only after G1a passes, enable counterfactuals on development prompts.
5. Freeze policy, coefficients, thresholds, seeds, budget, split, and hashes.
6. Evaluate the protected reserve exactly once.

Historical results and post-hoc Z are descriptive only and cannot authorize a
switch. TALON-left is the primary rescue; TALM-right is secondary; baseline is
the valid fail-closed fallback. TALM-left remains sensor/control-only.
