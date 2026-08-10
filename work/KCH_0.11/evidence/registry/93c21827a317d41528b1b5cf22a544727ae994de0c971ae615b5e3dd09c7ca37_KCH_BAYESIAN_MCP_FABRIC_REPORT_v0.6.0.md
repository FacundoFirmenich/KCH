# KwanCode KCH Bayesian MCP Fabric v0.6.0

## Correction

The previous enterprise evidence minimizer is not QAS. It remains a potentially
useful evidence-support operator, but it must not inherit the QAS name.

QAS is a logit-space localization operator. At each generation step it:

1. obtains native pre-softmax logits;
2. executes the selected TALM/TALON or other full operator;
3. computes native probabilities;
4. measures absolute operator displacement;
5. weights displacement by sqrt(p(1-p)), producing Fisher-like
   counterfactual energy;
6. selects native support reaching the baseline mass target;
7. selects operator support reaching the counterfactual-energy target;
8. unions both supports with native top-1;
9. applies full-operator logits only inside that union;
10. leaves native logits unchanged outside it;
11. optionally projects native top-1 back when the localized intervention
    changed it;
12. records mask fraction, retained energy and divergence.

The v0.6 implementation reproduces these semantics numerically from aligned
base and full-operator logits. Model generation requires a runtime exposing
pre-softmax logits. Closed APIs cannot execute QAS internally.

## MCP fabric

- kwancode-qas-mcp: numeric QAS localization and paired-trace certification.
- kwancode-probes-mcp: pre-freeze counterfactual probe contract.
- kwancode-bayes-rds-mcp: six-axis local posterior authority and backend gate.
- kwancode-kch-mcp: orchestration and active ASK/PROBE/VERIFY/DEFER cycle.
- kwancode-zph-mcp: post-outcome cartography, parent immutable.
- kwancode-obl-mcp: future-only posterior memory.
- kwancode-custody-mcp: exact identity, correlation and append-only evidence.

## Bayesian cycle applied to KCH

prior OBL
-> pre-output mechanical probes
-> preliminary RDS
-> active information acquisition
-> final local RDS
-> immutable route
-> QAS/full execution gate
-> outcome and adjudication
-> ZPH cartography
-> typed evidence admission
-> next-round OBL

QAS is an execution-support operator inside this cycle. It is not itself the
Bayesian learner, the router, ZPH or an organisational document selector.

## Current execution boundary

The current environment has no Torch, JAX or NumPyro. Numeric QAS localization
is executable because it consumes already-produced aligned logits. Live model
intervention and advanced posterior fitting remain fail-closed. No empirical
KCH/QAS result is claimed by this release.