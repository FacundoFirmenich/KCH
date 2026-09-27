# RDSS Temporal Common-State SHADOW Gate v0.1

TALON mass-right (TMR) is the fixed generation authority. SHADOW probes are
disposable, sample no token, and cannot mutate the active prefix, RNG, cache,
processor state, or active generation path.

[![Open In Kaggle](https://kaggle.com/static/images/open-in-kaggle.svg)](https://kaggle.com/kernels/welcome?src=https://github.com/FacundoFirmenich/KCH/blob/main/experiments/rdss_temporal_shadow/v0_1/RDSS_TEMPORAL_SHADOW_GATE_V0_1.ipynb)

## Verified evidence state

- **G1a non-interference: PASS**
  - 10 prompts / 20 paired rows.
  - Exact fixed-TMR vs TMR+SHADOW token identity.
  - Zero identity failures.
- **G1b development pilot checkpoint: PASS**
  - 60 counterfactual rows.
  - 15/15 complete four-action common-state groups.
  - TMR wins 14/15 groups.
  - The only positive residual pocket is `p02@step0`: TALON mass-left gains
    `+0.30` automatic utility over TMR, from semantic score only.
  - Protected reserve `p07-p10`: untouched.
- Durable receipt:
  [G1B_PILOT_CHECKPOINT_SEED14.json](./G1B_PILOT_CHECKPOINT_SEED14.json)
- Kaggle executed notebook:
  https://www.kaggle.com/code/fjfmad/rdss-temporal-shadow-g1b-pilot-seed14/edit

## Current scientific decision

Do **not** fit or promote a rescue router from one positive group. TMR remains the
authority. The observed `p02@step0` pocket advances only to a locked,
development-only seed replication. If it does not replicate, discard the pocket.

The next gate is defined in
[G1C_P02_STEP0_REPLICATION_SPEC.json](./G1C_P02_STEP0_REPLICATION_SPEC.json).
The notebook now supports an exact `CAMPAIGN_PROMPT_IDS` filter so targeted
replication does not spend GPU on unrelated prompts or touch the reserve.

## Execution order

1. Keep TMR as generation authority and verify exact SHADOW non-interference.
2. Run the locked `p02` replication on seeds 28 and 42.
3. Require complete four-action common-state groups and preserve branch seeds.
4. Apply the pre-registered G1c decision rule.
5. Only if G1c passes, expand development evidence and fit a cheap screen.
6. Freeze all hashes, coefficients, thresholds, seeds, budget, and split.
7. Evaluate the protected reserve exactly once.

Historical results and post-hoc Z are descriptive only and cannot authorize a
current switch. TALON mass-left is the primary rescue; TALM mass-right-soft is
secondary; baseline is the valid fail-closed fallback. TALM-left remains
sensor/control-only.
