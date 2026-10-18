# Systematic novelty review protocol

## Objective

Determine which BIFM components are established, directly anticipated, adjacent, or potentially residual. The review does not seek a rhetorical novelty claim; it seeks a component-level priority map and explicit claim reductions.

## Review strata

1. **Statistical learning and task-relative performance**
   - generalization, PAC, no-free-lunch, calibration, selective prediction.
2. **Observation and identifiability**
   - statistical experiments, Blackwell/Le Cam order, inverse problems, causal identifiability, latent equivalence classes.
3. **Mechanistic interpretability and causal abstraction**
   - interventions, activation patching, steering, causal abstraction, alignment maps, identification assumptions.
4. **Formal and proof-carrying evaluation**
   - theorem-prover benchmarks, verified code, machine-checkable certificates, dynamic ground truth.
5. **Semantic fidelity and specification faithfulness**
   - autoformalization drift, natural-language/formal equivalence, back-translation, counterfactual probes.
6. **Sociotechnical system, agency and authority**
   - model-versus-system evaluation, machine behaviour, identity/authorization, responsibility, TEVV.
7. **Biological analogy, autonomy and consciousness**
   - biological plausibility, embodiment, enaction, autopoiesis, consciousness indicators, anthropomorphism.
8. **Benchmark validity and observation artifacts**
   - prompt/order sensitivity, answer-label bias, judge bias, contamination, dynamic evaluation.

## Search sources

Primary-source searches are conducted over:

- arXiv;
- PMLR proceedings;
- NeurIPS proceedings;
- ACL Anthology;
- ACM Digital Library;
- official NIST publications;
- journal publishers for peer-reviewed records;
- backward and forward citation search from direct antecedents.

Secondary surveys may route discovery but do not establish technical priority when a primary source is available.

## Query grammar

Each stratum combines one term from each relevant block.

### Object block

- artificial intelligence
- machine learning
- deep learning
- language model
- neural network
- agentic system
- AI system

### Inference block

- identifiability
- indistinguishability
- observational equivalence
- equivalence class
- partial observability
- factorization
- inverse problem
- causal identification

### Claim block

- behavior to mechanism
- mechanistic claim
- biological equivalence
- consciousness
- alignment verification
- authority
- autonomy
- agency

### Certification block

- machine-checkable
- proof-carrying
- formal verification
- certificate
- counterexample
- witness
- semantic faithfulness

### Evaluation block

- benchmark
- evaluation
- intervention
- probe
- red teaming
- system testing
- sociotechnical

All literal queries, dates and result counts are to be logged in a future-only search ledger.

## Inclusion criteria

A record is included when it contributes at least one of:

- a formal definition or theorem relevant to a BIFM component;
- a directly comparable benchmark or evaluation architecture;
- an empirical intervention demonstrating or testing observational equivalence;
- a semantic-fidelity method connecting informal and formal claims;
- a system-level or authority-level evaluation framework;
- a biologically grounded criterion used to evaluate artificial systems.

## Exclusion criteria

Exclude:

- marketing pages without technical specification;
- commentary that merely repeats a primary result;
- benchmark papers with no relevance beyond generic model accuracy;
- metaphorical uses of identifiability or agency without operational content;
- duplicate versions, retaining the latest archival or peer-reviewed record while preserving version history.

## Evidence extraction schema

For each record extract:

- canonical identifier and version;
- venue and publication status;
- object class;
- observation operator;
- target property or claim;
- admissible class / assumptions;
- theorem or empirical design;
- certificate, ground truth or annotation source;
- result state;
- what the record establishes;
- what it explicitly does not establish;
- relationship to BIFM;
- claim reduction required, if any.

## Relationship labels

- `DIRECT_ANTECEDENT`: same core problem and substantially overlapping solution.
- `COMPONENT_ANTECEDENT`: establishes one component used by BIFM.
- `ADJACENT`: different primary problem but materially constrains interpretation.
- `COMPARATOR`: evaluation baseline or competing benchmark.
- `BOUNDARY_SOURCE`: supports a claim ceiling or limitation.
- `OUT_OF_SCOPE`.

## Priority rule

BIFM novelty may only be claimed for a composition or residual component when:

1. every constituent component has been mapped;
2. no direct antecedent implements the same composition;
3. the residual contribution can be stated without relying on renamed established concepts;
4. an ablation can show what the residual component adds;
5. the claim remains robust under forward citation search and adversarial query expansion.

## No-human review adaptation

Because the project does not assume external human reviewers, bibliographic screening uses:

- deterministic identifier deduplication;
- multiple heterogeneous search formulations;
- source-grounded extraction;
- model-generated candidate classifications treated as proposals;
- rule-based consistency checks;
- explicit `UNRESOLVED` status when semantic classification cannot be certified.

Model agreement is never treated as proof of priority.

## Frozen current boundaries

Already established as non-novel in isolation:

- factorization/constant-on-fibers identifiability;
- comparison of statistical experiments;
- causal abstraction and interchange interventions;
- steering-vector non-identifiability;
- machine-checkable proof benchmarks;
- natural-language/formal specification-faithfulness gaps;
- answer-order sensitivity in MCQ evaluation;
- sociotechnical evaluation of deployed AI systems.

The residual contribution under investigation is the integrated typed calculus combining claim ceilings, positive/negative certificates, observation refinement, architecture-relative intervention quotients, real open-weight collision frontiers, local uncertainty, fail-closed abstention and external authority separation.
