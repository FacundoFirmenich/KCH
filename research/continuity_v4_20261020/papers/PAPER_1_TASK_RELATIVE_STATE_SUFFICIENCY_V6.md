# Task-Relative State Sufficiency: Observation, Lifted Return, and Certified Evidence Planning

**Manuscript status:** full working draft V6, 20 October 2026, successor to `PAPER_1_PROJECTED_RECURRENCE_HELICAL_LIFTS_V5.md`. This revision repositions the contribution against causal states, predictive state representations, state-action abstraction, robust identification and independently verified optimization. The earlier HLT label is retained only for historical continuity and its explicitly defined lifted-return specialization. All V5 mathematical statements, proofs, analytic counterexamples, empirical quantities and reservations are retained; the v3 finite ECH specialization and solar v1.6/v3 chronology are integrated without changing frozen outcomes. No new experiment is reported in this manuscript revision. Scientific novelty and generalization remain separate from correctness of a finite certificate or reconstruction. This is a research manuscript, not an external-review certificate or a claim of universal physical helicity.

## Abstract

An observation can recur while a state distinction relevant to a task changes. The distinction follows from non-injective observation and does not establish a new general theory of memory. We formulate an observation-and-comparison contract that separates projected recurrence, nonidentity of a return operator, displacement of a realized state, path-odd transport, spatial chirality and domain-specific physical helicity. Their connections require explicit bridge assumptions. Nine retained numbered statements organize elementary separation arguments, standard information and coordinate identities, and computational consequences. Bayes-optimal logarithmic-score gain from an added state component is conditional mutual information under the stated law and existence conditions; fitted models need separate evaluation. Data processing cannot restore information absent from the declared experiment. Efficient Fisher information diagnoses regular first-order sensitivity, while singular information need not imply nonidentification. Operator nonidentity neither moves every initial state nor implies chirality; fixed additive transport scales with repeated loops under its concatenation assumptions. Changed lineage can prevent exact recovery from a recurrent workflow phase without establishing a literal helix. We position these statements against causal states, predictive state representations and decision-preserving abstractions. A finite ECH instantiation retains sensor-specific separation patterns and actual remaining capacities, preserving feasible acquisition plans and costs along fixed routes while leaving audit lineage intact. Its archived certificates and quotient establish the specified finite result, not minimality, acceleration or novelty of abstraction and rational checking. Domain records retain a closed terminal California predictive test, a separate unresolved historical earthquake-only eligibility interpretation, and solar proxy reconstruction against products of the same measurements. The later solar development comparison preserves local improvements but no declared dominant lift; its shared-translation coefficient telescopes to training endpoints. These results do not supply independent instrumental validation or a universal helicoidal mechanism. The contribution pursued is a precise, testable relation between a representation, the task it preserves and the observation contract needed for its physical interpretation.

**Keywords:** task-relative sufficiency; state abstraction; projected recurrence; predictive state; lifted return; conditional mutual information; identifiability; evidence acquisition; certified optimization; helicity; provenance.

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

The historical label Helical Lift Theory (HLT) is retained for continuity with earlier records. In this manuscript it denotes an observation-and-comparison framework, not a claim to a new general theory of memory or physical helicity. Its lifted-return specialization treats the recurrent observable as a base coordinate and asks whether a candidate omitted state—the fiber—undergoes nontrivial transport after a base loop. A Euclidean helix is one geometric realization. A geometric phase, covariance change, graph-valued successor, posterior update or append-only computational lineage can instantiate a more general lifted-state or successor construction. These examples need not admit invertible transport or topological monodromy, and none is a literal three-dimensional helix merely because its projected phase recurs. An observation quotient need not itself be a fiber bundle.

The word *helical* is therefore subordinate to the return structure. The framework explicitly rejects four shortcuts: visual spirality is not helicity; nontrivial monodromy is not chirality; a predictive fiber is not automatically causal; and physical helicity requires a domain-specific signed quantity rather than a generic nonidentity return.

The California seismic program provides a negative empirical case with a qualification. Increasingly flexible geometric and dynamic helical models competed against declared nonhelical rivals under locked gates. The sequence ended with a post-2021 full-network test that failed its materiality requirements and activated the terminal stop rule. A later audit found an event-type selection defect in the historical dynamic branch: numerical categories passed a filter written for textual blast labels. Its output is retained; a completed membership audit confirms that its earthquake-only interpretation remains uncertified, without estimating the effect on fitted metrics. The terminal experiment uses a different source and an explicit earthquake filter; the historical defect cannot be transferred to it without source-specific evidence. None of these empirical decisions changes the logical distinction between observation equality and state equality.

<!-- V6_ADDITION_BEGIN:RELATED_WORK -->
### 1.1 Related work and contribution boundaries

The relevance of a retained state distinction is task-relative, and that principle has substantial predecessors. Shalizi and Crutchfield (2001) define causal states by equivalence of histories that induce the same law of futures, with predictive sufficiency and minimality results under their setting. Littman, Sutton and Singh (2001) represent state through predictions of action-conditioned future tests. These are not interchangeable with an arbitrary stored history: adding a lineage field is not, by itself, evidence that the field improves prediction. Our deterministic lineage argument in Section 11 concerns recovery of a declared audit target; a predictive claim still needs a law and target-specific ambiguity.

Li, Walsh and Littman (2006) distinguish state abstractions by the properties they preserve, while Abel et al. (2020) analyze state-action abstractions and options that preserve value under specified conditions. Consequently, preserving decisions after compression is not proposed here as a new general principle. The finite ECH construction in Section 11.1 specifies the state, action capacities, costs and contract predicates for one exact planning problem. Its relation to existing abstraction theory is a concrete specialization to be compared, not a claim that abstraction theory cannot represent it.

Takens (1981) provides a complementary restriction on the insufficiency argument: a suitably constructed history of observations can recover state under the embedding theorem's smoothness, dimension and genericity assumptions. A phase-only rival must not be confused with every temporal representation built from the same instruments. Circular coordinates obtained through persistent cohomology (de Silva et al., 2011) address phase construction; they do not automatically identify a transported fiber or a physical helicity quantity. Comparisons must declare whether an added component supplies new measurements, more history, a structural assumption or merely a deterministic transformation of existing inputs.

The logarithmic-score identity in Section 5 instantiates classical information-theoretic and proper-scoring principles (Kullback & Leibler, 1951; Gneiting & Raftery, 2007). Its oracle gain is distinct from the out-of-sample performance of fitted estimators. The geometric distinctions also have established foundations: geometric phase and holonomy require their transport structure (Simon, 1983; Berry, 1984), and field helicity has a domain-specific definition and conservation conditions (Moffatt, 1969). None of these precedents turns arbitrary provenance accumulation into physical helicity.

Robust pair separation and multicover likewise precede ECH: Abbas et al. (2017) formulate resilient identification using multivalued sensors and bounded errors. Szeider (2026) constructs independently checkable rational VIPR certificates using black-box solver output. The specific composition of inherited evidence, changing intermediate contracts, sensor restrictions and finite capacity is therefore the candidate contribution to investigate. The present manuscript does not claim novelty of multicover, lookahead, rational certificates or task-relative memory considered separately.

| Component in this manuscript | Established or elementary content | Specific contribution or remaining obligation |
|---|---|---|
| Observation equality versus state equality | Non-injectivity and deterministic separation; Theorem 1 is elementary. | Declare a task whose relevant distinction is lost, and compare against adequately informed representations. |
| Predictive value of added state | Causal states, PSR and oracle information gain supply direct predecessors. | Identify which additional information is available and useful for the target; test fitted models separately. |
| Regular information and representation sign | First-order sensitivity, observational equivalence and transformation laws answer different questions. | Keep the gate's exact object explicit; do not promote a local rank diagnostic to universal impossibility. |
| Return, holonomy and physical helicity | Classical transport and field concepts with distinct assumptions. | Supply a domain-specific bridge between the measured observable and the claimed mechanism. |
| ECH reduced planning state | A cost-preserving transition abstraction specialized to bounded acquisitions. | Demonstrate the encoding, preservation argument and artifact; establish a differential advantage separately. |
| Audit lineage | Distinguishing histories can be necessary for custody even if planning merges them. | Keep provenance and authority available without claiming that ledger growth adds scientific information. |

The numbered results below retain their V5 identifiers to keep proofs and cross-references stable. They are not a count of novel mathematical discoveries. The contribution is evaluated by the declared task, preserved property and demonstrated consequence, not by the number of definitions or gates. The literature comparison is targeted, not an exhaustive certification of priority. Primary-source reading depth and access limits are recorded with this revision.
<!-- V6_ADDITION_END:RELATED_WORK -->

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

<!-- V6_ADDITION_BEGIN:TARGET_RELATIVE_LABEL -->
**Prospective naming clarification (V6).** For the population statement in Corollary 3.1, the preferred descriptive label is `BASE_REPRESENTATION_SUFFICIENT_FOR_TARGET`. The historical `NONHELICAL_RIVAL_SUFFICIENT` remains quoted above because it occurs in earlier adjudication records; it is interpreted only relative to the declared target, candidate fiber and law. This editorial mapping does not modify any stored result or deploy a renamed software status. A future implementation must version the mapping explicitly. Neither label establishes that the physical system has no helical mechanism.
<!-- V6_ADDITION_END:TARGET_RELATIVE_LABEL -->

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

<!-- V6_ADDITION_BEGIN:ECH_SPECIALIZATION -->
### 11.1 A finite instance: sufficient state for ECH acquisition planning

This subsection incorporates the v3 planning quotient as a concrete instance of the task-relative question. It reports the existing finite proof and corpus, not a new benchmark or a physical observation. Let \(K\) be the 65 functional classes of the frozen kernel, \(P\) its 2,080 unordered class pairs, and \(Q_s\) the 4,017 admissible masks for sensor \(s\in\{\mathrm{EXACT},\mathrm{MODE},\mathrm{ACTIONABLE}\}\). A coordinate \((s,q)\) is typed: identical masks under distinct sensors remain different acquisitions. For the fixed response table \(r_s(c,q)\), define

\[
a_{s,q}(c,c')=\mathbf 1\{r_s(c,q)\ne r_s(c',q)\},\qquad (c,c')\in P.
\]

For a set \(E\) of distinct acquired coordinates, inherited separation is

\[
D_p(E)=\sum_{(s,q)\in E}a_{s,q}(p).
\]

A contract \(C=(t,s,d)\) requires \(D_p(E)\ge d\) for every pair \(p\in I_t\), where \(I_t\) is the set of classes distinguished by target \(t\). Sensor \(s\) restricts new acquisitions at that stage; it does not erase inherited contributions from other sensors.

Partition coordinates only when they share both sensor and the complete separation vector on \(P\). Group \(g\) has vector \(a_g\), actual capacity \(M_g\), and retained original members. Write \(n_g(E)\) for the number already acquired. The reduced state is the current route stage together with \(n(E)\); its remaining capacity is \(M-n(E)\). For an admissible acquisition count vector \(u\),

\[
D_p(E)=\sum_g n_g(E)a_g(p),\qquad
0\le u_g\le M_g-n_g(E),\qquad
c(u)=\sum_g u_g,\qquad n'=n+u.
\]

Only groups with an allowed stage sensor may have positive \(u_g\). These quantities define a finite deterministic transition system with contract predicates and unit acquisition costs. No response-conditioned adaptive policy is assumed.

**Specialization proposition: exact preservation of finite-route planning.** With a fixed kernel, contracts depending exclusively on the stated distances, no repeated acquisition, unit coordinate costs and admissibility determined by the same sensor and route stage, two inherited sets \(E\) and \(F\) satisfying \(n(E)=n(F)\) admit matching feasible plans with the same costs along any fixed finite route. Consequently, feasibility and optimal route cost agree. This is a sufficiency result, not a claim of a minimal quotient or a new general abstraction theorem.

**Proof.** Equal counts yield equal complete distance vectors and equal remaining capacities. Every concrete acquisition from \(E\) determines counts \(u\) bounded by those capacities. From \(F\), choose exactly \(u_g\) unused members of each group; their existence follows from equal remaining capacity. The sensor restriction, cost and successor count vector are identical. The next contract is satisfied in one state exactly when it is satisfied in the other. The construction is symmetric. Induction over the fixed finite route matches all attainable costs and preserves infeasibility as well as minima. \(\square\)

For \(T\) route stages, this also gives the exact integer formulation

\[
\min\sum_{k=1}^{T}\sum_g u_{k,g},\qquad u_{k,g}\in\mathbb Z_{\ge0},
\]

subject to stage sensor restrictions and

\[
\sum_{j=1}^{k}u_{j,g}\le M_g-n_g(E_0),
\]

\[
\sum_g\left(n_g(E_0)+\sum_{j=1}^{k}u_{j,g}\right)a_g(p)\ge d_k,
\qquad p\in I_{t_k}.
\]

A concrete plan induces an integer solution of equal cost; an integer solution can be realized by distinct original members because cumulative capacity is respected. This encoding permits additional early acquisition when useful; it does not assume that separately minimal stages always form a globally optimal route. Problem-specific grouping may use only the active constraints if it preserves both stages and shared capacity when a sensor repeats; the full-pair partition supplies a sufficient construction for the stated family.

| Sensor | Original coordinates | Full-pair patterns | Maximum capacity | Groups with capacity above one |
|---|---:|---:|---:|---:|
| EXACT | 4,017 | 3,971 | 3 | 45 |
| MODE | 4,017 | 3,300 | 15 | 473 |
| ACTIONABLE | 4,017 | 609 | 159 | 317 |
| Total typed | 12,051 | 7,880 | — | 835 |

The archived v3 verification reconstructs these patterns and reproduces the 204 local certificates. Three terminal evidence sets use multiplicity within a pattern, so presence/absence alone is insufficient for those archived witnesses. The 93 distinct archived evidence sets induce 93 distinct reduced states: the corpus demonstrates coordinate grouping and the preservation property, not observed merging of these histories or measured planning acceleration.

The companion two-stage corpus has 46 fixed-route optima, supported by integer witnesses and matching rounded rational lower bounds. Eleven improve on historical witness choices, while 35 retain their costs. Its later tie audit found first-stage-minimal witnesses attaining the joint optimum in all eleven improved routes; the completed catalog supplies locally minimal stages and a route-optimal total for each frozen case. This establishes a finite existence result. It neither supplies a destination-blind tie-breaking policy nor proves that every instance admits such a plan. The descriptive sum 335 to 320 combines independent route costs and is not the cost of one shared experiment. Thirteen of 23 squares retain unequal optimal route costs under their respective intermediate-contract and sensor restrictions; that asymmetry alone is not physical holonomy.

The relation to state abstraction is operational. Equal reduced states preserve admissible reduced actions, costs, successor reduced states and contract predicates. Li et al. (2006) and Abel et al. (2020) provide the relevant broader context; the finite preservation proof does not demonstrate that ECH lies outside their representational reach. Robust multicover and rational checking also have direct predecessors (Abbas et al., 2017; Szeider, 2026). What remains to establish is an additional structural result or a useful algorithmic advantage with the same information, task and resource budget.

The reduced planning state does not retain response labels needed to decode an observation, coordinate identities and hashes, receipts, times, permissions or authority. It does not automatically accommodate heterogeneous costs, unequal quality, expiry, changing kernels, history-dependent sensor responses or group failures. Such attributes require a refined state or a restricted claim. The full ledger therefore remains beside the planning state; compression of a decision problem does not authorize deletion of its audit record. The finite result does not grant operational permission or validate a physical branch.

**Evidence locations.** The preserved v3 source is `research/continuity_v3_20261013/evidence/quotient/COCIENTE_DE_PLANIFICACION_ES.md`; the exact partition and checks are under its `results/` directory. Joint routes, certificates and the post hoc tie audit are under `research/continuity_v3_20261013/evidence/ech_joint/`. Kernel inputs and local certificates remain under `research/continuity_v2_20261013/evidence/ech/`. This subsection uses those frozen results; any subsequent comparison must identify its own protocol and record.
<!-- V6_ADDITION_END:ECH_SPECIALIZATION -->

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

The framework deliberately separates generic signed transport from magnetic helicity.

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

The framework requires a domain-specific bridge before a signed fiber can be interpreted as physical helicity. Solar vector magnetograms provide such a test because the relevant signed proxy is not inferred from the visual geometry of an event cloud: it is reconstructed from the measured vector field and its horizontal derivatives.

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

<!-- V6_ADDITION_BEGIN:HEMISPHERIC_COMPARATOR -->
**Comparator clarification (V6).** Park, Leka and Kusano's 2020 preprint studies estimated magnetic-helicity flux and a statistical hemispheric preference, whereas the present 32-region panel uses a vertical current-helicity proxy. This is pertinent context, not a like-for-like replication dataset. Observable, sample, time window and strata must agree before importing a success probability or interpreting disagreement as failure of the same physical claim. The archived panel outcome above is unchanged.
<!-- V6_ADDITION_END:HEMISPHERIC_COMPARATOR -->

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

At the historical v1.5 checkpoint, the temporal execution reached the support-gate outcome `INSUFFICIENT_TEMPORAL_SUPPORT`: six snapshots qualified, but only one complete trajectory remained. Quality failures included the initial record for HARP 2920 (`QUALITY=70656`) and the six-hour record for HARP 5249 (`QUALITY=66560`). No temporal or forecasting model comparison was performed. This remains the observation-support result of that v1.5 attempt, not evidence for or against physical temporal transport; it is not the current status of the later v1.6 comparison described below.

<!-- V6_ADDITION_BEGIN:SOLAR_CURRENT_STATUS -->
### Current temporal status: v1.6 and the subsequent v3 diagnosis

The v1.5 support failure is historical. The later v1.6 run evaluated a frozen development comparison on 15 snapshots from three HARPs, producing 12 transitions, 16 components and five operators. The v3 continuation reconstructed its local errors and algebra without acquiring new observations, changing predictions or reopening the adjudication. These are successive records, not contradictory descriptions of a single gate.

| Operator | Operational description | Transitions improving over T0 | HARPs improving over T0 | Global NMSE | Relative NMSE gain against T0 |
|---|---|---:|---:|---:|---:|
| T0 | Identity/persistence reference | — | — | 0.595157570 | reference |
| H | Shared translation | 4/12 | 0/3 | 0.621751465 | −4.468379% |
| L | Frozen alternating contrast | 7/12 | 1/3 | 0.594013807 | +0.192178% |
| G | Affine operator using endpoint activity | 5/12 | 0/3 | 1.071522606 | −80.040154% |
| M | Sign change | 0/12 | 0/3 | 5.594851754 | −840.062269% |

Local improvements remain observations of this development set. For example, H improves NMSE by 41.798% in HARP 2920's last transition; the corresponding absolute loss and support must accompany any operational interpretation of that relative change. L's small aggregate NMSE improvement is accompanied by a 1.186546% deterioration in NMAE and does not satisfy the declared margin and fold requirements. The retained outcome is `NO_DEVELOPMENT_DOMINANT_LIFT`. G uses activity from the final endpoint, so its comparison is conditional reconstruction rather than an information-matched ex ante forecast. The 960 cells and 1,200 overlapping aggregates do not constitute independent empirical replications.

**Calendar-time qualification.** This leave-one-HARP-out (LOHO) development comparison is retrospective cross-region transfer, not a historical real-time replay. The archived snapshot dates place HARP 401 in March 2011, HARP 2920 in July 2013 and HARP 5249 in March 2015. The coefficients for the 2011 held-out region use the 2013 and 2015 regions; those for the 2013 held-out region use 2011 and 2015. Thus causal dependence on the initial state within a prediction formula does not make the fitted procedure available at the historical issue time. This does not show a violation of the declared retrospective LOHO design. It limits the interpretation: even H/L, independently of G's endpoint covariate, are not demonstrated as contemporaneously deployable forecasts for those early dates. The 2015 fold uses earlier training regions, but that fact alone supplies neither a complete vintage audit nor an independent prospective trial. Dates and fold membership are recorded in `evidence/solar_local/SNAPSHOT_COVERAGE_ALL_15.csv` and `TRAIN_HARP_CONTRIBUTIONS_ALL_192.csv` under continuity v3.

For training HARPs A and B with five snapshots and four transitions each, the fitted translations satisfy

\[
b_H=\frac{(x_4-x_0)_A+(x_4-x_0)_B}{8},
\qquad
b_L=\frac{\sum_{R\in\{A,B\}}(-x_0+2x_1-2x_2+2x_3-x_4)_R}{8}.
\]

H's coefficient telescopes to endpoints; this does not make its normalizers or evaluation independent of interior snapshots. It tests transferable mean drift, not every possible helical geometry. L retains a particular alternating contrast, not a universal lemniscatic topology. In the fold evaluating HARP 5249, the two training HARPs have opposite signs of mean drift in all 16 components. The v3 decomposition found a negative mean alignment contribution for H in all three folds. These diagnostics explain a failure of shared-drift transfer while preserving local favorable transitions.

The v3 independent numerical checks reproduce 43,924 comparisons with maximum difference 2.8422 × 10⁻¹⁴. That is evidence of numerical reconstruction, not new physical measurements or independent instrumental accuracy. The local tables and algebra are retained at `research/continuity_v3_20261013/evidence/solar_local/`; the v1.6 results retain their development status.

| Record | Question resolved | Preserved outcome and limit |
|---|---|---|
| Direct-field proxy reconstruction | Does the implementation reproduce the specified boundary-field proxy and conventions? | Passed against indices from the same underlying field products; not independent instrumentation. |
| Hemispheric panel | Does this selected proxy panel satisfy its declared preference rule? | Not replicated; different from universal absence or a matched flux study. |
| Solar v1.5 | Was temporal observational support sufficient for that attempted continuation? | Insufficient support; no scored temporal-model comparison at that stage. |
| Solar v1.6 | Do the frozen development operators meet the declared dominance rule? | No dominant lift; local improvements and information differences remain explicit. |
| Solar v3 | What explains those fixed operators and local errors? | Post hoc algebra and reconstruction; no new confirmation or outcome-guided deployment. |

A future local policy must recognize favorable conditions before the target transition and compare against persistence, regularized local drift, autoregression and similarly informed state-dependent transport where relevant. Historical error-based regime discovery remains descriptive until evaluated on untouched appropriate observations. Useful local competence does not require a favorable global average, but a deployment rule needs its own timing, coverage, cost and harm evaluation.

A separate flux-gate question remains unresolved. Liu et al. (2026) explain why evaluation of induction for locally fitted DAVE4VM velocities must respect the derivatives used inside the fitting window rather than assume that differentiating the assembled velocity map gives the same object. The recovered record does not contain sufficient original v1.3 implementation to adjudicate that issue here. It is a targeted implementation question, not a diagnosed bug and not a reason to reverse the archived gate. Recovery and inspection must precede any corrected interpretation, and even a corrected operator would not establish unique helicity-flux identification.
<!-- V6_ADDITION_END:SOLAR_CURRENT_STATUS -->

### Contribution and limits

The numbered results collect established information-theoretic and coordinate principles, elementary separation arguments, and consequences for scientific computation. Counting them does not establish nine novel theorems. Berry (1984), Takens (1981), Eckmann et al. (1987), and de Silva et al. (2011) provide antecedents on geometric phase, reconstruction, recurrence description and circular coordinates; none alone establishes the broader empirical program. Rothenberg (1971) supplies an identification setting whose regularity conditions are essential. The contribution pursued here is an explicit observation-and-adjudication contract, together with the finite ECH instantiation of task-relative state sufficiency and the separation of planning state from audit lineage. The present related-work comparison identifies direct predecessors in causal states, predictive state representations, state-action abstraction, robust test design and independently checked optimization. It therefore does not establish priority for the general principles or a performance advantage for the composition. A differential theorem, algorithmic advantage or empirically discriminating observation contract remains necessary for a stronger novelty claim.

Fail-closed computation helps only when the blocked claim is named accurately. Source HOLD, first-order rank failure, absent prospective gain, unreplicated population pattern and unresolved physical interpretation are different states. Keeping them distinct permits independent research branches to progress without promoting an unverified global ontology or making all branches wait on an unrelated acquisition defect.

## 17. Conclusion

The central logical restriction remains:

\[
\boxed{\text{projected recurrence} \not\Rightarrow \text{state return}.}
\]

The scientific task is to specify the state and transport experiment, distinguish operator nonidentity from realized nonreturn, assess regular or nonregular identification, apply the correct sign transformation law, and evaluate the added state for a declared target. Physical helicity requires an additional domain definition and measurement contract. Negative comparisons, justified nonidentification, inconclusive evidence and predictive bounds below materiality are distinct legitimate outcomes. The mathematical distinctions are not themselves empirical hypotheses; their domain instantiations become falsifiable through explicit rivals, estimands and observation contracts.


<!-- V6_ADDITION_BEGIN:CONCLUSION_EXTENSION -->
For the current finite planning instance, the useful state lies between a contract label that can lose acquisition information and a full audit history that retains more than planning needs. Pattern counts with true remaining capacities preserve the stated transition and cost problem; the full ledger preserves separate custody obligations. This is the demonstrated mechanism connecting the abstract distinction to an explicit computational task. It is not a new general principle of sufficient state and it does not entail a physical helix.

The empirical branches require their own observation-to-mechanism bridges. The solar comparison now has actual development outcomes and local transfer diagnostics beyond the earlier support failure; the seismic terminal retains its closed, target-specific negative result and separate historical eligibility reservations. A future contribution must improve a discriminating prediction, decision or identification claim against adequately informed rivals, or derive a structural guarantee not supplied merely by relabeling established concepts. The present revision preserves those boundaries while making the common task-relative question explicit.
<!-- V6_ADDITION_END:CONCLUSION_EXTENSION -->

## References

Berry, M. V. (1984). Quantal phase factors accompanying adiabatic changes. *Proceedings of the Royal Society A*, 392, 45–57. https://doi.org/10.1098/rspa.1984.0023

de Silva, V., Morozov, D., & Vejdemo-Johansson, M. (2011). Persistent cohomology and circular coordinates. *Discrete & Computational Geometry*, 45, 737–759. https://doi.org/10.1007/s00454-011-9344-x

Eckmann, J.-P., Kamphorst, S. O., & Ruelle, D. (1987). Recurrence plots of dynamical systems. *Europhysics Letters*, 4, 973–977. https://doi.org/10.1209/0295-5075/4/9/004

Takens, F. (1981). Detecting strange attractors in turbulence. In *Dynamical Systems and Turbulence, Warwick 1980*. Lecture Notes in Mathematics 898. Springer. https://doi.org/10.1007/BFb0091924

Bobra, M. G., Sun, X., Hoeksema, J. T., Turmon, M., Liu, Y., Hayashi, K., Barnes, G., & Leka, K. D. (2014). The Helioseismic and Magnetic Imager (HMI) Vector Magnetic Field Pipeline: SHARPs—Space-Weather HMI Active Region Patches. *Solar Physics*, 289, 3549–3578. https://doi.org/10.1007/s11207-014-0529-3

Hoeksema, J. T., Liu, Y., Hayashi, K., Sun, X., Schou, J., Couvidat, S., et al. (2014). The Helioseismic and Magnetic Imager (HMI) Vector Magnetic Field Pipeline: Overview and Performance. *Solar Physics*, 289, 3483–3530. https://doi.org/10.1007/s11207-014-0516-8

Kullback, S., & Leibler, R. A. (1951). On information and sufficiency. *The Annals of Mathematical Statistics*, 22(1), 79–86. https://doi.org/10.1214/aoms/1177729694

Rothenberg, T. J. (1971). Identification in parametric models. *Econometrica*, 39(3), 577–591. https://doi.org/10.2307/1913267

<!-- V6_ADDITION_BEGIN:REFERENCES -->
Abbas, W., Sela Perelman, L., Amin, S., & Koutsoukos, X. (2017). Resilient sensor placement for fault localization in water distribution networks. *Proceedings of the ACM/IEEE International Conference on Cyber-Physical Systems*. https://doi.org/10.1145/3055004.3055020

Abel, D., Umbanhowar, N., Khetarpal, K., Arumugam, D., Precup, D., & Littman, M. L. (2020). Value preserving state-action abstractions. *Proceedings of the 23rd International Conference on Artificial Intelligence and Statistics*, PMLR 108, 1639–1650. https://proceedings.mlr.press/v108/abel20a.html

Gneiting, T., & Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *Journal of the American Statistical Association*, 102(477), 359–378. https://doi.org/10.1198/016214506000001437

Li, L., Walsh, T. J., & Littman, M. L. (2006). Towards a unified theory of state abstraction for MDPs. *Proceedings of the International Symposium on Artificial Intelligence and Mathematics*. Author manuscript: https://thomasjwalsh.net/pub/aima06Towards.pdf

Littman, M. L., Sutton, R. S., & Singh, S. (2001). Predictive representations of state. *Advances in Neural Information Processing Systems*. Official proceedings manuscript: https://papers.nips.cc/paper_files/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf

Liu, J., Sun, X., Schuck, P. W., & Daldorff, L. K. S. (2026). Towards a robust estimate of the solar photospheric Poynting flux and helicity flux. *arXiv:2604.16098v1*. https://arxiv.org/html/2604.16098v1. The inspected preprint metadata reports acceptance in *The Astrophysical Journal*; this revision cites the inspected preprint version and does not assert an independently verified journal DOI.

Moffatt, H. K. (1969). The degree of knottedness of tangled vortex lines. *Journal of Fluid Mechanics*, 35, 117–129. Author manuscript: https://www.damtp.cam.ac.uk/user/hkm2/PDFs/Moffatt_1969_JFM_35_117.pdf

Park, S.-H., Leka, K. D., & Kusano, K. (2020). Magnetic helicity flux across solar active region photospheres: I. Hemispheric sign preference in Solar Cycle 24. *arXiv:2010.06134*. https://arxiv.org/abs/2010.06134. Year refers to the inspected preprint; the related publication DOI is https://doi.org/10.3847/1538-4357/abbb93.

Shalizi, C. R., & Crutchfield, J. P. (2001). Computational mechanics: Pattern and prediction, structure and simplicity. *Journal of Statistical Physics*, 104. https://doi.org/10.1023/A:1010388907793. Author text: https://arxiv.org/html/cond-mat/9907176v2.

Simon, B. (1983). Holonomy, the quantum adiabatic theorem, and Berry's phase. *Physical Review Letters*, 51, 2167–2170. https://doi.org/10.1103/PhysRevLett.51.2167

Szeider, S. (2026). VIPR certificate construction from black-box ILP solvers. *32nd International Conference on Principles and Practice of Constraint Programming*, LIPIcs 379, 52:1–52:14. https://doi.org/10.4230/LIPIcs.CP.2026.52
<!-- V6_ADDITION_END:REFERENCES -->
