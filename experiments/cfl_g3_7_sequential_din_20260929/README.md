# CFL–UEP G3.7 — Sequential Active Closure / DIN Policy

G3.6 synthesized one intervention but exposed the one-bit ceiling of a single binary observation. G3.7 makes the experiment sequential and response-adaptive.

After every response, the compatible model fiber is recomputed. TOS then recomputes its Phi geometry and synthesizes the next intervention. The matched `TOS_NO_DIN_REENTRY` ablation freezes the initial Phi geometry and chooses an open-loop batch without posterior-conditioned re-entry.

The strongest comparator is exact finite-horizon dynamic programming over every linearly realizable binary partition of the current finite fiber.

Local development result before remote replication:
- at H=4 TOS reaches the exact attainable closure frontier: 97.9167% closure, 0.0208333 residual bits;
- matched no-reentry remains at 92.1875% closure and 0.0768484 bits;
- TOS-minus-no-reentry residual entropy = -0.0560150 bits, bootstrap 95% CI [-0.1080984,-0.0143484];
- TOS-minus-no-reentry closure = +5.7292 pp, CI [+1.5625,+10.9375] pp;
- exact DP reaches the same H=4 closure/entropy but uses 1.67708 expected interventions versus 2.00521 for TOS; cost delta +0.328125, CI [+0.20833,+0.46875].

Thus re-entry has a local operational effect inside the matched TOS architecture, while TOS-specific non-reducibility is not supported. Two active tasks also contain four truth branches that remain non-identifiable under the entire admissible intervention class; their residual entropy is preserved rather than falsely promoted.

Authority NONE; promotion/canonization/merge blocked.
