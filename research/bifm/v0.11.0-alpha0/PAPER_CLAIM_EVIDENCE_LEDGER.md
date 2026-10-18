# Paper claim–evidence ledger

No manuscript claim may exceed the ceiling recorded here without a new successor claim and new evidence.

| ID | Claim | Type | Evidence | Current state | Falsifier / downgrade condition | Ceiling |
|---|---|---|---|---|---|---|
| C1 | A target property is identifiable from an observation iff it is constant on observation fibers; equivalently it factors through the observation image. | Formal | Lean proof + finite exhaustive audit + Z3 cross-check | Proved within assumptions | Lean/Z3 contradiction or specification error | Abstract declared classes only |
| C2 | A collision witness refutes identifiability relative to the declared class and observation operator. | Formal | Lean proof and constructive certificates | Proved within assumptions | Invalid witness or undeclared class restriction | Does not refute richer observations |
| C3 | Observation refinement contracts the intervention invisibility set. | Formal | Lean observation-lattice proof | Proved within assumptions | Failure of deterministic refinement relation | Declared operators only |
| C4 | Enlarging a frozen observation sample contracts the invisibility set. | Formal / design | Restriction-map argument + exact implementation assertions | Proved for nested design | Samples not actually nested or operator changes | Nested finite samples only |
| C5 | Qwen top-1 behavior on a frozen ARC subset does not identify a known layer-14 MLP intervention state. | Empirical constructive | v0.8.1 exact collision, nonzero hidden displacement, held-out counterfactual separation | Supported for frozen release | Any reproduced observation flip under frozen environment or invalid intervention receipt | Qwen revision, operator and sample only |
| C6 | The amount of internally realized intervention that remains invisible varies by layer and observation sample size. | Empirical | v0.9 Qwen frontier | Supported for frozen release | Failure to reproduce frozen grid or effect receipts | Grid-, model-, layer- and sample-relative |
| C7 | Finer behavioral signatures expose interventions missed by top-1. | Empirical + formal | v0.10 cumulative observation lattice, exact contraction | Supported for frozen release | Signature implementation not cumulative or reproduction failure | Engineered signature lattice only |
| C8 | A substantive inter-model collision can occur in OLMo after development-only intervention selection. | Empirical confirmatory | v0.10 layer-14 MLP ablation: 0/12 observation flips, ~69.6% hidden displacement, 3/12 counterfactual flips | Supported for frozen release | Selection leakage, receipt mismatch or observation replication failure | OLMo revision, ARC operator and intervention family only |
| C9 | Raw intervention command magnitude is not a model-independent effect size. | Formal / architectural / empirical | Realization-map decomposition; OLMo normalization symmetry; contrast between scale-3 and ablation | Supported with explicit mechanism | Architecture analysis wrong or realized-effect metrics invalid | Tested architectures/interventions only |
| C10 | Exact collision prevalence varies across real-data blocks within the same declared jurisdiction. | Empirical / Bayesian | v0.11 six-block audit | Open until v0.11 closes | No cross-block variation or failed collector | One model, one domain, frozen block design |
| C11 | Local posterior uncertainty can guide future probes without overriding exact certificates. | Bayesian decision support | v0.11 hierarchical sensitivity + dependence-preserving Bayesian bootstrap + EIG | Open until v0.11 closes | Posterior implementation failure or unstable sensitivity | Follow-up prioritization only; no authority |
| C12 | Behavioral equivalence alone does not license mechanistic, biological, phenomenal, normative or authority equivalence. | Meta-inferential | C1–C8 plus typed no-lift calculus | Supported as a non-entailment rule | A declared identifying bridge satisfying assumptions | Does not assert impossibility under richer bridges |
| C13 | Capacity does not imply authority. | Formal constitutional | KCH typed leases and absence of capability→authority transition | Proved for declared transition system; runtime refinement remains separate | Executable bypass or runtime/spec mismatch | Declared KCH spec/runtime only |

## Prohibited manuscript upgrades

The following formulations remain prohibited:

- “LLMs do not understand anything.”
- “Artificial systems can never be conscious.”
- “Behavior never reveals mechanism.”
- “All AI is statistical.”
- “The technology is globally inferior or superior to humans.”
- “The v0.11 posterior is a population probability over all prompts or models.”
- “A model output grants authority.”

## Canonical main claim

> For a declared admissible system class, a property is scientifically supported only to the extent that it is identifiable from the declared observation and intervention family. In real open-weight SSEC, finite behavioral operators can collapse materially different internal interventions; refining the observation or adding probes contracts those equivalence classes. No mechanistic, biological, phenomenal or authority attribution follows without its own identifying bridge.
