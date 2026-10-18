# Frozen v0.12 protocol

## Strategic objective

Test whether TALM/TALON pre-softmax telemetry can act as a useful **sensor** for local intervention headroom and whether a separate no-preserve TALON arm can act as a beneficial **offline actuator** in a new model family and a real fully parallel multilingual domain.

The design deliberately separates:

- sensor utility;
- actuator utility;
- routing recommendation;
- execution authority.

Only the first three are evaluated. Authority is absent.

## Frozen jurisdictions

### Model

`tiiuae/Falcon3-1B-Instruct`

The exact model revision is resolved through the Hugging Face API before loading and stored in each receipt.

### Data

`facebook/belebele`

Languages:

- `eng_Latn`;
- `fra_Latn`;
- `spa_Latn`;
- `por_Latn`.

The exact dataset revision is resolved before file download. Within each language, records are ordered by `SHA256(link|question_number)`. The first 96 parallel identities are used.

### Split

- rows 0–31: development;
- rows 32–95: confirmatory.

The key set and revisions must match across all languages or the release fails.

## Frozen task operator

For every item:

1. render all four cyclic answer-order permutations;
2. execute one next-token forward pass for each permutation;
3. extract full-vocabulary logits;
4. apply each operator to the same frozen logits;
5. map displayed A/B/C/D scores back to answer contents;
6. average the four content-level scores;
7. compute prediction, correct probability, log loss, Brier score, margin, entropy and correct-answer rank.

## Frozen operator identities

### TALM sensor

`action_id: talm_mass_right_soft`

- registry configuration SHA-256: `8e310bbeba60b256d11246825fda71587dcbe6354d73291b5adb6e2b5ca32872`;
- preserve top-1: true;
- matched control: raw logits / temperature 1.0.

### TALON sensor

`action_id: talon_mass_right`

- registry configuration SHA-256: `67875f7e54c14e3aa11b7dea3120ee054116b951ebd2507b8f524c1b9e40712a`;
- preserve top-1: true;
- matched control: temperature 0.8.

### TALON actuator ablation

`action_id: talon_mass_right_no_preserve_exploratory`

- registry configuration SHA-256: `4dc71ef7281be381ce41dbff8d987f89c048ec98d4dd8d05c145da8df29bd9f4`;
- preserve top-1: false;
- source role: ablation;
- use in v0.12: offline actuator only.

## Operator implementation boundary

The historical configurations and their provenance hashes are exact registry records. The formulas in `talm_talon_ops.py` are a transparent registry-conformant reimplementation. The release does not claim source-code identity with the historical notebooks.

The implementation must pass:

- preserve-top-1 invariance for both sensor arms;
- nonzero, nonconstant logit transformation;
- nonidentical softmax distribution relative to the matched control;
- minimum registered tail/head cardinalities.

## Sensor features

The sensor cannot use telemetry from the no-preserve actuator. Frozen candidate feature families are:

1. `baseline_only`;
2. `talm_sensor`;
3. `talon_sensor`;
4. `combined_sensor`.

Features include matched-control margin and entropy plus preserve-arm:

- full-vocabulary JS divergence;
- four-choice JS divergence;
- top-10 and top-50 overlap;
- logit-delta norms;
- nonconstant-shift residual;
- selected-tail/head counts.

## Actuator target

The offline actuator target is defined relative to the temperature-0.8 matched control.

Primary continuous outcome:

`delta_correct_prob = p_correct(actuator) - p_correct(control)`.

Binary sensor target:

`benefit = 1{delta_correct_prob >= 0.02}`.

Additional outcomes:

- incorrect-to-correct rescue;
- correct-to-incorrect harm;
- top-1 choice change;
- log-loss and Brier changes.

## EIG-targeted transfer strata

For each language, the development distribution of matched-control top-1 margin defines:

- `EIG_TARGET_HIGH_HEADROOM`: confirmatory margin <= development q25;
- `EIG_CONTROL_LOW_HEADROOM`: confirmatory margin >= development q75;
- `MID_HEADROOM`: remaining rows.

The terminology indicates transfer from v0.11's high-EIG low-margin frontier. It is not a newly computed expected-information-gain posterior for Belebele.

## Sensor fitting

A class-balanced L2 logistic model is fitted on all development rows. Four frozen feature-family variants are evaluated. Model fitting uses no confirmatory outcome.

## Local future-only policy selection

For each language independently:

1. score development rows under each sensor family;
2. scan thresholds 0.20 to 0.90 in 0.05 increments;
3. require route coverage >= 0.05;
4. require routed harm rate <= 0.10;
5. require positive development net utility;
6. choose the sensor-family/threshold pair with maximal development net utility;
7. otherwise freeze `ABSTAIN_ALL`.

Per-item utility is:

`delta_correct_prob - 0.25 * harm`.

## Confirmatory metrics

Reported separately by language and stratum:

- sensor AUROC, AUPRC and Brier;
- always-off matched-control performance;
- always-on actuator performance;
- routed performance;
- coverage;
- routed harm and rescue rates;
- net utility;
- paired-bootstrap intervals for accuracy and correct-probability deltas;
- TALM, TALON and actuator telemetry.

## Parallel-language analysis

For every confirmatory item key, the release reports:

- number of languages with actuator benefit;
- number routed;
- number rescued;
- number harmed;
- cross-language mean and dispersion of actuator effect and sensor score.

Cross-language heterogeneity is a primary result, not noise to be averaged away.

## Promotion rule

The release passes only if:

1. all four language jobs pass;
2. model, dataset and registry revisions agree;
3. parallel item keys are identical;
4. preserve-arm top-1 invariants hold;
5. operator nontriviality holds;
6. development and confirmatory rows remain disjoint;
7. policies are selected from development only;
8. confirmatory results are reported locally;
9. receipts and sources are hashed.

## Claim ceiling

A successful result supports only local sensor/actuator claims in the frozen Falcon3–Belebele configuration. It does not establish global decoder superiority, biological equivalence, consciousness, semantic understanding, agency or authority.
