# Helical Lift Theory v0.1 — formal research specification

Status: **formal successor / not a physical claim**.  The purpose is to separate a general mathematical structure of projected recurrence with hidden state drift from any particular solar, seismic, fluid, biological, social, or computational interpretation.

## 1. State, base, fiber, observation

Let the physical/informational state space be a measurable differentiable state space `E`, with an observable base `B` and a surjective projection

\[
\pi:E\to B.
\]

For `b∈B`, the fiber is `F_b=π^{-1}(b)`.  A trajectory is `X_t∈E`; the ideal projected state is `Y_t=π(X_t)`, and an instrument produces

\[
Z_t\sim \mathcal O(\cdot\mid Y_t,X_t,\eta_t),
\]

where `η_t` denotes instrument/noise state.  No inference about fiber motion is admissible unless the observation model has non-zero sensitivity to the relevant vertical/fiber directions.

## 2. Projected recurrence is not lifted recurrence

For a base metric `d_B`, an `ε_B` projected recurrence is

\[
d_B(Y_{t_1},Y_{t_2})\le \varepsilon_B,
\qquad t_2>t_1.
\]

Choose a connection or an explicitly declared transport operator `P_γ` along the projected loop `γ=Y_[t1,t2]`.  The lifted recurrence defect is

\[
\delta_F(t_1,t_2)
=
 d_F\!\left(X_{t_2},P_\gamma X_{t_1}\right),
\]

or its gauge-invariant quotient when a raw fiber coordinate is not physical.  A projected recurrence is a **lifted recurrence** only when `δ_F` is compatible with zero under the frozen uncertainty model.

This immediately excludes the logical shortcut

\[
Y_{t_1}\simeq Y_{t_2}\;\Rightarrow\;X_{t_1}\simeq X_{t_2}.
\]

## 3. Holonomy / monodromy

For a closed projected loop `γ`, parallel transport induces a holonomy element

\[
H_\gamma:F_b\to F_b.
\]

Only gauge-invariant properties of `H_γ` (for example its conjugacy class or declared invariants of that class) are candidates for physical interpretation.  Raw phase increments are not canonically meaningful without a gauge convention.

A **helical lift** is operationally a recurrent family of projected loops whose admissible holonomy has a persistent oriented translational/rotational component in fiber space and whose out-of-sample predictive or explanatory value exceeds frozen non-helical rivals.

The word *helical* therefore denotes a lift structure, not necessarily a literal Euclidean helix.

## 4. Irreversibility and wear

Let `D:E→R` be a dissipation/wear coordinate.  If the dynamics form a forward semigroup and

\[
D(X_{t_2})>D(X_{t_1})\quad\text{for every }t_2>t_1
\]

on a declared interval, exact recurrence in `E` is impossible on that interval even if the base returns arbitrarily close to its previous value.  Friction, material wear, entropy production, irreversible plastic deformation, accumulated computation cost, or other domain-appropriate monotones can instantiate `D` only when independently observed or physically justified.

## 5. Information coordinate

An information state `I_t` may be included as a fiber coordinate only after its operational definition is frozen (posterior entropy reduction, acquired measurements, ledgered evidence, learned sufficient statistic, etc.).  A return of the projected geometry with `I_{t2}>I_{t1}` is a different lifted state.  Information gain and dissipation can coexist; neither is assumed to be universally monotone without a domain-specific contract.

## 6. Candidate lift classes

The initial model class is deliberately finite:

1. **Cylinder / trivial holonomy**: projected loops close and the fiber transport is identity up to noise.
2. **Möbius / Z2 holonomy**: one loop changes orientation and two loops restore it.
3. **Helical / affine drift**: each loop accumulates a consistently oriented non-zero fiber increment.
4. **Lemniscatic / alternating lift**: first-order signed increments alternate or cancel while a predeclared second-order loop-composition invariant remains non-trivial.
5. **Generic affine holonomy rival**: non-trivial transport without the structural restrictions of the helical or lemniscatic classes.

No topology is promoted merely because its fit is visually suggestive.  If the observation operator cannot distinguish candidate classes, the mandatory outcome is `NOT_IDENTIFIABLE`.

## 7. Observability gate

For a local vertical/fiber parameter `f` and observation mean `m(f)`, define the local sensitivity Jacobian `J_F=∂m/∂f` and noise covariance `Σ`.  The fiber Fisher matrix is

\[
\mathcal I_F=J_F^\top\Sigma^{-1}J_F.
\]

If `rank(I_F)` is smaller than the dimension of the claimed fiber component, that component is not locally identifiable.  Only identifiable projections may be tested; arbitrary coefficient interpretation is forbidden.

## 8. Causal state augmentation

Let `X_t` be Markov in `E`.  The projection `Y_t=π(X_t)` need not be Markov.  Apparent memory or hysteresis in `Y_t` is therefore compatible with hidden fiber state, but it does not prove one.  A causal lift claim requires that an explicitly specified state augmentation improves intervention- or transition-level predictions out of sample relative to rival history summaries of equal information budget.

## 9. Five propositions used as gates

**P1 — Projection non-injectivity.** If `π` is non-injective, equality of projected states is insufficient to imply equality of lifted states.  This is immediate because a fiber contains at least two distinct preimages.

**P2 — Monotone obstruction to recurrence.** A strictly increasing scalar `D(X_t)` on `(t1,t2)` forbids `X_t2=X_t1`.

**P3 — Gauge covariance of holonomy.** Under a gauge transformation `g`, `H_γ` transforms by conjugation, so only conjugacy-invariant functionals can be treated as gauge-independent observables.

**P4 — Local observability obstruction.** If a non-zero vertical direction `v` lies in the null space of `J_F`, infinitesimal changes along `v` cannot be distinguished by the declared observation model to first order; a unique local lift along `v` is not identifiable.

**P5 — Projected non-Markovity is non-diagnostic.** A Markov process can have a non-Markov projection.  Therefore path dependence in the base is evidence for missing state only after simpler rival history summaries are defeated prospectively.

## 10. Falsification logic

A domain-specific Helical Lift experiment must freeze before confirmatory access:

- base and fiber variables;
- projection and observation operator;
- gauge convention and gauge-invariant reported quantities;
- rival model class;
- future-only split / independent units;
- materiality thresholds;
- null families and perturbations;
- identifiability and support floors;
- abstention rules.

Permitted terminal outcomes are:

- `HELICAL_LIFT_SUPPORTED_WITHIN_SCOPE`;
- `LEMNISCATIC_LIFT_SUPPORTED_WITHIN_SCOPE`;
- `GENERIC_NONTRIVIAL_HOLONOMY_RIVAL_SUFFICIENT`;
- `TRIVIAL_HOLONOMY_RIVAL_SUFFICIENT`;
- `UPPER_BOUND_BELOW_MATERIALITY`;
- `NOT_IDENTIFIABLE`;
- `INSUFFICIENT_SUPPORT`.

No one-domain result is licensed as a universal ontological conclusion.

## 11. Bridge to MHD

For photospheric vector magnetograms the observable state can include the CEA vector field

\[
\mathbf B(x,y,t)=(B_r,B_\theta,B_\phi),
\]

with uncertainty maps and disambiguation confidence.  Direct parity-odd candidates include current-helicity density and other declared chiral spatial operators.  The first admissible gate is not forecasting: it is **adapter observability** — proving that the raw vector segments are retrievable, coordinate conventions reconcile with SHARP metadata, and pseudoscalar/even quantities transform correctly under parity, field reversal, and proper rotations.

Only after that adapter is frozen may 2010–2025 development data be used to select a finite direct-field model family.  The 2026 holdout already used by v1.1 is not recycled for model selection.

## 12. Governance

```text
authority_ceiling       NONE
physical_helicity       NOT_EVALUATED_BY_THEORY
universal_claim         FORBIDDEN
promotion               BLOCKED
canonicalization        BLOCKED
retrospective_rewrite   FORBIDDEN
```
