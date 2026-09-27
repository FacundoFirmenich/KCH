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

**G1c rejected the `p02@step0` pocket.** On seeds 28 and 42, TALON mass-left
tied TMR at `0.00`; neither new seed reproduced the seed-14 gain. Therefore no
rescue router or screen may be fit from this pocket. TMR remains the authority.

- Locked protocol:
  [G1C_P02_STEP0_REPLICATION_SPEC.json](./G1C_P02_STEP0_REPLICATION_SPEC.json)
- Executed result:
  [G1C_P02_STEP0_REPLICATION_RESULT.json](./G1C_P02_STEP0_REPLICATION_RESULT.json)

The active next gate is to complete the missing development prompt `p06`.
The notebook's exact `CAMPAIGN_PROMPT_IDS` filter avoids unrelated GPU work and
keeps the protected reserve untouched.

## Execution order

1. Keep TMR as generation authority and verify exact SHADOW non-interference.
2. Treat the executed G1c rejection as closed; do not fit a `p02@step0` rule.
3. Complete `p06` on the development split with all four actions.
4. Recompute the full p01-p06 development evidence.
5. Only if residual headroom remains supported, pre-register a new cheap screen.
6. Freeze all hashes, coefficients, thresholds, seeds, budget, and split.
7. Evaluate the protected reserve exactly once.

Historical results and post-hoc Z are descriptive only and cannot authorize a
current switch. TALON mass-left is the primary rescue; TALM mass-right-soft is
secondary; baseline is the valid fail-closed fallback. TALM-left remains
sensor/control-only.
