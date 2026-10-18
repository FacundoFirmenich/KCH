# Claim Identifiability in AI Evaluation: Proof-Carrying Boundaries and Open-Weight Mechanistic Collisions

## Abstract

Contemporary AI evaluation routinely moves from observed performance to claims about latent mechanism, cognition, biology, alignment, agency, or authority. Such moves are valid only when the target property is identifiable from the available observation and intervention family. We introduce a typed framework for claim identifiability in statistical-computational software systems (SSEC) and their deployed technical-statistical-computational configurations (CTEC). A property `q` is identifiable from an observation `O` over an admissible class `M` exactly when `q` is constant on every fiber of `O`, equivalently when `q = g o O` for some factor map `g`. Positive instances carry factorization certificates; negative instances carry constructive collision witnesses. We formalize the core results in Lean, exhaustively audit 813,297 finite partition pairs, quotient them into 1,347 non-isomorphic structures, and independently cross-check every class with Z3. We then bridge the formal calculus to real open-weight language models. In Qwen3-0.6B, doubling the layer-14 MLP output changes hidden states by 31.6% in relative L2 while preserving all 12 frozen multiple-choice decisions; the same intervention changes 4 of 12 held-out decisions. A cumulative observation lattice shows that the maximum invisible intervention contracts sharply as observations are refined from top-1 choice to rankings, quantized probabilities, and vocabulary-level signatures. In OLMo2-1B, a development-selected layer-14 MLP ablation preserves all 12 independent observation decisions despite approximately 69.6% hidden displacement and changes 3 of 12 frozen counterfactual decisions. These results do not establish global mechanistic equivalence, absence of understanding, or any biological or phenomenal conclusion. They establish a narrower and stronger result: finite behavioral equality is relative to an observation operator and does not by itself identify a declared internal intervention state. We conclude with a fail-closed evaluation architecture in which statistical, behavioral, mechanistic, biological, phenomenal, causal, genealogical, control, and authority claims require separate identifying bridges.

## 1. Introduction

The phrase *artificial intelligence* encourages comparisons between artificial systems and biological intelligence as though both occupied a single scalar order. Modern learned models can exceed humans on local tasks, generate fluent language, and participate in increasingly autonomous software configurations. None of those observations, however, determines what latent properties the observations identify.

A high benchmark score may establish task-relative predictive performance. It does not automatically identify the mechanism that generated the score. A behavioral resemblance may support an analogy within a declared domain. It does not by itself establish neural, biological, phenomenal, normative, or political equivalence. Likewise, a system's ability to produce a candidate action does not grant permission or authority to execute it.

We treat this as an identification problem rather than a terminological dispute. Let `M` be an admissible class of systems, `O : M -> Y` an observation operator, and `q : M -> Q` a target property. The central question is:

> Under what conditions does the observed value `O(m)` determine `q(m)` within `M`?

The answer is exact: `q` must be constant on every observation fiber. Equivalently, there must exist a factor map `g` such that `q = g o O`. If two admissible systems produce the same observation but differ in the target property, no estimator using only that observation can identify the property.

This formulation does not deny that behavior can reveal mechanism. It determines when it does, relative to an admissible class and an observation family. Enriching observations, adding interventions, restricting the admissible class, or introducing structural assumptions can contract equivalence classes and recover identification. The appropriate scientific result may therefore be `IDENTIFIABLE`, `NOT_IDENTIFIABLE`, `CONDITIONALLY_IDENTIFIABLE`, `RECOVERABLE_BY_PROBE`, or `PRACTICALLY_UNSTABLE`—not a forced scalar score.

We use two object classes. A **statistical-computational software system (SSEC)** is the executable learned or hybrid artifact: architecture, parameters, data-dependent estimation, predictive law, decision rule, memory, and software environment. A **technical-statistical-computational configuration (CTEC)** adds hardware, energy, networks, tools, operators, institutions, permissions, leases, effectors, and receipts. The distinction prevents effects of a deployed sociotechnical configuration from being attributed to an isolated model artifact.

### Contributions

1. **Typed claim identifiability.** We separate statistical, behavioral, mechanistic, biological, phenomenal, causal, genealogical, control, and authority claims. Cross-plane inference requires an explicit bridge with assumptions, an observation or intervention operator, a validation criterion, and a falsifier.
2. **Proof-carrying outcomes.** Identifiable claims carry factorization certificates; non-identifiable claims carry collision witnesses. `NOT_IDENTIFIABLE` is a valid terminal scientific state.
3. **Formal verification and structural quotient.** We prove the core theorems in Lean, exhaustively audit all finite partition pairs through seven worlds, quotient irrelevant relabelings, and independently cross-check the 1,347 resulting classes with Z3.
4. **Real open-weight collision witnesses.** We intervene on Qwen3-0.6B and OLMo2-1B using frozen model revisions and real ARC-Challenge stimuli, obtaining exact behavioral collisions alongside large internal changes and held-out counterfactual separation.
5. **Observation-lattice frontier.** We construct cumulative behavioral signatures and empirically verify that intervention invisibility contracts under operator refinement and sample enlargement.
6. **Architecture-relative intervention quotient.** We separate intervention commands, realized internal transitions, observations, and authority, revealing when architectural symmetries collapse nominally different controls before observation.

## 2. Typed systems and claims

### 2.1 Statistical-computational software systems

A SSEC is represented as

`S = <A, Theta, D, L, U, Q, delta, X>`,

where `A` is architecture, `Theta` parameters and state, `D` data or experience, `L` loss or statistical score, `U` the update procedure, `Q` the learned predictive law or scoring function, `delta` the decision or decoding rule, and `X` the execution environment.

The canonical learned pipeline is

`D --(U,L)--> theta_hat --Q_theta--> q_hat(z | x,c) --delta--> o`.

For autoregressive language models, generation is iterated conditional prediction plus a decoding policy. A deterministic decoder does not remove the statistical nature of the learned predictive distribution.

Not every historical AI system is a SSEC. Pure rule systems and theorem provers may be logical-computational systems. Many deployed systems are hybrids. The type is assigned by executable structure, not by marketing terminology.

### 2.2 Technical-statistical-computational configurations

A deployed configuration is

`C = <S,H,E,N,T,O,I,P,Lambda,R>`,

where `H` is hardware, `E` energy and material resources, `N` networks, `T` tools, `O` human and organizational operators, `I` institutions and owners, `P` policies and permissions, `Lambda` authority leases, and `R` execution receipts.

The SSEC produces scores, candidates, predictions, or plans. The CTEC produces world effects. Capacity, permission, authority, execution, and responsibility are therefore distinct types.

### 2.3 Claim planes

We distinguish at least the following claim planes:

- statistical;
- behavioral;
- mechanistic;
- biological;
- phenomenal;
- causal;
- normative;
- genealogical;
- control;
- authority.

Evidence does not automatically inherit upward. Behavioral similarity can support a mechanistic claim only through an identifying bridge. Mechanistic evidence can support a biological claim only relative to explicit biological criteria and measurement assumptions. Capability evidence cannot construct an authority lease.

## 3. Claim identifiability

### 3.1 Definition

A target property `q : M -> Q` is identifiable from `O : M -> Y` over `M` when

`O(m1) = O(m2) => q(m1) = q(m2)`

for all admissible `m1,m2`.

Equivalently, `q` is constant on every fiber `O^{-1}(y)`.

### 3.2 Factorization theorem

Under the set-theoretic formulation above,

`q is identifiable from O <=> exists g : Im(O) -> Q such that q = g o O`.

The factor map is a positive certificate. A pair `(m1,m2)` satisfying

`O(m1) = O(m2)` and `q(m1) != q(m2)`

is a negative certificate.

The theorem is formalized in Lean together with:

- identifiability iff absence of a collision;
- a collision blocks factorization;
- adding a probe cannot destroy structural identifiability;
- a finer observation contracts the invisible set.

### 3.3 Observation refinement

An operator `O_f` refines `O_c` when

`O_c = r o O_f`

for some deterministic reduction map `r`.

For baseline `m0` and an intervention family `m_e`, define

`I_O(B) = {e : O^B(m_e) = O^B(m0)}`.

If `O_f` refines `O_c`, then

`I_{O_f}(B) subset I_{O_c}(B)`.

If `B subset B'` and the smaller observation is a restriction of the larger, then

`I_O(B') subset I_O(B)`.

The grid invisibility supremum is

`epsilon_hat*(B,O;G) = max(I_O(B) intersect G)`.

It need not be a contiguous change-point threshold: interventions can change behavior and later return to the baseline signature. It is a supremum over the tested grid.

### 3.4 Structural versus practical identification

Structural identification is distinct from numerical stability, finite-sample estimation, calibration, and power. A claim may factor through an observation yet be highly unstable. Conversely, no amount of computation repairs structural non-identification from an unchanged observation family.

## 4. Proof-carrying finite benchmark

We enumerate all observation and target-property partitions through seven worlds. Across sizes one through seven there are 813,297 partition pairs. Three criteria agree in every case:

1. partition refinement;
2. existence of a factor map;
3. absence of a collision witness.

Raw pair counts overstate structural diversity because world and block labels are arbitrary. We therefore canonicalize contingency matrices under independent row and column permutations. The quotient contains 1,347 non-isomorphic structures: 220 identifiable and 1,127 non-identifiable.

Every positive structure includes a factor map. Every negative structure includes a collision witness. A separately implemented Z3 decision procedure asks whether a function from observation blocks to target blocks can satisfy all worlds; it agrees on all 1,347 classes.

The benchmark therefore measures inferential structures rather than paraphrase count, family labels, or relabeled copies.

## 5. Empirical methods

### 5.1 Models and data

We use frozen revisions of:

- Qwen3-0.6B;
- OLMo-2-0425-1B-Instruct.

Real stimuli come from ARC-Challenge validation. Items are deterministically ordered by SHA-256 of their original identifiers. The task is not used to claim leaderboard accuracy; it supplies reproducible external prompts with four answer contents.

### 5.2 Permutation-controlled behavior

Multiple-choice models are sensitive to answer order. Each item is rendered under four cyclic permutations. Displayed A/B/C/D scores are mapped back to original answer contents and averaged. The observation is therefore defined over content-level scores rather than one arbitrary label placement.

### 5.3 Internal intervention

For layer `l`, the MLP output is transformed as

`h_l^MLP -> c h_l^MLP`.

We retain exact intervention receipts. Hidden-state relative L2, cosine distance, and full-vocabulary next-token Jensen-Shannon divergence quantify realized effects. Top-1 equality is not treated as equality of distributions or internal states.

### 5.4 Frozen observation and counterfactual sets

Intervention selection uses a disjoint development set when selection is required. The observation set evaluates exact collision. A frozen counterfactual set evaluates whether the same unchanged intervention is functionally separable under additional stimuli.

## 6. Qwen collision witness

In Qwen3-0.6B, multiplying the layer-14 MLP output by two preserves all 12 permutation-averaged observation decisions:

`O_B(m0) = O_B(m1)`.

The intervention state differs by construction. Hidden states change by 31.56% in mean relative L2, with a minimum of 30.87% across observed items. Full-vocabulary next-token distributions have nonzero JS divergence. Applying the same intervention to a disjoint low-margin set changes 4 of 12 top-1 decisions.

Thus the frozen observation set does not identify the declared intervention state, while an enriched probe family separates the systems:

`m0 ~_{O_B} m1` but `m0 not~_{O_B' } m1`.

The result is claim-relative. It does not establish that the two systems have globally different mechanisms in every useful sense, nor that behavior can never identify mechanism.

## 7. Observation lattice

We construct cumulative signatures:

1. content top-1;
2. full ranking of four answer contents;
3. ranking plus 4-bin choice probabilities;
4. plus 8-bin probabilities;
5. plus 16-bin probabilities;
6. plus 32-bin probabilities;
7. plus ordered full-vocabulary top-8 token IDs;
8. plus ordered full-vocabulary top-32 token IDs.

Each signature contains the preceding signature. Exact equality at a fine level therefore implies equality at every coarser level.

At 16 observed items, the grid invisibility supremum contracts as follows.

| Layer | Top-1 | Rank-4 | Choice Q8 | Choice Q32 | Vocab top-32 |
|---:|---:|---:|---:|---:|---:|
| 4 | 0.75 | 0.10 | <0.05 | <0.05 | <0.05 |
| 14 | 0.35 | 0.05 | <0.05 | <0.05 | <0.05 |
| 24 | >=2.00 | 0.75 | 0.35 | 0.05 | <0.05 |

Top-1 is therefore a coarse observation operator. At layer 24, an intervention with scale three changes hidden states by approximately 50.4% relative L2 yet remains invisible to all tested top-1 decisions. Fine vocabulary-level signatures expose every nonzero tested intervention.

The result does not imply that the chosen lattice is cognitively privileged. It demonstrates that claims of “same behavior” depend on which information the evaluator retains.

## 8. Substantive inter-model replication

The first OLMo positive-scaling experiment produced an exact top-1 collision but almost no realized post-layer displacement. OLMo2 applies RMS normalization after feedforward output, making positive scalar multiplication approximately invariant. This exposed a two-stage map:

`intervention control --R_A--> realized transition --O--> observation`.

Different commands may be collapsed by the architecture-relative realization map `R_A` before observation. We therefore select layer and intervention using only a development set and require minimum realized-effect floors.

Across layers 2, 5, 8, 11, and 14 and scales 0, 0.5, 1.5, 2, 3, and 5, the selected candidate is complete ablation of the layer-14 MLP. On development it preserves 8 of 8 decisions, changes hidden states by 69.93% relative L2, and yields JS divergence 0.0224.

On an independent observation set it preserves 12 of 12 decisions while producing 69.57% mean relative hidden displacement and JS divergence 0.0214. On the frozen counterfactual set it changes 3 of 12 decisions.

This establishes a substantive inter-model collision: a large realized transition is hidden from the frozen top-1 operator and revealed by additional probes.

## 9. Intervention quotient

Let `E` be intervention commands, `R_A : E -> M` the architecture-relative realization map, and `O : M -> Y` the observation. The empirical map is `F = O o R_A`.

Two non-identifiability sources are distinct:

1. realization collision: `R_A(e1) = R_A(e2)` for different commands;
2. observation collision: `R_A(e1) != R_A(e2)` but `O(R_A(e1)) = O(R_A(e2))`.

Define `e1 ~_A e2` when `R_A(e1) = R_A(e2)`. The effective intervention space is the quotient `E / ~_A`. Raw control magnitude is not a model-independent causal effect size.

This separation also prevents control, realized state, observed behavior, and authority from being conflated.

## 10. Related work and novelty boundary

The framework does not claim novelty for factorization-based identifiability, comparison of statistical experiments, causal abstraction, interchange interventions, proof checking, answer-order sensitivity, or steering-vector non-identifiability.

Direct contemporary work proves that steering directions can form large behaviorally indistinguishable equivalence classes and can become identifiable under added structural assumptions. Work on mechanistic interpretability argues that causal claims require disclosed identification assumptions and that validation metrics are not identification. Formal-verification benchmarks provide machine-checkable correctness, while recent specification-faithfulness work shows that a valid proof does not guarantee that the formal statement captures the intended informal claim. NIST ARIA evaluates systems through model testing, red teaming, and user testing rather than model metrics alone.

The residual contribution evaluated here is their composition in a typed, proof-carrying architecture that spans claim planes, reports negative certificates, quotients structural and intervention symmetries, executes real open-weight collisions, refines observations monotonically, and separates evidence from authority.

## 11. Limitations

1. The empirical results use two model families and one behavioral domain.
2. ARC multiple-choice observations are convenient but not behaviorally exhaustive.
3. The intervention families are scaling, ablation, and a preliminary pre-softmax operator; learned directions and activation patching remain open.
4. Grid frontiers are censored and should not be interpreted as continuous exact thresholds.
5. A deterministic item sample does not provide population uncertainty across prompt samples.
6. Controlled-language semantic fidelity does not solve unrestricted natural-language interpretation.
7. The framework does not determine whether a future artificial system could be conscious or alive.
8. Formal authority separation must be connected to runtime refinement before deployment guarantees are claimed.

## 12. Conclusion

AI evaluation frequently asks an observation to support a stronger property than it identifies. A rigorous alternative begins by typing the claim, declaring the admissible system class, specifying the observation and intervention family, and requiring a positive factorization certificate or a negative collision witness.

Our formal and empirical results show that finite behavioral equality can conceal materially different internal interventions, that additional probes contract the compatible class, and that “same behavior” changes as the observation operator is refined. These results are sufficient to block automatic inference from task behavior to mechanism, biology, phenomenology, normativity, or authority. They are not sufficient to rule out such inferences under richer identifying bridges.

The scientific question is therefore not whether an artificial system is globally “more intelligent” or “the same as” a biological organism. It is which property is being claimed, which observation is available, what assumptions make the property identifiable, and what evidence would falsify the bridge.

## References

- Blackwell, D. Equivalent Comparisons of Experiments. *Annals of Mathematical Statistics* (1953).
- Geiger, A. et al. Causal Abstractions of Neural Networks. arXiv:2106.02997 (2021).
- Geiger, A. et al. Inducing Causal Structure for Interpretable Neural Networks. arXiv:2112.00826 (2021).
- Pezeshkpour, P. and Hruschka, E. Large Language Models Sensitivity to the Order of Options in Multiple-Choice Questions. Findings of NAACL (2024).
- Rahwan, I. et al. Machine Behaviour. *Nature* 568, 477–486 (2019).
- Sutter, D. et al. The Non-Linear Representation Dilemma: Is Causal Abstraction Enough for Mechanistic Interpretability? arXiv:2507.08802 (2025).
- Thakur, A. et al. CLEVER: A Curated Benchmark for Formally Verified Code Generation. NeurIPS Datasets and Benchmarks (2025).
- Venkatesh, S. and Kurapath, A. M. On the Identifiability of Steering Vectors in Large Language Models. arXiv:2602.06801 (2026).
- Lin, Z. and Liu, F. Mechanistic Interpretability Must Disclose Identification Assumptions for Causal Claims. arXiv:2605.08012 (2026).
- Santos-Grueiro, I. Alignment Verifiability in Large Language Models: Normative Indistinguishability under Behavioral Evaluation. arXiv:2602.05656 (2026).
- Amster, M. et al. claimcheck: Measuring and Improving Specification Faithfulness. arXiv:2610.17358 (2026).
- Jensen, T. et al. ARIA Evaluation Planning Manual. NIST AI 200-3 (2026).
