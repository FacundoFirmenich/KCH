# Conditional Predictive Limits of Signed Axial Transport on a Frozen California Fault Network

**Manuscript status:** integral working draft V6, 20 October 2026. The terminal post-2021 result is unchanged. This revision places the conditional estimand, the terminal evidence and the closest literature first. It adds no observations, fits, outcome openings or benchmark executions. The complete V5 manuscript is retained verbatim in the archival appendix, including every table, formula, reference, historical reservation and decision. The present main text governs the current interpretation; the appendix preserves the record rather than renewing any historical authorization.

**Contribution and readiness:** a source-qualified negative predictive case study of an additional signed axial-rotation term on a frozen external fault graph. This is not a new general forecasting-evaluation method, not a demonstration of physical nonhelicity, and not yet a verified comparison with all nearby marked-ETAS models. Editorial corrections are implemented here; remaining computational and inferential obligations are identified explicitly in Section 9.

## Abstract

We evaluate whether an additional signed axial rotation per network kilometer improves prediction of focal-mechanism orientation conditional on an event, its available metadata, previous mechanisms and a frozen external fault network. The primary result is a terminal temporal test on separately acquired post-2021 Bay Area and Parkfield events. A nondirectional census and external-fault preflight selected the two cohorts before directional scoring; a complete endpoint-junction graph and parent policy were then frozen. Against the executed nonhelical dynamic circular-regression rival, Bay Area gained 0.000227 nats per child and 0.0491% in axial RMSE on 1,196 test children. Parkfield lost 0.000611 nats per child while improving RMSE by 0.0136% on 421 test children. Both failed the declared conjunctive rule. Reported 97.5% moving-block-bootstrap upper endpoints, 0.001187 and 0.0000559 nats per child, lie below the prespecified material margin of 0.02; their inferential interpretation remains conditional on the model, graph, source, loss-dependence and resampling assumptions. The result restricts predictive benefit within this tested comparison, not geometric pitch, physical helicity or all forms of orientation transport. An earlier adaptive sequence is retained in full: it contains local improvements, negative decisions, prior-exposure qualifications and an unresolved historical event-membership reservation that does not automatically transfer to the terminal source. Comparison with ETAS models incorporating focal mechanisms and established forecast-evaluation methods narrows the candidate contribution to the specific signed network-transport contrast and its auditable stopping decision. No additional comparator performance or corrected empirical result is claimed by this revision.

## 1. Primary evidence: the terminal temporal test

The two jurisdictions must be read separately. Bay Area has a small positive point estimate for both recorded losses. Parkfield has a negative log-score difference and a small positive RMSE difference. These are distinct objectives, so their differing signs are not a contradiction. Neither cohort meets the declared material thresholds. The local results remain visible; a pooled score is not required to describe either one.

| Terminal jurisdiction | Test children | Mean log-score gain, nats/child | Relative axial-RMSE gain | Delta BIC, H minus rival | Reported bootstrap 95% lower endpoint | Reported bootstrap 97.5% upper endpoint |
|---|---:|---:|---:|---:|---:|---:|
| Bay Area | 1,196 | +0.000227 | +0.0491% | +6.543 | -0.000645 | 0.001187 |
| Parkfield–central San Andreas | 421 | -0.000611 | +0.0136% | +6.558 | -0.001440 | 0.0000559 |

These numbers are transcribed without refitting from V5 Section 7.3, preserved below. The different nominal labels of the lower and upper endpoints are retained as recorded; this table does not silently turn them into a single symmetric interval or a newly calibrated simultaneous confidence region.

A positive terminal cohort required at least 0.02 nats per child in log-score gain, at least 5% relative axial-RMSE improvement, delta BIC no greater than -10, and a positive moving-block-bootstrap lower bound. Neither cohort satisfied these necessary conditions. Expensive diagnostics that could not reverse that failed conjunction were not treated as a route to rescue it. No power or stability property is inferred merely from this early negative decision.

The archived outcome remains:

```text
SEISMIC_HELICAL_PROGRAM_CLOSED_WITH_UPPER_BOUNDS
```

This identifier records the precommitted stopping decision for the declared earthquake-catalog line. Its scientific interpretation is narrower than its shorthand: the executed signed-transport extension failed to earn the stated predictive benefit against its executed rival. It is not a theorem about all helicoidal mechanisms or a license to interpret every untested model as refuted.

### 1.1 What was fixed before directional scoring

The terminal graph contained 625 mapped fault polylines, 1,250 endpoint nodes, 837 graph edges and 212 endpoint junctions under a fixed 2 km radius. Interior projected crossings without endpoint proximity were not connections. Candidate parents were restricted to 30 days, 20 km network distance and at most 20 parents, with a fixed ETAS-like weighting law. Route orientation for 69,104 candidate edges was materialized before mechanism scoring. Static segment orientation was estimated on TRAIN only.

The terminal events were separately acquired from USGS records filtered as `earthquake`, without the historical numeric `ev_bl` selection. NCEDC monthly FPFIT mechanisms provided usable solutions for 99.10% and 98.74% of assigned events in Bay Area and Parkfield. The first stored FPFIT angle was treated as dip direction and converted to strike by subtracting 90 degrees modulo 360. The preserved chronology includes the blind census, fault-assignment preflight, final graph freeze and selected directional materialization; no step is backdated by the present revision.

New events in previously studied regions provide a temporal test. They do not provide replication in new geography, and the change of mechanism product must be considered when comparing historical and terminal measurement quality. Numerical replay on the same events is a separate property: V5 reports byte-identical terminal result JSON and metrics on rerun, not independent empirical replication.

## 2. Estimand, information set and observational unit

### 2.1 A conditional mark prediction

Let \(Y_j\in\mathbb R/\pi\mathbb Z\) denote the observable axial orientation of child event \(j\) in the declared fault-relative frame. The identification \(\psi\sim\psi+\pi\) removes eigenvector sign; the representation \(e^{2i\psi}\) is therefore appropriate to this axial target. The event is not a material particle traced continuously through the graph. The external graph provides a representation of possible paths; probabilistic parent weights do not establish a measured causal genealogy.

Let \(\mathcal F_j\) denote the intended information available after the child's nondirectional event metadata are known but before its target orientation is used for scoring. It includes the frozen graph and assignment policy, allowed past event and mechanism history, and parameters fitted or selected on the permitted earlier partitions. The child's time and location are conditioning inputs to this mark problem. Consequently the reported result is not, by itself, a prediction that the child will occur at that time and location. Claiming complete occurrence forecasting would require a point-process target, including event absence and the corresponding exposure measure, which this comparison does not establish.

Write \(q_H(\cdot\mid\mathcal F_j)\) and \(q_R(\cdot\mid\mathcal F_j)\) for the fitted axial predictive densities of the signed-transport extension and the executed nonhelical rival. The per-child contrast is

\[
D_j=\log q_H(Y_j\mid\mathcal F_j)-\log q_R(Y_j\mid\mathcal F_j),
\qquad
\widehat\Delta_J=\frac{1}{n_J}\sum_{j\in J}D_j,
\]

for a declared test jurisdiction \(J\). The population target is a conditional predictive contrast,

\[
\Delta_J=\mathbb E_J[D_j\mid\mathcal C],
\]

where \(\mathcal C\) records the trained models and the graph, source-selection and evaluation conditions under which the claim is made. This notation exposes the scope of the archived log-score comparison; it does not add a new fitted distribution or a new outcome to the study.

Conditioning on a trained pair of models and generalizing about an entire learning procedure are different inferential targets. The latter would require uncertainty assessment that accounts for relevant refitting, selection and graph construction, or an explicit reason for conditioning them away. The current revision does not silently promote model-conditional endpoints to unconditional guarantees for every future fitted model.

### 2.2 Child events, candidate edges and dependent losses

The terminal denominator is the number of scored children. The 69,104 candidate edges are possible contributions to parent assignments or weighted predictors, not 69,104 independent child outcomes. Children can share parents and histories; events can share fault segments and temporal windows. Chronological partitions regulate information access but do not make the losses independent.

Historical V5 tables use the label “test edges” for their scored units. That label and all denominators remain unchanged in the archival appendix. It must not be conflated with the terminal candidate-edge total or used to inflate the terminal sample size. Likewise, the 64 historical uncertainty perturbations are computational propagation draws, not 64 observational replications.

### 2.3 Axial normalization and the remaining implementation obligation

For an angle representative \(\psi\in[0,\pi)\), a density with respect to \(d\psi\) must satisfy

\[
\int_0^\pi q_\psi(\psi\mid\mathcal F_j)\,d\psi=1.
\]

If an implementation instead works with \(\phi=2\psi\in[0,2\pi)\), change of variables requires

\[
q_\phi(\phi\mid\mathcal F_j)=\tfrac12 q_\psi(\phi/2\mid\mathcal F_j).
\]

The common \(-\log2\) shift cancels from the paired log-score difference when both models use the same transformation and reference measure. This elementary normalization check does not certify that the archived implementation handled all conventions correctly. The exact density family, concentration fit, parent aggregation, support handling, zero-density treatment and numerical clipping policy must be recovered from the executed implementation before a complete likelihood audit can be declared. V5 describes dynamic circular regression but does not give that full formula; V6 does not fill the gap with an invented von Mises, wrapped-normal or mixture specification.

The same discipline applies to the clock of \(\mathcal F_j\): the intended information set is now explicit, while implementation-level compliance requires the appropriate prediction and input records. Specifying the contract and verifying the code are distinct achievements.

## 3. Closest prior work and the candidate contribution

ETAS and related self-exciting point-process models provide established ways to represent earthquake occurrence dependence (Hawkes, 1971; Ogata, 1988). They are scientific background, not a novelty claim of this study. The closest retrieved orientation-specific predecessor is Zhuang and Maita's 2020 SCEC poster, which uses ETAS-based stochastic reconstruction to model background focal mechanisms and parent–offspring rotations. Its primary document reports an ETAS extension with focal-mechanism distributions and fitting results. It is a poster, not a verified peer-reviewed prospective validation equivalent to the present terminal test. It nevertheless establishes that combining ETAS, focal mechanisms and parent–child orientation is insufficient as a novelty claim.

The candidate difference here is the additional **signed axial rotation per network kilometer**, evaluated using an externally specified fault-route representation and a declared temporal contrast. This difference must be assessed at the level of target, symmetry, geometry and information availability. The current literature search does not prove absolute priority for that combination, and the Zhuang–Maita model has not been implemented or scored on this terminal corpus in V6.

CSEP has long developed prospective comparative evaluation of earthquake forecasts (Schorlemmer et al., 2018). Brehmer et al. (2025; arXiv revision consulted in 2026) analyze consistent scores, calibration, discrimination and dependence in earthquake forecast comparisons. Their main count/expectation examples are not interchangeable with the axial mark target here. They provide a direct methodological comparison, rather than a numerical benchmark whose performance can be imported across targets. Proper scoring rules themselves are established theory (Gneiting and Raftery, 2007).

| Component of the present study | Closest established component | Candidate difference or retained value | What remains unestablished |
|---|---|---|---|
| Probabilistic parent candidates | ETAS/self-excitation | Frozen external-graph policy for this signed-transport contrast | Parentage as an observed causal genealogy |
| Parent–child orientation | Zhuang–Maita focal-mechanism extension | Signed axial term indexed by external network distance | Priority or empirical superiority over that marked-ETAS model |
| Gate-specific temporal comparison | CSEP and forecast-evaluation literature | Explicit adaptation history, terminal rule and source-specific case study | One globally calibrated confirmatory error rate for all gates |
| Log-score and uncertainty assessment | Proper scoring rules and dependent forecast evaluation | Recorded effects and conditional upper endpoints for this target | General coverage without an audit of loss dependence and the bootstrap |
| Local improvements | Conditional predictive ability (Giacomini and White, 2006) | Preservation of favorable and adverse jurisdictions | A validated rule recognizing those jurisdictions ex ante |
| Reproducible numerical record | Established provenance and computational reproducibility practices | Concrete preservation of failed acquisitions, reservations and adverse outcomes | Novelty of provenance itself, or truth of source semantics from hashes |

The defensible contribution is therefore a **specific, auditable negative empirical contrast**, with an explicit boundary between geometry, conditional predictive performance and physical interpretation. Its value does not depend on claiming invention of prospective testing, proper scoring, ETAS, local analysis or source hashing.

## 4. Interpretation of the material margin and bootstrap endpoints

The primary material margin was fixed at \(\delta=0.02\) nats per child. For a valid one-sided upper confidence bound \(U_J\), observing \(U_J<\delta\) supports exclusion of a gain at least that large at the stated confidence level and under the coverage assumptions. It does not establish \(\Delta_J=0\), bilateral equivalence, a bound on pitch, or a bound on field-level helicity. The distinction between failing to demonstrate superiority and excluding a material improvement is essential (Lakens, 2017).

The recorded Bay Area and Parkfield upper endpoints are smaller than \(\delta\). They are moving-block-bootstrap endpoints, not coverage guarantees obtained merely by selecting a percentile. Their interpretation requires that the resampling scheme adequately represents the relevant loss dependence, that the targeted conditional population is appropriate, and that any conditioning on fitting is disclosed. This revision explains that logic but does not recompute the endpoints or certify those assumptions anew.

If each of two one-sided 97.5% upper bounds had valid marginal coverage for its declared target, the union bound would permit a simultaneous coverage statement of at least 95% without requiring independence between cohorts. This is a conditional mathematical implication, not an additional empirical finding. The requisite marginal coverage has not been established by this editorial revision. No simultaneous guarantee is added to the reported results.

BIC remains an auxiliary diagnostic with a declared parameter count. Frequency searches, segmentation, graph choices and selection can produce complexity not captured by counting final coefficients. Conversely, an adverse BIC is not an ontological verdict. Here the negative decision also follows from the failed material gains, so the conclusion is not resting only on BIC.

The acceptance rule is a conjunction of requirements, not automatically a test with a known global type-I error or 80% joint power. Historical normal-approximation power calculations, preserved in V5 Section 6.1, concern their specified variance and dependence model. They do not establish the power of every conjunct after filtering, nor of the complete adaptive program. Reporting that distinction corrects the scope of the power claim without changing its archived calculation.

## 5. Comparators: executed, literature-based and still pending

The executed terminal comparison is the nonhelical dynamic circular-regression rival versus its signed-rotation extension. Static segment orientation was estimated on TRAIN. The extension did not obtain authority to alter the frozen parent policy. These facts delimit the completed comparison; they do not show that every nearby orientation model was implemented.

| Comparator or diagnostic | Current status | Fair-comparison condition | Allowed use of the opened terminal data |
|---|---|---|---|
| Executed dynamic nonhelical rival | Results reported and preserved | Same terminal target, graph and declared information | Reproduction or explicitly retrospective audit |
| Separate train-only segment-orientation model | Component described; separate terminal benchmark not established here | Same scored children and likelihood reference measure | Descriptive comparison only if subsequently executed |
| Parent orientation/persistence | Required nearby benchmark; no new execution in V6 | Same parent candidates, information clock and support | Retrospective, not a renewed confirmation |
| Spatially smoothed orientation field | Required nearby benchmark; no new execution in V6 | Capacity and tuning budget comparable, fitted on permitted partitions | Retrospective, with selection disclosed |
| Zhuang–Maita-style marked ETAS | Literature predecessor; not implemented here | Align target and symmetries; distinguish full intensity from conditional mark density | Method comparison may be retrospective; no rescue of the frozen rule |
| Circular calibration, coverage and residual structure | Desired diagnostic audit; no new results supplied | Respect axial symmetry and dependence; define a circular reference appropriately | Describe failure modes; learned policies require new evaluation |

One should not compare a space–time intensity score with an orientation-density score as though they estimated the same object. An occurrence model may supply parent candidates or an adapted conditional mark component, but that adaptation and its budget must be explicit. A physically informed stress comparator likewise requires available inputs and a defined forward model; naming Coulomb stress is not an executed baseline.

No row marked pending is a placeholder for a missing result. It records an unperformed scientific obligation and prevents a reader from mistaking a literature citation for a benchmark. The final closure of the original terminal line remains in force while such audit questions are documented.

## 6. Source validity and comparability across stages

The historical dynamic selector admitted numeric codes `0` and `1` after converting codes to strings and excluding only textual `b` and `bl`. That semantic gap is distinct from the remaining uncertainty about the source's version-specific numeric dictionary. Of 61,555 selected historical records, 3,513 carry numeric code 1; 3,506 of those are observable, including 771 in historical test partitions. The present evidence does not justify relabeling all code-1 records as blasts or certifying them all as earthquakes.

Independently, seventeen historical selections coded 0 have official `qb` counterparts under the candidate network/time correspondence. Sixteen are observable, including one Parkfield test record. Resolving the numeric 0/1 dictionary alone cannot resolve those discrepancies. Event identity, source revisions and label disposition must also be checked. The exact partition table, individual example, control-character exception and audit receipt are retained in V5 Section 4.5 in the appendix.

No angular access, exclusion, relabeling or scientific refit is performed by this revision. The influence of these membership discrepancies on fitted metrics is therefore unknown. Historical values remain results for the records actually analyzed. They are not silently deleted, corrected or reinterpreted as certified exclusively-earthquake estimates.

The terminal source was acquired separately with an `earthquake` filter and FPFIT mechanisms. It does not inherit the historical numeric-code defect by association. Nevertheless, a different mechanism product may change coverage, precision and error structure; temporal replication is not identical measurement under every detail. The source producer's documentation and the California stress-model study are relevant to this comparability question, not evidence that the historical audit is resolved (Cheng et al., dataset version 2; Cheng et al., 2026).

## 7. Local benefits, adverse results and adaptation

The historical program contains favorable observations that should remain scientifically visible. Johannesburg had a 3.05% static RMSE gain with raw \(p=0.035\) and Holm-adjusted \(p=0.14\). Ridgecrest and CalMex improved RMSE by 1.039% and 1.135%; CalMex passed the NLL and Holm conditions while failing other parts of its contract. Historical Parkfield improved log-score by 0.003443123 nats per scored unit and RMSE by 0.836872%, subject to its membership reservation and weak graph-sign stability. Bay Area worsened at that historical stage. All original tables and uncertainty qualifications remain below.

These observations answer “where did the fitted model improve in the analyzed data?” They do not by themselves answer whether the favorable jurisdiction can be recognized before its outcome, or whether the improvement persists on new data. Conditional predictive ability supplies an established framework for the second distinction (Giacomini and White, 2006). A positive local observation need not wait for a positive global mean to be recorded; a policy selected by examining that observation must still be evaluated on an appropriate new information set.

The whole sequence was adaptive. The Indio pilot overlapped the geographic/catalog domain of the later complete-catalog gate, and its exact event-ID/partition overlap remains reserved. The historical two-cohort hierarchical analysis reused opened outcomes for design only. Its probabilities, priors and calculations remain in full in the appendix; they are not new confirmation. Internal protocol hashes identify frozen instructions but do not independently prove absence of prior exposure, public preregistration or valid source semantics. These are distinct claims with distinct evidence requirements.

The terminal stop rule prevents moving from a failed prespecified model to a new same-data confirmation by adding flexibility. A newly described subgroup, revised likelihood or stronger benchmark may be an informative retrospective audit. It cannot change the historical permission boundary or replace the negative terminal adjudication with a freshly claimed prospective success.

## 8. What has been corrected in V6

This revision makes five substantive changes without changing results. First, it leads with the terminal temporal contrast rather than requiring the reader to traverse the whole development history. Second, it states the conditional axial-mark estimand and separates children from candidate edges. Third, it adds the closest focal-mechanism/ETAS predecessor and contemporary evaluation literature, reducing generic novelty claims. Fourth, it separates material-effect exclusion from nonsignificance, bilateral equivalence and physical nonhelicity. Fifth, it names the likelihood, dependence, comparator and source-audit obligations still needed for an independently inspectable empirical submission.

The archival appendix is deliberately lossless. Its V5 title, abstract and wording remain part of the historical record; terms such as “strong rivals” and historical “edge” labels are not expanded into claims that the new comparator matrix has been executed. Where a broad historical phrase could imply more, Sections 2–7 give the current narrower operational interpretation. Preserving text is not the same as endorsing every earlier framing unchanged.

## 9. Remaining publication obligations and stopping boundaries

| Obligation | Concrete completion criterion | Status after this revision |
|---|---|---|
| Exact axial likelihood | Recover executed formula and fitting code; document reference measure, normalizer, support, concentration/dispersion, parent aggregation and numerical policy | Contract clarified; implementation-level verification remains open |
| Information-time audit | Pair each scored prediction with allowed inputs and emission/availability times; distinguish child metadata conditioning from prior occurrence prediction | Intended information set explicit; complete record-level audit not performed here |
| Loss dependence and bounds | Recover paired per-child losses, bootstrap parameters and rationale; state fitting conditioning and dependence sensitivity | Inferential interpretation clarified; coverage not newly certified |
| Joint-rule power | Evaluate the actual conjunction under justified assumptions after eligibility attrition, or qualify historical approximations as such | Qualification implemented; no new power calculation claimed |
| Nearby comparators | Implement and document any chosen rival with equal target, available information and tuning budget | Matrix supplied; no performance invented and no frozen gate reopened |
| Historical event membership | Obtain version-specific dictionary and resolve matched `qb` discrepancies as distinct tasks | Reservation preserved; no source semantics repaired by wording |
| Reproducibility package | Connect exact terminal inputs, model implementation, predictions, paired losses and receipts to the reported tables | V5 reproducibility claims preserved; this editorial pass is not a fresh full replay |

The task-relative scientific conclusion remains meaningful while these limitations are disclosed: within the executed terminal comparison, the additional signed transport term failed its declared predictive requirements in both jurisdictions. The stronger claim that the reported bootstrap endpoints have a specified repeated-sampling coverage needs the corresponding audit. No recommendation in this manuscript authorizes another confirmatory opening of the already scored test or a silent change to the terminal decision.

## 10. Conclusions

The tested mechanism adds signed axial rotation along a frozen representation of a fault network to a nonhelical dynamic orientation predictor. Its observable consequence is a paired change in conditional predictive score, not direct measurement of a transported physical field. The terminal Bay Area effect is small and positive; the terminal Parkfield log-score effect is small and negative. Both fail the material contract, while earlier favorable local observations retain their exact scopes and source qualifications.

The contribution is the particular negative contrast, its preserved sequence of decisions and the clear separation between numerical replay, cohort validity, conditional predictive evidence and physical interpretation. ETAS with orientation marks, proper scores and prospective evaluation are prior art. The remaining scientific frontier is to make the implemented likelihood and uncertainty contract completely inspectable and to delimit the specific signed-network mechanism against close comparators without reclassifying an opened test as new evidence. The declared terminal line remains closed; lessons for genuinely different observables or estimands require their own evidence and information clocks.

## References added in V6

The original references are retained verbatim in the archival appendix. The following entries expand the comparative context; a citation does not imply that its software or experiments were reproduced here.

Brehmer, J. R., Kraus, K., Gneiting, T., Herrmann, M., & Marzocchi, W. (2025). Enhancing the statistical evaluation of earthquake forecasts—An application to Italy. *Seismological Research Letters*, 96(3), 1966–1988. https://doi.org/10.1785/0220240209. The consulted author version is arXiv:2405.10712v2, revised in 2026: https://arxiv.org/html/2405.10712v2.

Cawley, G. C., & Talbot, N. L. C. (2010). On over-fitting in model selection and subsequent selection bias in performance evaluation. *Journal of Machine Learning Research*, 11, 2079–2107. https://www.jmlr.org/papers/v11/cawley10a.html.

Giacomini, R., & White, H. (2006). Tests of conditional predictive ability. *Econometrica*, 74(6), 1545–1578. https://doi.org/10.1111/j.1468-0262.2006.00718.x.

Gneiting, T., & Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *Journal of the American Statistical Association*, 102(477), 359–378. https://doi.org/10.1198/016214506000001437.

Lakens, D. (2017). Equivalence tests: A practical primer for t tests, correlations, and meta-analyses. *Social Psychological and Personality Science*, 8(4), 355–362. https://doi.org/10.1177/1948550617697177. Used here for the logical distinction between nonsignificance and equivalence, not to import independent-sample t-test assumptions into a dependent earthquake graph.

Roberts, D. R., et al. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography*. https://doi.org/10.1111/ecog.02881.

Schorlemmer, D., et al. (2018). The Collaboratory for the Study of Earthquake Predictability: Achievements and priorities. *Seismological Research Letters*, 89(4), 1305–1313. https://doi.org/10.1785/0220180053.

Zhuang, J., & Maita, E. (2020). An ETAS model incorporated with focal mechanisms. *2020 SCEC Annual Meeting*, poster 101, contribution 10446. https://central.scec.org/node/45670. The linked one-page primary poster names both authors; the institutional catalog's citation names Zhuang. This is a conference poster, not a verified peer-reviewed prospective-validation article. No DOI was identified in the source review.

## Archival appendix: complete V5 manuscript, unchanged

The following material is the exact V5 source text, not a reconstruction from its tables or a shortened history. Its internal section numbers, cross-references, result identifiers and bibliography remain unchanged. Those internal numbers refer to V5. Sections 1–10 above supply the current V6 ordering, estimand, interpretation and unresolved-obligation matrix. The accompanying retention map records byte identity and hashes of every preserved section.

<!-- BEGIN_EXACT_V5_SOURCE -->
# Fail-Closed Predictive Tests of Static and Dynamic Helical Structure in California Earthquake Catalogs

**Manuscript status:** full working draft V5, integral correction dated 2026-10-13; the precommitted terminal post-2021 full-network gate has now been executed. Engineering, gate-specific testing, blind-analysis-lock and exploratory-design stages are separated explicitly. Historical v0.8.2 claims carry a material event-membership reservation; their numeric results are preserved. External seismological and statistical review remains required.

## Abstract

Geometric resemblance can make a helical explanation difficult to falsify: when a global helix fails, locality, segmentation or dynamics can be added after inspection. We report a sequence of predictive tests designed to prevent that rescue pattern. Gate-specific locks preserved predecessors and declared model families, materiality rules and nonhelical rivals before directional scoring. The sequence was adaptive; the global Indio catalog also overlaps the domain of an earlier engineering sample, so complete independence from pilot exposure is not certified. An engineering pilot was followed by a global static gate, a static local/piecewise gate and a dynamic signed-orientation gate using focal mechanisms and an external fault network. No completed gate met its conjunctive decision rule. Global static gains were small and nonreplicating; local/piecewise gains remained below materiality and unstable; and the dynamic extension worsened Bay Area predictions while improving Parkfield by less than 1% with a strongly adverse BIC penalty. A subsequent two-cohort hierarchical analysis was performed only for design and supports a no-reuse decision for the opened tests. The result is not evidence for universal nonhelicity. It is a sequence of negative results for declared model classes, with source-specific qualifications. A retrospective index-only audit now identifies unresolved numeric event codes and seventeen historical selections with official qb counterparts; historical dynamic metrics therefore remain conditional on the actual selected cohort. A terminal rule allowed at most one new post-2021 full-network test. A blind 2022--2026 census and external-fault preflight retained exactly two powered cohorts without accessing directional angles. A complete endpoint-junction fault-network policy and parent graph were then frozen before directional scoring. The terminal Bay Area/Parkfield test again failed: Bay Area gained only 0.000227 nats per child and 0.049% in axial RMSE, while Parkfield lost 0.000611 nats per child and improved RMSE by only 0.014%; both complexity penalties favored the nonhelical rival. The precommitted stopping rule therefore closes the declared earthquake-catalog helicoidal line with model- and source-conditional upper bounds on predictive log-score gain, not bounds on physical helicity. The study also demonstrates content-addressed protocols, exact-source receipts, fail-closed abstention and append-only preservation of adverse evidence.

## 1. Introduction

Helical descriptions are attractive in geophysics because fault systems are curved, rupture migrates, focal mechanisms rotate and three-dimensional projections can conceal structure. The same flexibility makes the hypothesis vulnerable to post hoc rescue. If a global helix fails, one can introduce local pitch. If a static fit fails, one can introduce time. If same-segment transport fails, one can add cross-segment paths. Without predeclared rivals, materiality thresholds and stop rules, the hypothesis can become effectively unfalsifiable.

This study was designed to prevent that outcome. Each gate had to preserve its predecessor, freeze its own decision rule before the designated scoring step, and distinguish scientific results from source or infrastructure failures. Freeze receipts alone do not certify prior nonexposure or correct event-type semantics; those require separate audits. The program therefore treated a helical model not as a visual template but as a candidate predictive mechanism that must earn authority over simpler alternatives.

The sequence addressed four increasingly demanding questions:

1. Does a global helical tube improve prediction of relocated hypocenter geometry?
2. Does the result replicate across complete catalogs and stronger nulls?
3. Can a local or piecewise residual helix beat flexible nonhelical centerlines?
4. Does signed focal-mechanism orientation propagate along directed triggering paths beyond ETAS/Hawkes and static orientation-field rivals?

The answer was negative at every completed level. This paper reports that sequence because the cumulative structure is more informative than any individual nonsignificant test. It also demonstrates a general approach to negative-result science: define the jurisdiction, make the hypothesis capable of losing, preserve adverse evidence, and produce upper bounds rather than silently moving the target.

## 2. Scientific scope and ontological units

### 2.1 Static catalogs are not particle trajectories

A hypocenter catalog is a marked point process

\[
\mathcal E=
\{(t_i,x_i,m_i,\Sigma_i,\ldots)\}_{i=1}^{N},
\]

not the continuous path \(\gamma(t)\) of one material object. A static helical fit can therefore describe the support of events, but it does not by itself establish transport of matter, energy or stress.

The static model classes were interpreted narrowly as predictive descriptions of spatial support. The dynamic gate changed the unit of analysis to directed parent–child transitions between marked events. Its helical quantity was signed transport of focal-mechanism orientation along externally defined fault coordinates.

### 2.2 Physical helicity was not the primary estimand

Fluid or magnetic helicity is a field-level pseudoscalar or invariant. Earthquake catalogs do not directly observe an analogous field. The program therefore used the phrase *helical structure* for geometric support models and *signed orientation transport* for the dynamic mark model. Replicated signed transport, directed propagation, out-of-sample gain and stability were necessary program-level criteria for further investigation. Even their joint satisfaction would not identify physical helicity without an appropriate measured field, physical observation model and identifiability argument. No completed gate met the declared predictive criteria.

## 3. Governance and fail-closed design

Every gate separated:

\[
\text{source acquisition}
\rightarrow
\text{parsing}
\rightarrow
\text{eligibility}
\rightarrow
\text{model selection}
\rightarrow
\text{sealed test}
\rightarrow
\text{adjudication}.
\]

Blocked acquisition was not labeled a null result. Rank deficiency or inadequate mechanism coverage produced nonidentifiability, not evidence of absence. A successor run never rewrote the predecessor. Data hashes, protocol identities, graph states and event-chain heads were stored in append-only KwanBlocks artifacts.

The recurring split was chronological:

\[
50\%\ \text{train},
\qquad
25\%\ \text{calibration},
\qquad
25\%\ \text{sealed test}.
\]

Geometry and parent-graph parameters were fit on train; model choice used calibration; the designated held-out test was scored after its lock. Independent numerical replays are repeated computation on the same outcomes, not new independent test openings. Prior pilot exposure and later design-only reuse are disclosed below. Model complexity, null distributions and uncertainty propagation were part of the decision rule rather than optional diagnostics.

### 3.1 Stage classification and evidential status

The term **pre-specified** means that a protocol and its content hash were frozen before the corresponding test partition or directional field was opened. These internal locks are not represented as equivalent to a public registry. The stages are:

| Gate | Data status | Evidential role | Test reuse permitted? |
|---|---|---|---|
| Indio 229-event run | real sample, protocol stabilized during engineering | software/method qualification | no confirmatory claim |
| Four-catalog global gate | exact complete catalogs, frozen protocol; prior Indio pilot exposure | gate-specific global test; full four-catalog independence not certified | no |
| Cahuilla/Ridgecrest/CalMex | previously untouched catalogs, frozen protocol | confirmatory within local/piecewise class | no |
| Bay Area/Parkfield dynamic | blind angular selection; event-type semantics and actual membership reserved | historical conditional result within same-segment graph | no |
| v0.9-A hierarchical analysis | already opened dynamic tests; inherits membership reservation | exploratory design and GO/NO-GO | engineering/prior design only |
| Terminal post-2021 full-network gate | separately acquired USGS/NCEDC events; same geographic regions | temporal replication of the frozen terminal estimand | no |

The program does not claim a single familywise error rate spanning all adaptive gates. Each gate has a declared jurisdiction, and the terminal stop rule limits further adaptation.

### 3.2 Units, blocking and source roles

Nominal rows are not treated as independent replicates. The principal units are complete earthquake sequences for static replication and fault-network event transitions for the dynamic gate. Temporal blocks, spatial blocks, mechanism perturbations and parent-graph resampling are used according to the dependence structure. The external fault database defines candidate geometry; it is not evidence of parentage. The focal-mechanism catalog supplies source orientation and uncertainty; it is not itself a stress-transport measurement.

| Source | Role | Prohibited interpretation |
|---|---|---|
| rapid-response HypoDD/GrowClust catalogs | relocated event geometry | continuous material trajectory |
| focal-mechanism catalog | marked source orientation | directly transported director field |
| GEM/UCERF3-derived traces | external assignment and local tangent | exact three-dimensional causative fault |
| ETAS/Hawkes weights | probabilistic parent candidates | proven causal genealogy |

## 4. Gate sequence

### 4.1 Engineering pilot on a real observational sample

The first empirical gate used a contiguous 229-event sample from the 2026 Indio rapid-response HypoDD catalog. It compared a straight tube, linear ribbon, quadratic curve and helical tube. The helical model reduced test RMSE by 1.81%, below the frozen 10% threshold; the cyclic-shift null gave \(p=0.23\), and chirality stability was 0.625 against a required 0.80. The outcome was `NONHELICAL_RIVAL_SUFFICIENT`.

This pilot was not confirmatory because the protocol had been stabilized through internal engineering. Its purpose was to demonstrate that the software could process real data and that the helical model could lose.

### 4.2 Global static gate and prior-exposure qualification

Four complete rapid-response HypoDD catalogs were acquired exactly: Indio, Brawley, Johannesburg and Coso Junction. The locked model used a train-only quadratic centerline, arc-length parameterization, a Bishop frame and one stationary residual frequency. The rivals were straight, linear and quadratic nonhelical supports.

The earlier pilot used 229 events from the Indio catalog. The complete-catalog gate therefore cannot be described as four wholly new independent sequences without an event-ID and partition crosswalk excluding pilot-to-test overlap. That exact overlap count has not been established in the present continuity audit; the Indio exposure reservation is retained rather than presumed absent. The aggregate below remains the historical four-catalog computation.

No sequence passed the 10% held-out RMSE threshold. The weighted aggregate gain was only 0.225%. Johannesburg displayed the strongest local indication, with raw \(p=0.035\), but its Holm-adjusted value was 0.14 and its RMSE gain was 3.05%. The correct aggregate outcome was `NONHELICAL_RIVALS_GENERALIZE`.

### 4.3 Static local/piecewise gate

A more flexible gate tested whether the global negative result concealed local helicity. Three previously untouched cohorts were used: Cahuilla, Ridgecrest QTM and CalMex. Flexible nonhelical centerlines (`POLY0`, `POLY1`, `POLY2`, `SPLINE4`, `SPLINE6`) competed against residual sinusoidal models with one, two or three piecewise regions.

A positive cohort required simultaneously:

\[
\Delta\mathrm{RMSE}\geq5\%,
\]

\[
\Delta\overline{\mathrm{NLL}}\geq0.02,
\]

\[
\Delta\mathrm{BIC}_{H-B}\leq-10,
\]

Holm-adjusted \(p\leq0.05\), positive moving-block-bootstrap lower bound and at least 80% perturbational pass fraction.

No cohort passed. Cahuilla worsened by 0.327%. Ridgecrest improved by 1.039% but had \(\Delta\mathrm{BIC}=+56.28\). CalMex improved by 1.135% and passed the NLL and Holm gates, but failed materiality, strong BIC, bootstrap and uncertainty stability. The weighted aggregate gain was 1.133%, below the 5% threshold. The outcome was `NONHELICAL_BRANCHING_RIVALS_GENERALIZE`.

### 4.3.1 Cumulative effect-size summary

| Completed class | Sequence/cohort units | Best or aggregate held-out gain | Frozen minimum | Adjudication |
|---|---:|---:|---:|---|
| engineering pilot | 1 sample | RMSE +1.81% | 10% | rival sufficient |
| global static gate, Indio exposure reserved | 4 sequences | weighted RMSE +0.225% | 10% | rivals generalize |
| local/piecewise confirmation | 3 cohorts | weighted RMSE +1.133% | 5% | rivals generalize |
| conservative dynamic gate, membership reserved | 2 cohorts | log score +0.001143; RMSE +0.142% | 0.02 nats; 5% | rival sufficient |

The table is descriptive across gates; it is not a pooled meta-analysis because estimands and units differ.

### 4.4 Dynamic marked-process gate

The dynamic gate used the version-2 Statewide California focal-mechanism catalog and an immutable GEM active-fault network. Eligibility was blind to strike, dip and rake. Five candidate geographic cohorts were filtered using non-directional quality metadata and external-fault assignment. Bay Area–Hayward/Calaveras and Parkfield–central San Andreas passed the implemented frozen eligibility rule. Retrospective audit shows that passing that implementation did not certify exclusively-earthquake membership (Section 4.5).

After the selection receipt was sealed, strike, dip and rake were opened only for the selected rows. Of 61,555 selected mechanisms, 60,577 were axially observable after projecting the principal compression axis into the fault cross-section. The sealed test contained 9,320 Bay Area and 5,825 Parkfield events.

The orientation mark was represented by a normalized double-couple tensor, eliminating arbitrary nodal-plane choice. Axial phase used \(e^{2i\psi}\), removing eigenvector-sign and \(\pi\)-period ambiguities. Parent candidates were generated through a train-fit ETAS/Hawkes distribution restricted conservatively to the same externally assigned fault segment. The helical model could not alter that parent graph.

The primary comparison was between a nonhelical temporal/static/network rival and an extension with signed twist per network kilometer. A positive cohort required all of:

- at least 0.02 nats per test edge in log-score gain;
- at least 5% relative axial-RMSE improvement;
- \(\Delta\mathrm{BIC}_{H-B}\leq-10\);
- Holm-adjusted null \(p\leq0.05\);
- positive moving-block-bootstrap lower bound;
- at least 0.80 stability under mechanism, fault-assignment and parent-graph perturbations;
- at least 0.80 sign consistency under propagation reversal.

### 4.5 Retrospective membership audit and interpretation boundary

A retrospective membership audit recovered all 61,555 historical selected indices from the archived v0.8.2 evidence and matched their event identifiers, network codes and event-type codes against an independently extracted blind view of the same SHA-256-pinned source catalog. Of the selected records, 3,513 carry the numeric event-type code 1; 3,506 remain in the previously published observable subset, including 771 in the historical test partitions. We do not identify this numeric code with blasts because its version-specific encoding has not been certified. An intersection with previously preserved official-catalog discrepancy records identifies 17 selected records coded 0 with qb counterparts under the candidate network correspondence and a maximum one-second origin-time difference. Sixteen of these are observable: two in Bay Area training, thirteen in Bay Area calibration, and one in Parkfield testing. One additional observable Bay Area training record has an unsupported control-character event type in its catalog counterpart. These findings establish a material cohort-membership reservation; they do not quantify its influence on fitted metrics. The reported v0.8.2 metrics remain historical results conditional on the records actually analyzed, while the exclusively-earthquake interpretation of that cohort is not currently certified. This audit decoded no angular values, reran no scientific models, and does not transfer its source-specific reservation to the separately sourced post-2021 terminal experiment.

The historical selector converted numeric event codes to strings and excluded only textual labels `b` and `bl`. Numeric codes `0` and `1` were both admitted. This was a semantic validation gap, independently of the unresolved version-specific numeric dictionary. The selected membership counts are:

| Observable partition | Bay Area numeric code 1 | Parkfield numeric code 1 |
|---|---:|---:|
| Training | 1,683 / 18,640 | 40 / 11,648 |
| Calibration | 975 / 9,320 | 37 / 5,824 |
| Test | 710 / 9,320 | 61 / 5,825 |

The test exception in Parkfield is source index 1,378,396, event 72270365, with a same-time `qb` counterpart in the pinned NCEDC 2014 catalog. All seventeen `qb` counterparts carry source code 0. Consequently resolving the numeric 0/1 dictionary alone would not resolve these discrepancies; source-label disposition and dictionary validation are distinct obligations. No exclusion, relabeling, directional access or scientific refit was performed in this audit. Any later sensitivity analysis must be explicitly retrospective and cannot repair the original confirmation status by reusing the opened test.

The audit receipt is `hcontinuitymembership:ab63c91ad2697577daa98a8863d7f68af0f24a095c9407ccdea7f69395171ead`; its machine-readable sources and row-level nonangular crosswalk accompany this revision.

## 5. Dynamic results, conditional on historical membership

| Cohort | Test edges | Log-score gain/edge | Relative RMSE gain | \(\Delta\mathrm{BIC}_{H-B}\) | Positive? |
|---|---:|---:|---:|---:|---|
| Bay Area–Hayward/Calaveras | 9,320 | −0.000294641 | −0.291649% | +417.139 | No |
| Parkfield–central SAF | 5,825 | +0.003443123 | +0.836872% | +123.285 | No |

The weighted aggregate was

\[
\Delta\overline{\log p}
=0.0011429605
<0.02,
\]

and

\[
\Delta\mathrm{RMSE}_{\mathrm{weighted}}
=0.142397\%
<5\%.
\]

### 5.1 Bay Area

The extension worsened both primary metrics. The large positive BIC difference strongly favored the nonhelical rival. These historical scores provide no positive support for the extension within the analyzed cohort and model class. Their interpretation as an exclusively-earthquake result remains reserved.

### 5.2 Parkfield

Parkfield retained a small signed association. It was nevertheless far below materiality: the log-score gain reached 17.2% of the frozen threshold and the RMSE gain 16.7%. The BIC penalty was strongly adverse, and parent-graph sign stability was 0.40625. None of the 64 computational mechanism-uncertainty perturbations passed the full gate. These are propagation draws from the declared uncertainty model, not 64 independent observational replications. The result is a weak, nonrobust residual association, not a near detection.

### 5.3 Aggregate adjudication

Zero of two primary cohorts passed, while two were required. The outcome was

```text
NONHELICAL_DYNAMIC_RIVAL_SUFFICIENT_WITHIN_CONSERVATIVE_PARENT_GRAPH
```

The qualifier matters. The executed graph was restricted to parent candidates on the same external fault segment. A complete cross-segment graph was not adjudicated because its topology and path semantics had not been fully frozen before the v0.8.2 test was opened.

## 6. v0.9-A upper-bound and GO/NO-GO analysis

After v0.8.2, the opened test data were used only for experimental design. Every quantity in this section inherits the historical membership reservation; it is not re-estimated or promoted by the present audit. Moving-block-bootstrap standard errors were combined in a two-cohort normal random-effects model with explicit prior sensitivity.

For log-score gain per edge, the default-prior posterior median population mean was

\[
0.00148,
\]

with a 95% interval

\[
[-0.01355,0.01575].
\]

The probability that the population mean exceeded the material threshold of 0.02 was

\[
0.01152.
\]

For relative RMSE improvement, the posterior median was

\[
0.00264,
\]

with 95% interval

\[
[-0.03573,0.03948],
\]

and probability of exceeding 0.05 equal to

\[
0.01159.
\]

Doubling both prior scales raised these probabilities to at most 0.0490 and 0.0495. These are design-model probabilities, not a new confirmatory test, and only two cohorts are available. They nevertheless show that another experiment is not justified by an expectation of a large average effect.

### 6.1 Power was not the main bottleneck

Normal approximations based on moving-block-bootstrap standard errors indicate that the existing test sizes were already capable of detecting effects below the frozen material thresholds with approximately 80% power. Conditional on the variance, dependence and membership assumptions of that design calculation, sample size alone is not its indicated bottleneck. This approximation does not resolve source-label uncertainty or certify power after a corrected selection. The substantive problems are small observed effects, complexity penalties and graph instability.

### 6.2 Cross-segment support audit

Bay Area had 55 assigned segments but an inverse-Herfindahl effective count of 9.84. Parkfield had 11 segments and an effective count of 3.46. The conservative same-segment graph already provided at least one candidate parent for 89.22% of Bay Area and 96.06% of Parkfield observable events. The maximum support that a full graph could add before further temporal/path restrictions was therefore 10.78% and 3.94%, respectively.

The full graph was not confirmatorily identifiable on the opened test because six choices remained scientifically consequential: adjacency, segment orientation, junction transfer cost, multipath integration, projected crossings and parent-weight refit policy. Freezing those choices after seeing the test and then reporting the same test as confirmation would be post-selection inference.

## 7. Decision and terminal rule

The v0.9-A decision is:

\[
\boxed{\texttt{NO\_GO\_FOR\_CONFIRMATORY\_REUSE}}
\]

and

\[
\boxed{\texttt{CONDITIONAL\_GO\_FOR\_ONE\_NEW\_POST\text{-}2021\_GATE}}.
\]

The historical terminal authorization allowed one final gate only on new post-2021 mechanisms. The blind feasibility census reported below passed the raw-count screen; directional access remained prohibited until external-fault assignment and parent-support gates passed. That authorization also required the full external graph frozen before directional access, at least two blind-selected cohorts, at least 80% power at the existing material thresholds, and stability of fault assignment, path ambiguity and parent graph of at least 0.80. The opened 1981–2021 Bay Area and Parkfield outcomes could be used for engineering and priors, never reused as confirmatory observations. New events in those same geographic regions provide temporal replication, not replication in new geography.

The stop rule is terminal: if one new-data full-network gate again favors nonhelical rivals, the seismic helical program closes with predictive-gain upper bounds for the signed-transport model.

### 7.1 Blind post-2021 feasibility census

The conditional new-data gate was subjected to a blind census before any post-2021 focal-angle product payload was opened. ComCat event metadata were queried for the presence of `focal-mechanism` or `moment-tensor` products between 1 January 2022 and 11 October 2026. The census retained event identifier, time, hypocenter, magnitude, review status and product-presence flags, but did not retrieve strike, dip, rake, nodal planes, principal axes or moment-tensor components.

Four primary regions exceeded the predeclared minimum of 800 events with a directional product:

| Blind region | Unique events | Chronological train | Calibration | Sealed test | Expected test children at 80% parent retention |
|---|---:|---:|---:|---:|---:|
| Bay Area | 6,513 | 3,256 | 1,628 | 1,629 | 1,303 |
| Parkfield--central SAF | 2,302 | 1,151 | 575 | 576 | 460 |
| Mendocino Triple Junction | 1,334 | 667 | 333 | 334 | 267 |
| Northern Walker Lane | 1,012 | 506 | 253 | 253 | 202 |

The control region in southern California contained 17,764 events. The census therefore returns

\[
\boxed{\texttt{BLIND\_CENSUS\_PASS}}.
\]

This is a feasibility result, not evidence for signed transport. The next admissible operation at that historical stage was external-fault assignment and parent-support auditing using only nondirectional fields. At least two cohorts must retain 200 or more sealed-test child events after exact fault assignment and the frozen parent-graph rules. Failure at that stage closes the seismic line before angle access. If that gate passes, cohort identities, graph rules and test partitions must be sealed before directional products are opened.

The census also changes the interpretation of the terminal rule. At the census stage a sufficiently large post-2021 pool existed. Its scientific usability remained contingent on fault-assignment stability, graph identifiability, product quality and power after attrition; Sections 7.2–7.3 report the subsequent preflight and execution.

### 7.2 External-fault assignment and parental-support preflight

The blind census was then intersected with the immutable GEM active-fault geometry. Event-cloud clustering was forbidden. Assignment was accepted only when the nearest mapped segment lay within 10 km and the second-to-first distance ratio was at least 1.5; ambiguous events were excluded. Conservative parent support required a previous event on the same assigned segment within 30 days and 20 km along the segment.

| Region | Blind events | Assigned | Coverage | Sealed test | Test children with parent | Parent-support fraction | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| Bay Area | 6,513 | 5,346 | 0.821 | 1,337 | 1,195 | 0.894 | pass |
| Parkfield--central SAF | 2,302 | 1,903 | 0.827 | 476 | 422 | 0.887 | pass |
| Mendocino Triple Junction | 1,334 | 932 | 0.699 | 233 | 162 | 0.695 | fail |
| Northern Walker Lane | 1,012 | 658 | 0.650 | 165 | 103 | 0.624 | fail |

The preflight therefore returns

\[
\boxed{\texttt{FAULT\_ASSIGNMENT\_PREFLIGHT\_PASS}}
\]

for exactly two new-data cohorts. Directional fields remained sealed throughout. At that stage Bay Area and Parkfield were authorized for selected-only directional-product materialization after the full cross-segment topology, orientation, junction and multipath rules are content-addressed. Mendocino and Northern Walker Lane are excluded before angle access. This selection is based on new post-2021 events and does not reuse the 1981--2021 directional outcomes as confirmatory evidence.

### 7.3 Terminal post-2021 full-network gate

After blind cohort selection, the complete external graph was frozen before scientific directional scoring. The graph contained 625 mapped fault polylines, 1,250 endpoint nodes, 837 graph edges and 212 endpoint-to-endpoint junctions under a fixed 2 km junction radius. Interior projected crossings without endpoint proximity were not treated as connections. Parent candidates were restricted to 30 days, 20 km network distance and at most 20 parents, with a fixed ETAS-like weighting law. Event-cloud clustering remained forbidden.

The full graph increased sealed-test parent support to 90.65% in Bay Area and 89.29% in Parkfield. Route orientation for 69,104 parent-child candidate edges was materialized deterministically before mechanism scoring. This terminal cohort was acquired separately from USGS records filtered as `earthquake`; it did not use the unresolved numeric `ev_bl` selection. Official NCEDC monthly FPFIT mechanisms then supplied usable focal mechanisms for 99.10% and 98.74% of assigned events, respectively. The FPFIT angular convention was treated explicitly: the stored first angle is dip direction, converted to strike by subtracting 90 degrees modulo 360.

The terminal model compared a nonhelical dynamic circular-regression rival with an extension adding signed axial rotation per network kilometer. Static segment orientation was estimated on TRAIN only. A cohort required simultaneously at least 0.02 nats per child in log-score gain, 5% relative axial-RMSE improvement, delta BIC no greater than -10 and a positive moving-block-bootstrap lower bound.

| New-data cohort | Test children | Log-score gain/child | Relative RMSE gain | delta BIC H-B | Bootstrap 95% lower | Positive? |
|---|---:|---:|---:|---:|---:|---|
| Bay Area | 1,196 | +0.000227 | +0.0491% | +6.543 | -0.000645 | No |
| Parkfield--central SAF | 421 | -0.000611 | +0.0136% | +6.558 | -0.001440 | No |

Both cohorts fail before expensive rescue diagnostics are needed. Bay Area's 97.5% moving-block-bootstrap upper bound for log-score gain is 0.001187 nats per child, only 5.9% of the material threshold. Parkfield's upper bound is 0.0000559. The independently rerun result JSON and metrics CSV are byte-identical; this verifies numerical replay, not independent empirical replication. These bootstrap endpoints concern held-out predictive log-score differences under the declared model, graph, source and resampling assumptions. They do not bound geometric pitch, magnetic/fluid helicity or all possible signed physical transport.

The terminal outcome is therefore

```text
SEISMIC_HELICAL_PROGRAM_CLOSED_WITH_UPPER_BOUNDS
```

This closes the declared earthquake-catalog research line under its precommitted stopping rule. It does not establish universal nonhelicity and does not adjudicate field-level magnetic or fluid helicity.

## 8. Interpretation

The cumulative evidence argues against the tested helical classes, not against every possible physical mechanism involving chirality. Three distinctions are essential.

First,

\[
\text{curved support}
\neq
\text{helical transport}.
\]

Second,

\[
\text{periodic residual}
\neq
\text{predictively material effect}.
\]

Third,

\[
\text{signed association}
\neq
\text{physical helicity}.
\]

The sequence is informative because locality, piecewise structure and dynamic orientation were operationalized as explicit successors and did not meet their own gates. Its evidential strength remains heterogeneous: the pilot was engineering, Indio prior exposure is reserved, old dynamic membership is reserved, and the separately sourced terminal gate is a temporal test of a declared estimand.

## 9. Limitations

The former same-segment graph limitation was addressed by the terminal post-2021 full-network gate, but the external fault network remains a two-dimensional mapped representation with endpoint-defined junctions rather than a complete three-dimensional rupture surface. The focal-mechanism catalog is large but heterogeneous in time, network coverage and solution quality. External fault assignment is two-dimensional and does not fully represent subsurface topology. Double-couple tensors summarize source orientation but not the complete stress field. Parent graphs remain probabilistic. BIC uses a declared effective parameter count and is not a substitute for full marginal likelihood. The two-cohort hierarchical design model is prior-sensitive and should be interpreted only as a GO/NO-GO tool.

The program also involved multiple sequential gates. Although protocols were frozen before their designated scoring steps, the broader scientific program learned from predecessors, and a lock alone does not establish absence of prior exposure. Claims are therefore gate-specific rather than equivalent to one monolithic preregistered study.

### 9.1 Sequential adaptation and program-level multiplicity

The program learned from earlier failures. Gate-specific locks coexist with the disclosed Indio exposure and old dynamic-membership reservations. The sequence as a whole is adaptive. We therefore do not attach a single global type-I error rate to the entire research program. Scientific weight comes from replicated out-of-sample effect sizes, strong rivals, null preservation, adverse BIC penalties, perturbational instability and a terminal stopping decision—not from accumulating nominally independent p-values.

### 9.2 Effective complexity and BIC

BIC was one conjunctive diagnostic. Frequency search, spline selection, segmentation and parent-graph construction can make the effective parameter count exceed the coefficient count. The conclusions do not rely on BIC alone: the helical models also failed material predictive gains, bootstrap or perturbational stability. Future work should use marginal likelihood or nested predictive comparison where computationally feasible.

## 10. Reproducibility and provenance

All gates used content-addressed protocols, exact-source receipts where possible, deterministic seeds, append-only ledgers and SQLite mirrors. Adverse results, failed acquisitions and runtime boundaries were preserved. The v0.8.2 primary held-out metrics were reproduced exactly in an autonomous replay. The terminal post-2021 result and its metrics were also reproduced byte-for-byte in an independent rerun. One complete v0.8.2 null-and-stability execution was preserved; a monolithic heavy replay reproduced calibration and primary results but stalled during repeated diagnostics, which is disclosed rather than represented as a second complete reproduction.

The computational record supports replay of historical numerical claims while distinguishing full reproduction from partial replay, numerical reproducibility from valid source semantics, and source-specific reservations from unrelated terminal evidence.

## 11. Conclusions

Across global static, local/piecewise static, conservative dynamic and final post-2021 full-network tests, helical model classes did not outperform strong nonhelical rivals by the declared content-addressed material margins. The result is not universal nonhelicity. It is a sequence of negative results at declared material thresholds, with Indio prior exposure and historical dynamic membership explicitly reserved. The terminal source-specific stopping decision remains in force.

The broader contribution is methodological. Geometric hypotheses should be evaluated through future prediction, strong rivals, signed invariance contracts, nulls, uncertainty and append-only provenance. A hypothesis that can always be rescued by adding geometric flexibility is not yet scientific. A hypothesis that is allowed to lose can generate useful upper bounds and a principled stopping decision. Under that rule, the earthquake-catalog helicoidal program is now closed; further work must move to a different observable domain or a genuinely distinct physical estimand.

## References

Hawkes, A. G. (1971). Spectra of some self-exciting and mutually exciting point processes. *Biometrika*, 58, 83–90. https://doi.org/10.1093/biomet/58.1.83

Ogata, Y. (1988). Statistical models for earthquake occurrences and residual analysis for point processes. *Journal of the American Statistical Association*, 83, 9–27. https://doi.org/10.1080/01621459.1988.10478560

Styron, R., & Pagani, M. (2020). The GEM Global Active Faults Database. *Earthquake Spectra*, 36, 160–180. https://doi.org/10.1177/8755293020944182

Trugman, D. T., & Shearer, P. M. (2017). GrowClust: A hierarchical clustering algorithm for relative earthquake relocation. *Seismological Research Letters*, 88, 379–391. https://doi.org/10.1785/0220160188

Waldhauser, F., & Ellsworth, W. L. (2000). A double-difference earthquake location algorithm. *Bulletin of the Seismological Society of America*, 90, 1353–1368. https://doi.org/10.1785/0120000006

Statewide California focal mechanism catalog and stress model (1981–2021), version 2. Dataset. https://doi.org/10.17632/2np9vw5v7w.2


Cheng, Y., Hauksson, E., & Ben-Zion, Y. (2023). Refined earthquake focal mechanism catalog for Southern California derived with deep learning algorithms. *Journal of Geophysical Research: Solid Earth*, 128, e2022JB025975. https://doi.org/10.1029/2022JB025975

Cheng, Y., Bürgmann, R., Taira, T., Liao, Z., & Allen, R. M. (2026). Stress model of California: Fault-stress interactions across a complex plate boundary system from focal mechanisms of small earthquakes. *Journal of Geophysical Research: Solid Earth*, 131, e2025JB032164. https://doi.org/10.1029/2025JB032164

Field, E. H., et al. (2014). Uniform California Earthquake Rupture Forecast, Version 3 (UCERF3)—The time-independent model. *Bulletin of the Seismological Society of America*, 104, 1122–1180. https://doi.org/10.1785/0120130164

Hardebeck, J. L., & Shearer, P. M. (2002). A new method for determining first-motion focal mechanisms. *Bulletin of the Seismological Society of America*, 92, 2264–2276. https://doi.org/10.1785/0120010200

Hardebeck, J. L., & Shearer, P. M. (2003). Using S/P amplitude ratios to constrain the focal mechanisms of small earthquakes. *Bulletin of the Seismological Society of America*, 93, 2434–2444. https://doi.org/10.1785/0120020236

Hauksson, E., Yang, W., & Shearer, P. M. (2012). Waveform relocated earthquake catalog for Southern California (1981 to June 2011). *Bulletin of the Seismological Society of America*, 102, 2239–2244. https://doi.org/10.1785/0120120010

Waldhauser, F., & Schaff, D. P. (2008). Large-scale relocation of two decades of Northern California seismicity using cross-correlation and double-difference methods. *Journal of Geophysical Research: Solid Earth*, 113, B08311. https://doi.org/10.1029/2007JB005479
<!-- END_EXACT_V5_SOURCE -->
