# Projected Recurrence Is Not State Return: Helical Lift Theory, Monodromy, Identifiability, and Fail-Closed Scientific Computation

**Manuscript status:** corrected full working draft V5, 13 October 2026, successor to `PAPER_1_PROJECTED_RECURRENCE_HELICAL_LIFTS_V4.md`. The mathematical claims are separated from domain-specific helicity. The terminal California seismic instantiation remains closed under its declared stop rule; the historical dynamic branch carries an event-type eligibility reservation. Solar results qualify reconstruction of a photospheric proxy against products of the same underlying measurements, not independent instrumental validation. Numbered statements organize the argument and do not establish mathematical novelty. External mathematical and domain review remain required.

## Abstract

Recurrence of an observable is sometimes promoted to recurrence of the underlying state. That implication is not generally valid for a non-injective observation map; the relevance of an omitted distinction depends on the declared task. We develop **Helical Lift Theory (HLT)** as a framework for testing whether observed recurrence is accompanied by nontrivial lifted return. The framework distinguishes projected recurrence, nonidentity of a return operator, displacement of a realized state, path-odd signed transport, spatial chirality, and domain-specific physical helicity. Their connections require explicit bridge assumptions rather than a universal implication chain. Nine numbered statements organize elementary state-separation arguments, standard information-theoretic and coordinate-covariance identities, and application-specific consequences. Under well-defined Bayes-optimal logarithmic scoring, a candidate fiber's predictive value equals conditional mutual information. Downstream processing cannot recover information absent from the declared input experiment. Efficient Fisher information diagnoses regular first-order sensitivity; zero information at a singular point does not exclude nonregular identification. Nonidentity of a return operator neither establishes displacement of every initial state nor implies chirality. Additive transport scales with loop count under fixed concatenation assumptions. Signed claims require a transformation contract, and changed computational lineage prevents exact state identification for lineage-sensitive tasks without proving a literal helix. A California-earthquake program recorded adverse materiality decisions for several model classes and closed its post-2021 terminal branch. A completed retrospective membership audit confirms an unresolved earthquake-only interpretation for the historical dynamic branch; it does not quantify the effect on its fitted metrics. A solar program reconstructed a signed vertical current-helicity proxy from vector magnetograms, while a separate hemispheric-preference panel did not meet its replication criterion. Agreement with pipeline indices derived from the same fields qualifies the reconstruction, not independent instrumental accuracy. HLT does not assert that recurrent systems are universally helicoidal. Its proposed contribution is an explicit chain of definitions, observation contracts, rival comparisons and limits on interpretation.

**Keywords:** projected recurrence; fiber bundle; monodromy; holonomy; chirality; conditional mutual information; Fisher information; identifiability; helicity; fail-closed inference; provenance.

## 1. Motivation and scope

A periodic observable need not imply a periodic world. If

\[
O(X_{t+T})=O(X_t),
\]

this equality holds in an observation space. It does not generally imply

\[
X_{t+T}=X_t.
\]

The distinction is elementary, but it is often obscured by dimensional reduction, phase plots, periodic interfaces, seasonal summaries, or learned embeddings. The scientific problem is not that projection is illegitimate. Projection is unavoidable. The problem is the unlicensed inference from equality of a projection to equality of a stronger state representation.

HLT treats the recurrent observable as a base coordinate and asks whether a candidate omitted state—the fiber—undergoes nontrivial transport after a base loop. A Euclidean helix is one geometric realization. A geometric phase, covariance change, graph-valued successor, posterior update or append-only computational lineage can instantiate a more general lifted-state or successor construction. These examples need not admit invertible transport or topological monodromy, and none is a literal three-dimensional helix merely because its projected phase recurs. An observation quotient need not itself be a fiber bundle.

The word *helical* is therefore subordinate to the return structure. The theory explicitly rejects four shortcuts: visual spirality is not helicity; nontrivial monodromy is not chirality; a predictive fiber is not automatically causal; and physical helicity requires a domain-specific signed quantity rather than a generic nonidentity return.

The California seismic program provides a negative empirical case with a qualification. Increasingly flexible geometric and dynamic helical models competed against declared nonhelical rivals under locked gates. The sequence ended with a post-2021 full-network test that failed its materiality requirements and activated the terminal stop rule. A later audit found an event-type selection defect in the historical dynamic branch: numerical categories passed a filter written for textual blast labels. Its output is retained; a completed membership audit confirms that its earthquake-only interpretation remains uncertified, without estimating the effect on fitted metrics. The terminal experiment uses a different source and an explicit earthquake filter; the historical defect cannot be transferred to it without source-specific evidence. None of these empirical decisions changes the logical distinction between observation equality and state equality.

## 2. Claim distinctions and conditional bridges

Let \(X\) be a state space, \(O:X\to Y\) an observation map, and \(\Phi_t\) a declared state evolution. The labels from previous versions are retained for comparison, but no longer constitute a universally nested hierarchy:

\[
\mathsf R_0:\ O(\Phi_Tx)=O(x)
\]

(projected recurrence),

\[
\mathsf R_1^{\mathrm{op}}:\ M_\ell\neq I,
\qquad
\mathsf R_1^x:\ M_\ell(f_0)\neq f_0
\]

(nonidentity of the return operator, distinguished from nonreturn of the realized initial state),

\[
\mathsf R_2^{\mathrm{path}}:\
\chi(\ell^{-1})=-\chi(\ell),\quad\chi(\ell)\neq0
\]

(path-odd signed transport),

\[
\mathsf R_2^{\mathrm{parity}}:\
\chi(PX)=-\chi(X),\quad\chi(X)\neq0
\]

(spatial parity-odd observable under a specified physical operation \(P\)), and

\[
\mathsf R_3:\ \chi\text{ is a domain-defined physical helicity observable or specified proxy.}
\]

An observable and a conserved invariant are different claims. A component proxy must also remain distinguished from the full quantity. The implication \(\mathsf R_1^x\Rightarrow\mathsf R_1^{\mathrm{op}}\) holds; its converse fails at fixed points. There is no general chain \(\mathsf R_3\Rightarrow\mathsf R_2\Rightarrow\mathsf R_1\): a parity-odd field quantity need not describe temporal transport, and a path-odd functional need not measure endpoint displacement. A nonzero loop circulation can coexist with identity transport on a separately chosen fiber.

A valid bridge from signed endpoint change to realized nonreturn requires a declared statistic \(c(f_0,M_\ell f_0)\), with \(c(f,f)=0\), and evidence that it is nonzero. Bridges from physical field quantities require their own measurement and transport definitions.

**Analytic separation of field helicity and temporal return.** On a periodic spatial domain, take the stationary field

\[
\mathbf B(x,y,z)=(\cos z,\sin z,0).
\]

It satisfies \(\nabla\cdot\mathbf B=0\), \(\nabla\times\mathbf B=-\mathbf B\), and

\[
\mathbf B\cdot(\nabla\times\mathbf B)=-1.
\]

Its current-helicity density is nonzero while its Eulerian field state remains constant in time. With the field itself as state, temporal evolution and return are identity. Thus nonzero physical helicity density does not imply nontrivial temporal lifted return. This is an exact counterexample to a logical implication, not simulated evidence about a physical dataset.

Projected recurrence \(\mathsf R_0\) alone implies none of the separate stronger claims. Each result must declare its state, path, parity, physical definition and bridge assumptions.

---

## 3. Observation quotient and lifted state

### Definition 1 — Observation equivalence

For \(x,x'\in X\),

\[
x\sim_O x' \iff O(x)=O(x').
\]

The direct observational object is the quotient \(X/\!\sim_O\). A representation that is sufficient for one target can remain insufficient for another.

### Definition 2 — Projected recurrence

A state \(x\) is recurrent at lag \(T>0\) under \(O\) if

\[
O(\Phi_Tx)=O(x).
\]

This is a statement in the codomain of \(O\), not an equality of total states.

### Theorem 1 — Projected recurrence does not imply state return

If

\[
O(\Phi_Tx)=O(x)
\]

and there exists any state function \(F:X\to\mathcal F\) for which

\[
F(\Phi_Tx)\neq F(x),
\]

then \(\Phi_Tx\neq x\), although \(x\) and \(\Phi_Tx\) belong to the same observation-equivalence class.

**Proof.** If \(\Phi_Tx=x\), every function on state would take the same value at both points. The assumed inequality under \(F\) contradicts that equality. The observation equality establishes only quotient recurrence. \(\square\)

### Corollary 1.1 — Closure gap

For a metric or pseudometric \(d_{\mathcal F}\), including a distance induced by a seminorm,

\[
G_F(T)=d_{\mathcal F}(F(\Phi_Tx),F(x))
\]

is a state-dependent closure gap. A positive gap certifies a difference in the chosen fiber. A zero gap does not prove total-state return unless the distance separates the relevant fiber states and the joint representation consisting of the observation and fiber is injective on the jurisdiction of interest. A pseudometric can assign zero distance to distinct fiber states.

---

## 4. Return operators, gauge covariance, and monodromy

Let \(\pi:E\to B\) be a bundle or locally fibered state representation equipped with a specified transport rule. A base loop alone does not determine how its fiber moves. A connection with defined horizontal lifting, a covering with unique path lifting, or a specified dynamical evolution can supply the missing rule. A single observed trajectory determines at most its own endpoint, not a return map on every initial fiber state.

When transport around a closed base loop \(\ell\) based at \(b\in B\) is defined on the whole fiber and returns to that fiber, it defines a return operator

\[
M_\ell:E_b\to E_b.
\]

### Definition 3 — Operator-level and realized nontrivial return

A specified return operator is nontrivial when

\[
M_\ell\neq I.
\]

The realized initial fiber state \(f_0\) fails to return when

\[
M_\ell(f_0)\neq f_0.
\]

For example, \(M(f)=-f\) on \(\mathbb R\) is not identity but fixes \(f=0\). Operator nonidentity cannot establish displacement of that initial state.

Translation on a scalar fiber,

\[
M_\ell(f)=f+\delta,\qquad \delta\neq0,
\]

moves every point. It can realize the return map of a Euclidean helix when the base is an oriented circle, the fiber is its axial coordinate, and the intervening trajectory has the corresponding constant radius and pitch. The endpoint translation alone does not determine the intervening curve's shape or torsion. A helix is a curve; a helicoid is a surface.

### Theorem 2 — Gauge covariance of the return operator

Let \(g_b:E_b\to E_b\) be an admissible bijective change of fiber coordinates used at both endpoints. In the new trivialization the same return is represented by

\[
M_\ell' = g_b\,M_\ell\,g_b^{-1}.
\]

Consequently:

1. \(M_\ell=I\) iff \(M_\ell'=I\);
2. the conjugacy class of \(M_\ell\) is coordinate-invariant;
3. fixed states correspond: \(M_\ell(f_0)=f_0\) iff \(M_\ell'(g_bf_0)=g_bf_0\);
4. for finite-dimensional linear fibers, when \(M_\ell\) is linear and \(g_b\) is invertible linear, eigenvalues, determinant, trace, Jordan structure and spectral radius are preserved by matrix similarity. Arbitrary nonlinear coordinate changes do not supply this matrix-similarity statement.

**Proof.** The input is mapped back by \(g_b^{-1}\), acted upon by \(M_\ell\), and expressed in the new coordinates by \(g_b\). Identity and fixed-state correspondence follow by substitution. For linear maps and invertible linear changes, the formula is matrix similarity and preserves the listed invariants. \(\square\)

**Consequence.** A claim of nontrivial lifted transport should be stated in terms of gauge-invariant properties of the return map, not the visual shape of coordinates chosen to display it.

### Definition 4 — Monodromy and holonomy

- **Monodromy** here requires invertible transport that depends only on endpoint-fixed homotopy classes. Identity paths must act as identity, concatenation must match composition, and reversal must act by inverse transport. With a consistent concatenation convention, this yields
  \[
  \rho:\pi_1(B,b)\to\operatorname{Aut}(E_b).
  \]
  Covering-space lifting and complete flat parallel transport supply familiar settings under their respective assumptions.
- **Holonomy** is transport around loops for a specified connection. It need not be invariant under arbitrary endpoint-fixed homotopies: curvature can produce nontrivial transport around contractible loops. Flatness, with the required existence and completeness of transport, supplies the homotopy-invariance bridge.
- **Return or successor map** is the appropriate general term when transport is irreversible, depends on the path rather than its homotopy class, or records evidence accumulation. Stochastic transitions require kernels and their composition rather than deterministic automorphisms.

These constructions can coincide in special settings. A loop alone establishes neither transport, invertibility nor topological monodromy.

---

## 5. Task-relative necessity of a lift

A state distinction can be ontologically real yet irrelevant to the prediction or decision target.

Let \(Y=O(X)\), let \(F\) be a candidate fiber, and let \(Z\) be a declared target.

### Theorem 3 — Log-score value of the fiber equals conditional mutual information

Assume a common joint law for \((Z,Y,F)\) on spaces admitting regular conditional distributions, and conditional target densities with respect to a common dominating measure. Use the true conditional distributions under logarithmic score. Require finite expected scores, or a directly well-defined expected log-density ratio that does not subtract infinite expectations. Then the Bayes-optimal expected gain from using \((Y,F)\) instead of \(Y\) alone is

\[
\mathbb E\!\left[\log p(Z\mid Y,F)-\log p(Z\mid Y)\right]
= I(Z;F\mid Y)\ge 0.
\]

Therefore the candidate fiber has strictly positive Bayes-optimal predictive value iff

\[
I(Z;F\mid Y)>0.
\]

**Proof.** The conditional KL representation gives

\[
I(Z;F\mid Y)
=\mathbb E_{Y,F}\!\left[
D_{\mathrm{KL}}\big(P_{Z\mid Y,F}\Vert P_{Z\mid Y}\big)\right]
=\mathbb E\left[\log\frac{p(Z\mid Y,F)}{p(Z\mid Y)}\right].
\]

Where the joint and fiber conditional densities also exist, the equivalent factorization is

\[
I(Z;F\mid Y)
=\mathbb E\left[\log\frac{p(Z,F\mid Y)}{p(Z\mid Y)p(F\mid Y)}\right].
\]

Nonnegativity follows from the KL-divergence representation of conditional mutual information. The KL construction is classical (Kullback & Leibler, 1951); the identity applies it to the declared predictive experiment. \(\square\)

This is an oracle identity, not a guarantee for fitted models. A richer estimated model can lose prospective score through estimation error, regularization, misspecification, selection or distribution shift. Positive conditional mutual information does not by itself establish causation.

### Corollary 3.1 — Task-relative sufficiency

If

\[
I(Z;F\mid Y)=0,
\]

then \(Z\) and \(F\) are conditionally independent given \(Y\), almost surely. Thus \(Y\) is sufficient for predicting \(Z\) relative to this fiber and joint law, even if states with the same \(Y\) differ in \(F\). This gives a population interpretation for the adjudication

```text
NONHELICAL_RIVAL_SUFFICIENT
```

without asserting total-state identity. A finite experiment that fails to detect improvement does not establish exact zero conditional mutual information; practical sufficiency must specify a materiality margin, uncertainty and comparison class.

---

## 6. Observation cannot be repaired by postprocessing alone

### Theorem 4 — Data-processing obstruction

For deterministic downstream processing, or a stochastic kernel using only \(Y\) and randomness conditionally independent of \(F\) given \(Y\),

\[
I(F;T(Y))\le I(F;Y).
\]

In particular, if the observation carries no information about a fiber component,

\[
I(F;Y)=0,
\]

then no downstream embedding, neural network, manifold learner, recurrence plot, or coordinate transform built only from \(Y\) can create information about \(F\) that was absent from the observation experiment.

**Proof.** \(F\to Y\to T(Y)\) forms a Markov chain. The result is the data-processing inequality. \(\square\)

**Interpretation.** A learned three-dimensional spiral can be visually compelling while remaining informationally incapable of identifying a hidden fiber. New observations or justified structural restrictions change the experiment; otherwise partial-identification bounds may be appropriate. If training data, external knowledge or temporal histories are used, they belong in the declared input random variable. Delay reconstruction may exploit information in a history that a single snapshot omits. The inequality does not forbid recovery from an enlarged experiment.

---

## 7. Local identifiability with nuisance parameters

Let

\[
y=h(x;\psi)+\varepsilon,
\]

where \(\psi\) contains instrument and processing state. Partition local parameters into candidate fiber coordinates \(F\) and nuisance coordinates \(N\). Write the Fisher information as

\[
\mathcal I=
\begin{pmatrix}
I_{FF} & I_{FN}\\
I_{NF} & I_{NN}
\end{pmatrix}.
\]

### Theorem 5 — Efficient information as a regular first-order criterion

Consider a dominated parametric experiment differentiable in quadratic mean at the parameter of interest. Assume centered square-integrable score vectors \(s_F,s_N\), and invertible nuisance covariance \(I_{NN}\). Projecting the fiber score away from the nuisance-score span gives

\[
s_{F\cdot N}=s_F-I_{FN}I_{NN}^{-1}s_N,
\]

whose covariance is

\[
I_{FF\cdot N}=I_{FF}-I_{FN}I_{NN}^{-1}I_{NF}.
\]

For any direction \(v_F\),

\[
v_F^{\mathsf T}I_{FF\cdot N}v_F
=\mathbb E[(v_F^{\mathsf T}s_{F\cdot N})^2].
\]

A zero quadratic form means that the nuisance-adjusted score vanishes almost surely in that direction at that point: first-order score sensitivity is absent. A positive form indicates first-order sensitivity after nuisance adjustment. Neither statement alone establishes global injectivity of the parameter-to-law map.

**Proof.** Orthogonal projection in the score \(L^2\) space gives the efficient score. Expanding its covariance gives the Schur complement. The displayed quadratic form is the expected square of the scalar projected score; it vanishes exactly when that score is zero almost surely. \(\square\)

At regular points with locally constant information rank and appropriate model regularity, rank conditions can characterize local identification. The regular-point qualification in Rothenberg (1971) cannot be dropped. Singular Fisher information at a nonregular point does not universally imply nonidentification; positive information is also distinct from adequate finite-sample precision.

### Analytic counterexample — Zero information with point identification

Consider the exact family

\[
Y\mid\theta\sim\mathcal N(\theta^3,1),\qquad\theta\in\mathbb R.
\]

This is an analytic counterexample, not generated data or an empirical fit. The map \(\theta\mapsto\theta^3\) is injective, so distinct parameters induce distinct laws. The score and information are

\[
s_\theta(Y)=3\theta^2(Y-\theta^3),\qquad I(\theta)=9\theta^4.
\]

Thus \(I(0)=0\) although zero is point-identified. Under independent repetition, \(\widehat\theta_n=\sqrt[3]{\overline Y_n}\), using the real cube root, is consistent by the law of large numbers and continuity. At zero its stochastic order is \(n^{-1/6}\), not the usual regular \(n^{-1/2}\) order. Equivalently,

\[
D_{\mathrm{KL}}(P_\theta\Vert P_0)=\theta^6/2.
\]

The laws are distinguishable away from zero even though the local quadratic term vanishes. Repetition can identify this nonregular parameter; it does not create a nonzero first-order score at zero in this parameterization.

### Corollary 5.1 — Exact instrumental null space

For \(Y=AX+\varepsilon\), let \(\varepsilon\sim\mathcal N(0,\Sigma)\) with positive-definite, parameter-independent \(\Sigma\). If both \(X\) and \(X+tv\) are admissible and \(v\in\ker A\), then

\[
v^{\mathsf T}A^{\mathsf T}\Sigma^{-1}Av=0,
\qquad
\mathcal L(Y\mid X+tv)=\mathcal L(Y\mid X).
\]

The equality of laws proves nonidentification along that admissible direction. Independent repetition with the same operator preserves this equality. Additional measurements, a changed operator or justified state restrictions change the experiment and can remove ambiguity.

**Decision consequence.** A rank failure warrants a first-order diagnostic or abstention under a declared procedure. The stronger statement `NOT_IDENTIFIABLE_OBSERVATION_OPERATOR` requires observational equivalence, equality of laws, or a valid applicable identification theorem. A singular point may instead require higher-order or partial-identification analysis.

---

## 8. Nontrivial return is not chirality

### Definition 5 — Separate contracts for signed transport and chirality

A path-oriented statistic can satisfy

\[
\chi(\ell^{-1})=-\chi(\ell),
\]

whereas a spatial pseudoscalar can satisfy

\[
\chi(PX)=-\chi(X)
\]

under a specified physical orientation reversal \(P\). These are different operations. Reversing traversal need not construct a spatial mirror image. Chirality requires a declared spatial transformation group; path antisymmetry alone establishes signed transport under its path convention.

For vector-field measurements, the contract must specify transformations of polar and axial components, coordinates, derivatives and masks. Active physical reflection is distinct from a passive change of frame. A pseudoscalar's sign change under an orientation-reversing coordinate convention is expected covariance, not by itself a failure of physical definition.

### Theorem 6 — Monodromy is insufficient for chirality

The condition

\[
M_\ell\neq I
\]

does not imply the existence of a nonzero chiral observable.

**Proof by counterexample.** On the scalar fiber \(\mathbb R_+\), let

\[
M_\ell(f)=2f.
\]

This map can generate the monodromy action \(\rho(n)f=2^n f\) of \(\pi_1(S^1)\cong\mathbb Z\). Take the parity action on the scalar fiber to be identity. Any parity-odd statistic of the scalar state must then equal its own negative and vanish. The nontrivial dilation therefore supplies no nonzero chirality under this specified action. Variance inflation, posterior contraction, scalar growth and lineage extension likewise need additional geometric and transformation structure before chirality can be inferred. This does not prohibit chiral variables in a separately enlarged system. \(\square\)

### Corollary 6.1 — Authorized terminology

If a specified return satisfies \(M_\ell\neq I\) but spatial parity-odd structure has not been identified, the appropriate operator-level statement is

```text
NONTRIVIAL_LIFTED_TRANSPORT
```

not

```text
CHIRALITY_DETECTED
```

or

```text
PHYSICAL_HELICITY_DETECTED
```

A claim about the realized state additionally requires \(M_\ell(f_0)\neq f_0\). A pseudoscalar need not keep its raw sign under every orientation convention; its transformation-corrected physical claim must be consistent.

---

## 9. Additive signed transport and loop reversal

Suppose composable paths carry a fixed scalar additive transport functional \(\chi\), with identity paths mapped to zero, satisfying concatenation

\[
\chi(\ell_1\!\cdot\!\ell_2)=\chi(\ell_1)+\chi(\ell_2)
\]

and path reversal

\[
\chi(\ell^{-1})=-\chi(\ell).
\]

### Proposition 7 — Repeated-loop scaling

For the \(n\)-fold concatenation \(\ell^n\),

\[
\chi(\ell^n)=n\chi(\ell).
\]

**Proof.** Induction using concatenation proves the formula for positive integers; the identity path gives zero, and reversal gives negative integers when inverse paths are defined. \(\square\)

Repeated identical loops under a fixed additive rule therefore have linear signed accumulation. A separate stochastic rival with increments \(\xi_k\) has zero mean displacement when \(\mathbb E\xi_k=0\). Variance \(n\sigma^2\) additionally requires uncorrelated increments with common finite variance \(\sigma^2\). Correlated or nonstationary diffusion need not obey that dispersion law. Non-Abelian transport, varying loops and state-dependent pitch need not admit the scalar additivity assumed here.

**Use.** These assumptions yield distinct accumulation and dispersion predictions for coherent transport, unbiased diffusion and pure cyclic return. A secular trend may share the same accumulation law; the identity alone does not uniquely identify a helical mechanism.

---

## 10. Representation uncertainty and gauge stress tests

Any learned phase, centerline, tangent frame, graph, or local coordinate may itself be uncertain. A signed claim is not identifiable merely because a preferred representation yields a stable sign.

### Definition 6 — Transformation-corrected representation robustness

Let \(\mathcal G\) be a declared class of admissible frame or representation changes, with an explicit probability measure or finite weighted stress-test design \(\mu\). A transformation set alone does not define a probability. Express each statistic \(\widetilde\chi_g\) in a common physical orientation using its known transformation law. For a pseudoscalar and an orthogonal frame change \(Q_g\), this can take the form \(\widetilde\chi_g=\det(Q_g)\chi_g\), with all field conventions specified. More general changes require their appropriate law.

A nonzero result is representation-robust at level \(q\) under this design when

\[
\mu\{g:\operatorname{sign}\widetilde\chi_g
=\operatorname{sign}\widetilde\chi_0\}\ge q.
\]

Treatment of zero and intervals overlapping zero must be declared. This is a robustness diagnostic for \(\mu\), not a universal guarantee or posterior probability without a generative interpretation. Active mirror configurations test physical parity behavior; they are not passive gauges of one configuration.

### Proposition 8 — Unresolved representation sign is not identified

Suppose two observationally equivalent admissible representations of one physical state yield opposite nonzero signs after all justified transformation corrections. If no observational or orientation rule resolves the ambiguity, the experiment does not identify the signed claim.

**Proof.** The same observational equivalence class admits both signs, so the sign is not a well-defined function of that class. \(\square\)

A raw sign flip under a known orientation reversal can instead be exactly the covariance required of a defined pseudoscalar. Its occurrence does not establish nonidentification.

---

## 11. Append-only recurrence in computational systems

Let \(P(S)\) be a projected workflow phase and \(L(S)\) a lineage state containing content hashes, source receipts, authority, execution identity, and predecessor links.

### Theorem 9 — Recurrent phase with changed lineage is a successor state

If

\[
P(S_{n+1})=P(S_n)
\]

but

\[
L(S_{n+1})\neq L(S_n),
\]

then a representation identifying \(S_{n+1}\) with \(S_n\) cannot exactly recover lineage on a domain containing both states. An append-only successor representation preserves the distinction if it retains the relevant lineage fields.

**Proof.** Take the deterministic target \(Z=L(S)\). A decoder of the phase-only representation would receive the same input for both states but would have to return different lineage values. It therefore cannot recover both exactly. \(\square\)

A probabilistic sufficiency claim additionally requires a declared law and positive conditional ambiguity on the relevant support. A pair of distinct states alone does not establish positive conditional mutual information under every sampling distribution; a law concentrated on one state has no such ambiguity.

This is a deterministic separation statement with a computational design application, not a new physical law. It prevents recurrent interfaces, retries, checkpoints and phase returns from becoming silent state mutation. Strict append-only growth with retained predecessor information establishes a nonreturning lineage path. It does not establish geometric pitch, torsion, spatial chirality, invertible monodromy or a literal helix. A new receipt can record another execution without new scientific evidence: lineage growth, evidence gain and permission change require separate accounting.

---

## 12. Falsification architecture

A helical or signed-lift model must compete against at least the following rivals where applicable:

1. identity return/cycle;
2. cycle plus secular trend;
3. quasiperiodic torus;
4. zero-mean diffusive fiber;
5. branching or graph-valued successor;
6. nonperiodic attractor;
7. observation-induced apparent torsion;
8. unsigned-magnitude control when a signed physical claim is proposed.

Authorized outcomes are semantically distinct:

```text
HELICAL_LIFT_SUPPORTED
SIGNED_TRANSPORT_SUPPORTED
NONHELICAL_RIVAL_SUFFICIENT
SIGNED_TRANSPORT_UPPER_BOUND
NOT_IDENTIFIABLE_OBSERVATION_OPERATOR
NOT_IDENTIFIABLE_REPRESENTATION
MODEL_MISMATCH
BLOCKED_SOURCE_PROVENANCE
```

A blocked acquisition is not a null result. Rank deficiency requires interpretation under the observation model and is not evidence of physical absence. A valid upper confidence bound below a materiality threshold can support a stronger comparison than a nonsignificant p-value, provided its estimand, coverage assumptions and selection procedure are stated. A bound on predictive gain is not a physical bound on helicity.

Source status, regular or nonregular identification, realized transport, physical interpretation, prospective prediction and lineage must remain distinct. Passed software tests establish tested implementation properties, not empirical support for a physical model. Listing the eight rivals does not imply that every experimental branch implemented all eight.

---

## 13. Domain-specific helicity: magnetic case

The theory deliberately separates generic signed transport from magnetic helicity.

For a differentiable magnetic field \(\mathbf B\), define current-helicity density in the curl convention by

\[
h_c = \mathbf B\cdot(\nabla\times\mathbf B).
\]

If electric current density is \(\mathbf j=\mu_0^{-1}\nabla\times\mathbf B\), then \(\mathbf B\cdot\mathbf j=h_c/\mu_0\) in SI units. Volume-integrated helicity is another object. Instrument conventions and conversion factors must be recorded, rather than silently interchanging curl and electric-current-density units.

From a photospheric vector magnetogram, HMI directly supports the vertical current-helicity proxy

\[
h_c^{(z)}=B_zJ_z,
\qquad
J_z\propto\frac{\partial B_y}{\partial x}-\frac{\partial B_x}{\partial y}.
\]

This is signed and physically defined, but it is **not** the full three-dimensional current helicity because vertical derivatives are unavailable from a single photospheric boundary. Nor is it the same object as gauge-invariant relative magnetic helicity of a coronal volume.

Therefore the direct-field MHD program has three levels:

1. reconstruct \(B_zJ_z\) from pixel-level vector fields and qualify the calculation and sign/units against the HMI pipeline;
2. establish robustness under inversion/disambiguation uncertainty and coordinate parity;
3. only then ask whether a signed field-level quantity adds prospective information beyond unsigned controls.

A forecasting gain without successful levels 1–2 cannot establish the proposed signed-proxy interpretation. Passing them still does not turn the proxy into full current helicity or magnetic helicity. The SHARP construction and instrumental context are described by Bobra et al. (2014) and Hoeksema et al. (2014).

---


## 14. Direct physical observability gate in MHD

The theory requires a domain-specific bridge before a signed fiber can be interpreted as physical helicity. Solar vector magnetograms provide such a test because the relevant signed proxy is not inferred from the visual geometry of an event cloud: it is reconstructed from the measured vector field and its horizontal derivatives.

For an HMI/SHARP CEA patch we use

\[
B_z=B_r,\qquad B_x=B_\phi,\qquad B_y=-B_\theta,
\]

and reconstruct

\[
J_z\propto
\frac{\partial B_y}{\partial x}
-
\frac{\partial B_x}{\partial y},
\]

followed by

\[
h_{c,z}=B_zJ_z,
\qquad
\alpha_{\rm av}
=
\frac{\sum J_zB_z}{\sum B_z^2}.
\]

The archived experiment reports sixteen TRAIN-only active regions, balanced by hemisphere and chosen without flare outcomes or helicity values, frozen before vector-field FITS acquisition. Its gate required exact high-confidence-mask reconstruction, SHARP pipeline agreement, parity antisymmetry, and signed stability under 64 propagated component-error realizations per record. These historical realizations are computational uncertainty propagation conditional on an error model, not additional independent magnetograms. This revision preserves the reported procedure and metrics; it generates no new realizations. Such propagation does not by itself exhaust inversion, disambiguation, correlation or model-systematic uncertainty.

The result was:

```text
DIRECT_SIGNED_CURRENT_HELICITY_OBSERVABLE
```

with

```text
16/16 records processed
MEANJZH sign agreement       1.000
MEANALP sign agreement       1.000
Spearman MEANJZH             1.000
Spearman MEANALP             1.000
median rel. error MEANJZH    4.49e-6
median rel. error MEANALP    3.97e-6
informative-sign stability   1.000
parity control               PASS
```

This supports the specified proxy interpretation under \(\mathsf R_3\) within the reconstruction contract. It does not imply temporal transport, realized nonreturn or a general hierarchy of physical authority. The comparison uses SHARP indices derived from the same underlying field measurements. Agreement qualifies implementation, conventions and reproducibility against that reference pipeline; it is not independent instrumental validation, an independent magnetic-field measurement or validation against an external physical ground truth.

The result does not promote \(B_zJ_z\) to full \(\mathbf B\cdot\mathbf J\), nor to coronal relative magnetic helicity. It also contains no flare-prediction claim.

### 14.1 Hemispheric-sign replication

A second panel of 32 CALIBRATION-period active regions, 16 in each hemisphere, was selected deterministically without using helicity values or flare labels. The physical literature predicts only a statistical hemispheric preference, not a universal sign law, so the gate required at least 22 of 32 robust sign agreements, at least 9 of 16 in each hemisphere, and a one-sided exact binomial \(p\le0.05\).

Direct-field reconstruction again passed exactly, but the hemispheric preference did not:

```text
robust compliant total       15 / 32
north                         7 / 16
south                         8 / 16
exact one-sided binomial p    0.7017
MEANALP sign-rule total       16 / 32
```

The authorized outcome is therefore

```text
HEMISPHERIC_SIGN_PREFERENCE_NOT_REPLICATED
```

for this locked 2017–2020 panel. The result does not establish universal absence of a hemispheric tendency or demonstrate a cycle-based explanation for the failed panel. The exact binomial calculation relies on its Bernoulli null and independence of counted units; dependence and temporal selection require separate treatment for wider population claims. It is not evidence that the signed proxy is unobservable. Reconstruction and population-pattern replication answer different questions. The motivating literature on hemispheric preference requires its own primary references in the dedicated empirical manuscript.

---

## 15. Seismic counterexample and the role of negative evidence

The earthquake-catalog program sequentially tested global static, local/piecewise static, conservative dynamic, and post-2021 full-network dynamic classes. The archived final gate failed its materiality and complexity requirements and activated the terminal stop rule. These are decisions about tested models and estimands, not a universal exclusion of seismic helicity. The historical dynamic membership audit is now complete: it recovered specific selected records with discordant official counterparts under its stated matching contract. Its earthquake-only interpretation remains reserved, and metric sensitivity to corrected selection has not been calculated. Completion of the audit is therefore distinct from clearance of the eligibility reservation.

This does **not** falsify the valid mathematical statements above. Failure of a materiality gate means that the tested procedure did not earn support under its comparison. A valid upper bound limits the specified predictive gain under its assumptions, not every physical helicity magnitude. An adverse predictive result cannot be treated as a fully qualified earthquake-only result while its cohort eligibility remains unresolved.

The negative sequence demonstrates why these distinctions matter:

\[
\text{projected recurrence}
\not\Rightarrow
\text{helicoidal transport}
\not\Rightarrow
\text{physical helicity}.
\]

---


## 16. Discussion: what the negative seismic sequence and direct-field results change

The closed terminal seismic program provides no support for treating apparent geometric helicity in these earthquake catalogs as a privileged route to the abstract framework. Global static, local/piecewise, conservative dynamic and full-network new-data models have archived adverse decisions. Those decisions remain visible with their separate scopes and eligibility status. They do not license indefinite post-hoc model rescue or universally exclude all possible seismic mechanisms.

### Historical dynamic eligibility reservation

The retrospective membership audit completed on 13 October 2026 recovered all 61,555 selected historical indices and matched event identity and codes against an independently extracted blind view of the same exact source. Among selected records, 3,513 have numerical `ev_bl=1`; 3,506 are in the archived observable subset, including 771 in test partitions. Their version-specific numerical meaning remains uncertified, so these are category counts, not established blast counts. Under the candidate network correspondence and an origin-time difference of at most one second, 17 selected code-0 records have previously verified official-catalog `qb` counterparts. Sixteen are observable: two in Bay Area training, thirteen in Bay Area calibration, and one in Parkfield testing. An additional observable Bay Area training record has an unsupported control-character type in its counterpart. The audit establishes that specific discordant records entered the selected cohorts. It decoded no angular values, reran no model and does not quantify the impact on fitted metrics. Authenticating the code dictionary and resolving record-level discrepancies remain separate tasks; no retrospective exclusion has been made.

The post-2021 terminal branch uses another source and an explicit earthquake filter. The historical label defect does not automatically invalidate that terminal adverse result or revoke its stop rule. Its own source, eligibility, cohort and scoring contracts govern interpretation; further correction requires source-specific evidence.

Decoding the producer's categories and reconciling other catalogs are separate checks. A version-specific authenticated dictionary can establish category meaning. Cross-catalog reconciliation assesses identity, revision and quality agreement. An exhaustive corroboration contract may appropriately produce a HOLD under its thresholds, but complete agreement is not a universal precondition for semantic identification. No frozen threshold, cohort or historical gate result is modified by this editorial correction.

### Physical proxies and the remaining temporal bridge

Covariance changes, posterior updates, accumulated scalars and graph successors can be subjects of lifted-state analysis when their state and transport rules are defined. They are not automatically physical helicity or topological monodromy. Conversely, a field can have nonzero current-helicity density while stationary in time, as the analytic counterexample demonstrates.

The direct-field reconstruction reported here has already passed its archived pipeline-comparison gate and should no longer be described as a merely future success. It shows that this proxy can be reproduced from these vector-field products under the reported conventions. The hemispheric preference did not replicate its declared rule. Neither result supplies independent magnetic-field measurement or temporal lifted transport. A temporal study must specify the evolving state, base recurrence or comparison path, transport, registration, boundaries, uncertainty, and the link between its proxy and its transport claim. Prospective prediction then requires unsigned controls and appropriate nonhelical rivals.

The subsequent v1.5 temporal execution has reached an actual support-gate outcome, `INSUFFICIENT_TEMPORAL_SUPPORT`: six snapshots qualified, but only one complete trajectory remained. Quality failures included the initial record for HARP 2920 (`QUALITY=70656`) and the six-hour record for HARP 5249 (`QUALITY=66560`). No temporal or forecasting model comparison was performed. This is a concrete observation-support result for the attempted continuation, not evidence for or against physical temporal transport.

### Contribution and limits

The numbered results collect established information-theoretic and coordinate principles, elementary separation arguments, and consequences for scientific computation. Counting them does not establish nine novel theorems. Berry (1984), Takens (1981), Eckmann et al. (1987), and de Silva et al. (2011) provide antecedents on geometric phase, reconstruction, recurrence description and circular coordinates; none alone establishes the broader empirical program. Rothenberg (1971) supplies an identification setting whose regularity conditions are essential. The proposed contribution is the use of these distinctions in an explicit observation-and-adjudication contract with implementation and empirical records. Novelty relative to integrated prior frameworks remains subject to comparative review and external assessment.

Fail-closed computation helps only when the blocked claim is named accurately. Source HOLD, first-order rank failure, absent prospective gain, unreplicated population pattern and unresolved physical interpretation are different states. Keeping them distinct permits independent research branches to progress without promoting an unverified global ontology or making all branches wait on an unrelated acquisition defect.

## 17. Conclusion

The central logical restriction remains:

\[
\boxed{\text{projected recurrence} \not\Rightarrow \text{state return}.}
\]

The scientific task is to specify the state and transport experiment, distinguish operator nonidentity from realized nonreturn, assess regular or nonregular identification, apply the correct sign transformation law, and evaluate the added state for a declared target. Physical helicity requires an additional domain definition and measurement contract. Negative comparisons, justified nonidentification, inconclusive evidence and predictive bounds below materiality are distinct legitimate outcomes. The mathematical distinctions are not themselves empirical hypotheses; their domain instantiations become falsifiable through explicit rivals, estimands and observation contracts.


## References

Berry, M. V. (1984). Quantal phase factors accompanying adiabatic changes. *Proceedings of the Royal Society A*, 392, 45–57. https://doi.org/10.1098/rspa.1984.0023

de Silva, V., Morozov, D., & Vejdemo-Johansson, M. (2011). Persistent cohomology and circular coordinates. *Discrete & Computational Geometry*, 45, 737–759. https://doi.org/10.1007/s00454-011-9344-x

Eckmann, J.-P., Kamphorst, S. O., & Ruelle, D. (1987). Recurrence plots of dynamical systems. *Europhysics Letters*, 4, 973–977. https://doi.org/10.1209/0295-5075/4/9/004

Takens, F. (1981). Detecting strange attractors in turbulence. In *Dynamical Systems and Turbulence, Warwick 1980*. Lecture Notes in Mathematics 898. Springer. https://doi.org/10.1007/BFb0091924

Bobra, M. G., Sun, X., Hoeksema, J. T., Turmon, M., Liu, Y., Hayashi, K., Barnes, G., & Leka, K. D. (2014). The Helioseismic and Magnetic Imager (HMI) Vector Magnetic Field Pipeline: SHARPs—Space-Weather HMI Active Region Patches. *Solar Physics*, 289, 3549–3578. https://doi.org/10.1007/s11207-014-0529-3

Hoeksema, J. T., Liu, Y., Hayashi, K., Sun, X., Schou, J., Couvidat, S., et al. (2014). The Helioseismic and Magnetic Imager (HMI) Vector Magnetic Field Pipeline: Overview and Performance. *Solar Physics*, 289, 3483–3530. https://doi.org/10.1007/s11207-014-0516-8

Kullback, S., & Leibler, R. A. (1951). On information and sufficiency. *The Annals of Mathematical Statistics*, 22(1), 79–86. https://doi.org/10.1214/aoms/1177729694

Rothenberg, T. J. (1971). Identification in parametric models. *Econometrica*, 39(3), 577–591. https://doi.org/10.2307/1913267
