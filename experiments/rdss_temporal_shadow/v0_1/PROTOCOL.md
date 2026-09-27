# RDSS Temporal Common-State SHADOW Gate — protocol v0.1

## Question

Can RDSS recover the small residual headroom left by fixed TALON mass-right
(TMR) without degrading TMR's dominant performance after compute and harm are
charged?

This is not a contest between TALM and TALON. TMR is the default authority.
The gate studies only when evidence is strong enough to leave it.

## Causal contract

1. Generate the prefix under TMR.
2. At frozen checkpoints, clone the same raw model logits and prefix.
3. Apply each rescue operator in SHADOW. A probe samples no token, consumes no
   generation RNG, and mutates neither the TMR processor nor the prefix.
4. In stage G1a (`SHADOW_ONLY`), generation always remains under TMR. Exact
   token identity with the fixed-TMR arm is mandatory.
5. On development prompts only, launch counterfactual continuations from the
   captured common prefix to label residual headroom and fit the cheap screen
   plus value model.
6. Freeze hashes, coefficients, thresholds, split, and rescue ladder.
7. Evaluate once on the protected reserve. Post-hoc oracle results are
   descriptive and cannot authorize a switch.

## Authority ladder

`talon_mass_right` is the fixed default. The ordered rescue set is:

1. `talon_mass_left`
2. `talm_mass_right_soft`
3. `baseline`

`ABSTAIN` and `ASK` are formal outputs. Missing, immature, out-of-distribution,
or unsafe evidence fails closed to TMR.

## Arms

| Arm | Purpose | May affect tokens? |
|---|---|---:|
| Fixed TMR | Dominant baseline | Yes, TMR only |
| TMR + SHADOW | Non-interference and feature capture | No relative to fixed TMR |
| Cheap screen only | Screen value and calibration | Only after freeze |
| Screen + SHADOW | Primary RDSS policy | Only after freeze |
| Probe-all SHADOW | Compute-cost upper control | No in G1a |
| Coverage-matched random | Trigger control | After freeze |
| Post-hoc oracle | Residual-headroom ceiling | Never |

## Primary estimand

For a frozen rescue candidate \(a\) at history \(H_t\):

\[
\operatorname{VoC}_{LCB}(a, H_t) =
LCB_{95}[U(a)-U(TMR)\mid H_t] - C_{probe}
- \lambda_R\,UCB_{95}[P(\mathrm{harm})].
\]

Switch only when the cheap screen is positive, the policy is frozen,
`VoC_LCB > 0`, and the harm UCB is no greater than the predeclared delta.

## Promotion gate

The gate passes only if all conditions hold on the protected reserve:

- fixed TMR and SHADOW-only outputs are token-identical;
- paired utility of screen+SHADOW exceeds fixed TMR after charged cost;
- the lower confidence bound of the improvement is positive;
- harm UCB95 is within the configured delta;
- improvement is not explained by a single prompt, seed, or benchmark family;
- all decisions are reconstructible from frozen logs and hashes.

The 10-prompt × 3-seed historical archive is a feasibility source only. It
cannot promote the gate because its inline traces were produced by a different,
flat router and are not common-state TMR observations.

## Lineage rule

The executable adapter in this release reproduces the `historical_v04` operator
lineage: operator temperature 1.0, internal `preserve_top1=false`, followed by
one common external top-1 projection. The separate canonical TMR configuration
with hash `67875f7e...12a` is recorded for reference and must be evaluated as a
separate arm. Results from the two lineages must never be pooled silently.
