# KwanBlocks Helical Lift v0.8.2 — dynamic marked-process adjudication

This successor executes the dynamic signed-orientation transport gate on the two cohorts sealed by v0.8.1. It does not alter the locked protocol, thresholds, cohort selection or test partition.

## Result

```text
OUTCOME                         NONHELICAL_DYNAMIC_RIVAL_SUFFICIENT_WITHIN_CONSERVATIVE_PARENT_GRAPH
POSITIVE PRIMARY COHORTS        0 / 2
PHYSICAL HELICITY               NOT_DEMONSTRATED
UNIVERSAL ABSENCE OF HELICITY   NOT_ESTABLISHED
```

| Cohort | test n | log-score gain/edge | RMSE gain | ΔBIC H−B |
|---|---:|---:|---:|---:|
| Bay Area–Hayward/Calaveras | 9,320 | −0.000294641 | −0.291649% | +417.139 |
| Parkfield–central SAF | 5,825 | +0.003443123 | +0.836872% | +123.285 |

The locked minima were `0.02` nats/edge and `5%` RMSE improvement, with `ΔBIC≤−10` and the null/stability gates required conjunctively. Bay Area worsens. Parkfield retains a weak residual association but fails effect size, complexity and parent-graph stability; it is not a positive result.

## Scope boundary

The executed candidate-parent graph is the conservative same-external-fault-segment subset. The full cross-segment fault-network graph remains unexecuted, so the complete network claim is not adjudicated. Static-cloud, static-piecewise and this conservative dynamic model class are now all unsupported within their respective tested jurisdictions; this is not a universal proof of nonhelicity.

## Reproducibility

- 72-cell calibration grid recomputed cellwise in isolated processes;
- calibration selection content-addressed before held-out test evaluation;
- primary test metrics independently replayed exactly;
- complete null and stability battery preserved from one finished execution;
- monolithic heavy replay stalled after reproducing calibration and primary test, and that boundary is disclosed rather than hidden;
- independent package validation: `2,587/2,587 PASS`.

## KwanBlocks

```text
graph
kbg:ae5c4b86cd336b94aad61bbd0142155e69ea01d89f039f616d7d9fc9cac75dda

ledger head
677c7ed4af2873a75857127e4b99ac4072ec500d5aceb5e0bf3b83c748b2e128

blocks / edges / events
190 / 366 / 561

validation
2,775 / 2,775 PASS
```

```text
PROMOTION        BLOCKED
CANONICALIZATION BLOCKED
MERGE            NOT PERFORMED
AUTHORITY        NONE
```

Detailed identities, metrics, hashes and limits are in `REMOTE_RESULT_INDEX.json`.
