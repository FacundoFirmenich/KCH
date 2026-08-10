# KCH Enterprise Active Authority v0.5.0

## What changed

The operators are now applied to our target case rather than imported as
historical performance numbers.

The target is an enterprise KCH task grounded in organisational evidence, with
BIND as the first commercial setting. The active alternatives are ANSWER, ASK,
RETRIEVE, VERIFY, DEFER and ABSTAIN. Counterfactual probes establish which are
feasible before a route is frozen.

CAS is implemented as an exact bounded search over organisational evidence. It
finds the smallest evidence subset whose complete claim-by-claim decision
signature is identical to the signature obtained with the full evidence
snapshot. The certificate records the selected evidence, support fraction,
retrieval cost, full and minimal hashes, and exact-preservation status.

RDS remains the Bayesian local governor. It consumes posterior draws rather
than heuristic scores. The adapter supplies its exact action set and local
evidence state. After the outcome, the enterprise ZPH adapter emits a six-axis
EvidenceRecord targeting only the next round.

## Our prospective evidence

A matched A/B protocol is frozen. Arm A uses full context and the earlier static
answer-or-abstain KCH policy. Arm B uses counterfactual probes, active
information acquisition, exact CAS, local RDS and future-only ZPH. No outcome
has yet been observed.

Historical QAS support fractions are not target metrics and are not gates.
Our experiment will produce its own support fractions, full/local identity,
first divergence, question yield, verified completion, unsupported claims,
harm, latency and cost in each exact local jurisdiction.