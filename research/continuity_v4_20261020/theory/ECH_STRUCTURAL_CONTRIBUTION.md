# Certified two-stage evidence acquisition: local minima, completion cost, and sufficient state

20 October 2026. Structural clarification of the frozen ECH corpus. No new optimization, observations, synthetic instances, or empirical adjudication are introduced here. The contribution is a task-specific formulation and interpretation of existing exact certificates. Bellman decomposition, multicover, state abstraction, and rational certification are established methods; no priority claim is made for these principles.

## 1. Model and relation to prior work

The finite kernel has 65 functional classes and 2,080 unordered class pairs. Each of three sensors admits 4,017 masks. A coordinate is a typed pair `(sensor, mask)`: identical masks at different sensors are different acquisitions. The frozen response function defines a binary separation vector \(a_q\) over all class pairs. Inherited evidence \(E\) is a set of distinct coordinates, with distance \(D_p(E)=\sum_{q\in E}a_q(p)\).

A contract specifies a target pair set \(I\), a distance requirement \(d\), and the sensor permitted for new acquisitions. Inherited coordinates from other sensors continue contributing. For a fixed two-stage route, let \(Q_1,Q_2\) denote the permitted coordinate sets, \(C_1,C_2\) the intermediate and terminal contracts, and \(E_0\) the fixed inherited evidence. A legal plan consists of disjoint additions \(X\subseteq Q_1\setminus E_0\) and \(Y\subseteq Q_2\setminus(E_0\cup X)\), satisfying \(C_1\) after \(X\) and \(C_2\) after \(X\cup Y\). Costs are unit acquisition counts. There is no expiry, replacement, destructive update, response-dependent action policy, or additional scheduling cost.

Pair separation is a test-cover/multicover formulation. Resilient sensor placement already links multivalued responses, distance and multicover [1]. Rational witness-and-bound certification has direct precedents [2–3], including black-box solver certification [4]. State abstractions preserving decision properties are established [5–6]. ECH's candidate contribution concerns the exact combination of inherited evidence, stage-specific admissibility, intermediate contracts, capacity preservation and inspectable certificates. Its advantage over comparable implementations remains a separate empirical question.

## 2. Completion cost and the exact decomposition

Let \(\mathcal F\) be the finite family of first-stage additions satisfying \(C_1\), and let

\[
m=\min_{X\in\mathcal F}|X|,\qquad
V(X)=\min\{|Y|:Y\text{ legally completes }X\text{ to }C_2\}.
\]

Set \(V(X)=+\infty\) if no completion exists. Assume a finite jointly feasible optimum. Define

\[
J=\min_{X\in\mathcal F}(|X|+V(X)),\quad
\mathcal M=\{X\in\mathcal F:|X|=m\},\quad
R=m+\min_{X\in\mathcal M}V(X).
\]

**Proposition 1 (completion criterion).** A jointly optimal route with a locally minimum first stage exists if and only if some \(X\in\mathcal M\) satisfies \(V(X)=J-m\). Equivalently, \(R=J\).

**Proof.** A plan starting with such an \(X\) and an optimal completion has cost \(J\). Conversely, a jointly optimal plan with first-stage cost \(m\) has completion cost \(J-m\); a cheaper completion would contradict joint optimality. Since the restricted plans form a subset of all legal plans, \(J\le R\). Equality holds exactly when that subset contains an optimum. This is a finite optimal-substructure argument, not a new dynamic-programming theorem. □

Let the archived plan start with \(X_A\in\mathcal M\), and let its second step be optimal for that inherited state, as certified in the original bridge corpus. Write its total cost as \(A=m+V(X_A)\). If \(R\) is finite, then

\[
A-J=\underbrace{A-R}_{\text{choice among local minima}}
    +\underbrace{R-J}_{\text{benefit of allowing a nonminimum first stage}}.
\]

Both terms are nonnegative. The second is positive precisely when every joint optimum has first-stage cost greater than \(m\). A nonminimum first stage returned by a solver does not establish that inequality: another optimum may start minimally. If the archived second step were not conditionally optimal, \(A-R\) would also contain completion-policy inefficiency and could not be attributed solely to the first-stage tie.

For each attainable first-stage count \(k\), define \(v(k)=\min_{X\in\mathcal F,|X|=k}V(X)\), using infinity for empty or uncompletable families. Then \(J=\min_k[k+v(k)]\) and \(R=m+v(m)\). When \(v(m)\) is finite, nonminimum acquisition is strictly beneficial exactly when some \(k>m\) satisfies

\[
v(m)-v(k)>k-m.
\]

Thus the completion reduction must exceed its extra acquisition cost. The nondominated attainable pairs \((k,V(X))\) suffice for minimizing their sum. This characterization does not claim that the complete attainable frontier has been enumerated in ECH.

## 3. What can be postponed without changing final evidence?

**Proposition 2 (rescheduling a fixed final set).** Let \(U=X\cup Y\) be the additions of a legal plan. A partition with locally minimum first-stage cost and the same final set \(U\) exists if and only if there is \(B\in\mathcal M\) such that

\[
B\subseteq U\cap Q_1,\qquad U\setminus Q_2\subseteq B.
\]

**Proof.** The first inclusion makes \(B\) an available first-stage subset of the fixed additions. Its membership in \(\mathcal M\) establishes the intermediate contract and minimum cost. The second inclusion ensures that every coordinate postponed to \(U\setminus B\) is admissible in stage two. The additions remain disjoint, final evidence remains \(E_0\cup U\), and total unit cost remains \(|U|\). Conversely, any legal partition of \(U\) must place coordinates outside \(Q_2\) in the first step and must satisfy both inclusions. □

If \(Q_1=Q_2\), the condition reduces to the existence of an intermediate minimum \(B\subseteq U\). In particular, if \(m=0\), the empty first step works for every legal final set: all additions can be postponed. If the two typed sensor sets are disjoint, all coordinates in \(U\cap Q_1\) are forced into the first stage. Changing their acquisition time is then impossible without changing the final set.

Applied to any *optimal* final set, Proposition 2 gives a sufficient construction for \(R=J\). Existence of at least one such optimal final set is also necessary. It does not say that every solver-returned optimum admits that rescheduling, nor that an inclusion-minimal first set has minimum cardinality. No same-final-set containment search was performed here.

## 4. Sufficient planning state and its limits

Group coordinates only when they share a sensor and the same complete separation vector over all pairs. Group \(g\) has true capacity \(M_g\), vector \(a_g\), and inherited count \(n_g\). An acquisition vector satisfies \(0\le u_g\le M_g-n_g\), integer entries and stage-specific sensor admissibility. Distances and costs are

\[
D_p(n)=\sum_g n_ga_g(p),\qquad c(u)=\sum_g u_g,\qquad n'=n+u.
\]

**Proposition 3 (conditional sufficiency).** At the same route stage, equal count vectors admit identical reduced plans with equal costs for every fixed finite future route governed by the stated assumptions.

**Proof.** Equal counts imply equal distances and residual capacities. Any concrete acquisition induces an admissible integer vector \(u\). From another history with equal counts, the same number of unused members can be selected in every group because capacities agree. The resulting distances, stage-contract satisfaction, cost and successor counts agree. Applying this symmetric correspondence repeatedly preserves the attainable costs and infeasibility of every finite route. □

This is a specialization of behavior-preserving abstraction, not a proof of minimal state. It preserves planning, not response labels, decoding, timestamps, receipts or authority. For heterogeneous fixed coordinate costs, grouping additionally by exact cost is a sufficient refinement; equal counts within the refined groups preserve cost by the same proof. Expiry, quality, permissions, history-dependent responses or availability require their own sufficient attributes. This extension is mathematical only; the archived experiment uses unit costs.

## 5. Application to the frozen routes

The complete route-level decomposition is in `EXACT_SAVING_DECOMPOSITION_46.csv`; `STRUCTURAL_EVIDENCE_DEPENDENCIES.json` records hashes and provenance. Its values are read from existing exact certificates and the locally minimum lookahead catalogue, not estimated by a new solver.

| Certified family or structural subset | Result | Interpretation |
|---|---|---|
| All 46 fixed routes | \(R=J\) | Every route has a jointly optimal plan with minimum first-stage cost. |
| Eleven routes improved over archive | \(A-R>0\), \(R-J=0\) | Their certified savings arise from selecting another local minimum, with its optimal completion. |
| Other 35 routes | \(A=R=J\) | The archived plan already attains the joint optimum. |
| Thirty returned unrestricted witnesses | First-stage count exceeds \(m\) | A property of returned witnesses, not a necessity theorem. |
| Fourteen routes with \(m=0\) and identical sensors | Empty first step is sufficient | Proposition 2 explains postponability without invoking a numerical coincidence. |
| Sensor jurisdictions | 33 same-sensor; 13 different-sensor routes | Timing flexibility differs; equal aggregate optimum does not erase that distinction. |

For example, S06P2 has \(m=7\), \(A=9\), and \(R=J=7\): choosing an appropriate seven-coordinate first minimum satisfies the final contract without a second acquisition. S13P2 has \(m=7\), \(A=12\), and \(R=J=10\): the selected first minimum needs three additional coordinates rather than the five of the archived continuation. These are actual archived routes, not constructed examples.

The sums \(335\to320\) concern independent routes, not a shared experiment. The original quotient groups 12,051 coordinates into 7,880 patterns; 93 archived ledgers still give 93 distinct count states. Column grouping therefore does not establish measured state collisions or acceleration. The 204 local certificates and 46 joint certificates remain claims about the declared finite kernel.

## 6. Falsifiers, comparison, and remaining contribution

A feasible route with certified \(R>J\) would establish genuine value of relaxing first-stage minimality in that jurisdiction. A solver's nonminimum witness alone would not. A future minimum-first policy must also specify its tie rule and access to the destination: existence of a suitable minimum is not a destination-blind algorithm. Stagewise greedy may incur losses in its first cardinality, in its chosen minimum, or in its completion. The archive decomposition cannot be transferred unchanged to greedy without checking those components.

Relevant comparisons use equal target, inherited evidence, availability and information: an ungrouped versus grouped ILP isolates representation cost; destination-aware versus destination-blind policies isolate information differences; standard multicover and certified solvers test algorithmic utility. Generation, solution, rationalization and checking costs must be reported separately. No performance or external-generalization advantage is established by these propositions.

The scientific advance is an explicit distinction between the identity of a first-stage minimum, its downstream completion and the extra cardinality permitted by joint planning. In the frozen family, all observed archive savings belong to the first distinction. The next frontier is an implementable, fairly compared rule for selecting those useful states, or a structural class where its guarantee can be proved. This finite result grants neither operational authority nor physical helicity.

## References

1. Abbas et al. (2017), *Resilient Sensor Placement for Fault Localization in Water Distribution Networks*. ICCPS. https://doi.org/10.1145/3055004.3055020
2. Cheung, Gleixner and Steffy (2017), *Verifying Integer Programming Results*. IPCO. https://arxiv.org/abs/1611.08832
3. Eifler and Gleixner (2024), *Safe and Verified Gomory Mixed-Integer Cuts in a Rational Mixed-Integer Program Framework*. SIOPT. https://doi.org/10.1137/23M156046X
4. Szeider (2026), *VIPR Certificate Construction from Black-Box ILP Solvers*. CP. https://doi.org/10.4230/LIPIcs.CP.2026.52
5. Li, Walsh and Littman (2006), *Towards a Unified Theory of State Abstraction for MDPs*. https://thomasjwalsh.net/pub/aima06Towards.pdf
6. Abel et al. (2020), *Value Preserving State-Action Abstractions*. AISTATS. https://proceedings.mlr.press/v108/abel20a.html
