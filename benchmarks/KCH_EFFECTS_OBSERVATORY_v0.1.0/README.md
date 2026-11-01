# KCH Contrastive Effects Observatory v0.1.0

This is a fail-closed evidence compiler and activation governor for the KCH research programme. It does not generate new model answers, infer provider metadata, or promote a harness from descriptive scores. It reads the three canonical KCH prepilot evaluations already preserved in GitHub, normalizes their changing schemas, retains failed condition-integrity gates, computes only admissible paired summaries, and emits a traceable activation receipt.

## Historical result recovered from GitHub

| Case | Condition integrity | Baseline | KCH candidate | Admissible conclusion |
|---|---|---:|---:|---|
| KCH-PREPILOT-001 | invalid | 95/95 | 95/95 | no comparative estimate |
| KCH-PREPILOT-002 | pass, one non-randomized pair | 95/95 | 95/95 | descriptive tie |
| KCH-PREPILOT-003 | pass, one non-randomized pair | 100/100 | 100/100 | descriptive tie |

The two admissible pairs contain no directional disagreement. Under the same Beta(1,1) directional model already implemented in UnlikelyLOOP, `P(KCH better)=0.5` and the 95% interval of conditional advantage remains approximately `[-0.95, +0.95]`: the posterior learned nothing from two ties. This is not evidence that KCH has no value; it is evidence that the existing rubric did not discriminate and that the executions omitted the metrics needed to assess time, cost, tokens, corrections, task resolution, human utility, and avoided errors.

## Activation contract

The governor separates need, recommendation, authority, execution, and learning:

1. A deterministic need score is computed from risk, coupling, provenance need, authority sensitivity, and recovery need.
2. User policy is one of `NEVER`, `ASK`, or `AUTO_BOUNDED`.
3. An explicit one-run request can authorize one run; a high need score alone never can.
4. `AUTO_BOUNDED` remains blocked until the preregistered evidence gate passes: at least 20 admissible future-only pairs, at least five discordant pairs, posterior probability above 0.95, positive lower credible bound, and complete cost/latency receipts.
5. Budget at or below the user reserve fails closed before activation.
6. Every decision emits a hash-bound pre-execution receipt; actual provider usage must be supplied later in a post-execution receipt and is never invented.

The public example uses a 50% remaining budget, a 15% reserve and no explicit request. Its need score is `0.840`, so the deterministic result is `ASK_USER_BEFORE_USE`: high need is visible, but execution is not authorized. A private current-budget profile can be evaluated locally without publishing account state.

## Run

From this directory in the KCH repository:

```bash
python observatory.py analyze \
  ../KCH_PREPILOT_001/evaluation.json \
  ../KCH_PREPILOT_002/evaluation.json \
  ../KCH_PREPILOT_003/evaluation.json \
  --json results/effects_report.json \
  --markdown results/EFFECTS_REPORT.md

python observatory.py decide \
  --evidence results/effects_report.json \
  --profile activation_profile.example.json \
  --output results/ACTIVATION_RECEIPT_EXAMPLE.json

python -m unittest -v test_observatory.py
```

The local package carries exact copies of the three GitHub evaluations only to make the delivered artifact self-verifying. The GitHub integration uses the existing canonical files in `benchmarks/KCH_PREPILOT_001..003` and does not duplicate them.

## Scientific boundary

- Receipt size is not token usage, runtime, cost, quality, or utility.
- A tie on a saturated rubric is not proof of equivalence.
- A recommendation is not authority.
- Explicit policy is not proof that an effect occurred.
- A post hoc observation does not rewrite a pre-outcome freeze.
- No HHC/H2C construct is used or reinstated. The previous detour is retained only as superseded history.

The numerical Beta routines are adapted from the user's own `UnlikelyLOOP/baselines/lmd_dgs_cpu_frontier_v0_8/src/lmd_dgs/paired_bayes.py`; the activation boundary aligns with KCH TokenMaster's existing principle that recommendation is not authority.
