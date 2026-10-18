# BIFM ↔ TALM/TALON bridge protocol

## Source-grounded role

The existing TALM/TALON programme fixes the following boundaries:

- TALM and TALON are inference-time logit operators;
- the scientific claim unit is a local edge, not global dominance;
- `Z_xpl` is post-hoc local-edge analysis, not an independent decoder and not a human-quality oracle;
- prompt suite, model revision, method hash, runtime manifest and row status must be preserved;
- the same nominal operator strength may have different realized force across models;
- global aggregates are guardrails rather than the primary claim object;
- operator utility may be actuator utility, sensor/probe utility, or neither.

Historical Qwen/Gemma bundles further show that larger global text displacement does not imply more CI-supported local edges, and that operator/model interaction is strongly jurisdictional.

## Typed bridge

Let:

- `m_0` be the baseline SSEC inference configuration;
- `T_{f,c}` be a frozen TALM/TALON operator family `f` with candidate configuration `c`;
- `m_{f,c}` be the realized intervened inference configuration;
- `O_B` be a declared behavioral observation family;
- `q_control` identify the operator command and frozen configuration;
- `q_realized` describe the realized logit/distribution transition;
- `q_behavior` describe observed outputs;
- `q_utility` describe a local task/rival/metric edge;
- `q_authority` describe whether the intervention is permitted.

The bridge preserves:

`q_control != q_realized != q_behavior != q_utility != q_authority`.

No transition among these types is automatic.

## Four experimental roles

### R1 — collision probe

Search for configurations satisfying:

`O_B(m_0) = O_B(m_{f,c})`

with a nontrivial realized logit transition. This provides a negative certificate for identifying `q_control` or `q_realized` from `O_B`.

### R2 — separating probe

Given a baseline/intervention collision under `O_B`, use an independently frozen probe family `P` and test:

`(O_B,P)(m_0) != (O_B,P)(m_{f,c})`.

A valid separator contracts the equivalence class; it does not prove semantic improvement.

### R3 — sensor utility

Treat transient TALM/TALON responses as regime features before choosing a deployment action. Sensor utility is measured by whether the probe improves future-only routing, abstention, baseline selection or jurisdiction detection.

A probe can be useful even when the corresponding operator is not selected for generation.

### R4 — actuator utility

Evaluate the deployed operator candidate against explicit rivals on a frozen local claim unit:

`model × language × prompt_suite × segment × candidate × rival × metric`.

Actuator utility requires task-relevant evidence beyond distributional movement.

## Required telemetry

Each operator execution must preserve, at minimum:

- model ID and exact revision;
- tokenizer and chat-template hash;
- prompt-suite hash and item ID;
- operator family, branch, configuration and source hash;
- baseline logits or sufficient frozen summaries;
- intervened logits or sufficient frozen summaries;
- top-1 preservation status;
- rank displacement;
- top-k overlap;
- KL/JSD/TV where numerically admissible;
- entropy and margin changes;
- generated output and decoder settings;
- runtime precision and quantization condition;
- NaN/inf/blocked-logit handling;
- execution status and receipt hash.

## Realization quotient

Raw TALM/TALON parameters are not assumed comparable across model families. Define the architecture-relative realization map:

`R_A : operator_command -> realized_logit_transition`.

Commands are realization-equivalent when their realized transition is equal under the frozen telemetry, or approximately equal under a preregistered metric/tolerance. Benchmark diversity is computed on realized-transition classes, not candidate names alone.

## Observation lattice

The TALM/TALON bridge extends the existing BIFM lattice with pre-softmax levels:

1. output top-1 / generated-text outcome;
2. output ranking / choice-vector signature;
3. generated-output distributional and structural metrics;
4. next-token logit rank signature;
5. local logit-transition telemetry;
6. operator-command and source receipt.

Finer levels must contain or deterministically recover coarser levels for monotonic identifiability claims.

## Candidate families

Candidates are imported only from frozen versioned implementations. Historical labels such as:

- `talm_mass_right_soft`;
- `talm_mass_left_soft`;
- `talm_balanced_high`;
- `talm_hybrid_right_mid`;
- `talon_mass_left`;
- `talon_mass_right`;
- `talon_hybrid_right`;
- `talon_hybrid_balanced`;

are identifiers, not universal semantic classes. Their meaning is artifact- and version-specific.

## Primary hypotheses

### H-TT1 — local identification

A TALM/TALON intervention may remain invisible under a coarse behavioral operator while being identifiable from finer logit telemetry.

### H-TT2 — probe/actuator separation

Sensor utility and actuator utility need not coincide.

### H-TT3 — jurisdictional topology

Supported edges vary by model, language, segment, candidate, rival and metric; no global dominance is required.

### H-TT4 — realized-force drift

The same nominal candidate can induce different realized-transition magnitudes across models and precision regimes.

### H-TT5 — complementary evidence

TALM and TALON add evidential value only where their probe responses reduce a relevant observation fiber or improve future-only routing after dependence and cost are accounted for.

## Falsifiers

The bridge is weakened or falsified if:

- candidate names do not map to reproducible source/configuration hashes;
- reported intervention telemetry is equivalent to a trivial uniform-logit shift or another declared baseline;
- probe responses add no out-of-sample routing information beyond baseline features;
- local-edge support vanishes under frozen rivals, paired rows or prospective evaluation;
- apparent diversity collapses after quotienting realization-equivalent candidates;
- Z_xpl results are used as quality ground truth rather than post-hoc cartography;
- an operator is promoted from sensor to actuator without task-relevant evidence and authority.

## Promotion states

- `SPECIFIED`: source/configuration/interface frozen;
- `REPRODUCED`: historical result regenerated from raw artifact;
- `COLLISION_CERTIFIED`: exact coarse-observation collision plus nontrivial realized transition;
- `SEPARATOR_CERTIFIED`: independent frozen probe separates a collision;
- `SENSOR_VALIDATED`: prospective routing gain under future-only evaluation;
- `ACTUATOR_VALIDATED`: prospective local utility against explicit rivals;
- `AUTHORIZED`: external KCH lease permits execution;
- `NOT_IDENTIFIABLE` / `NO_LOCAL_EDGE` / `INSUFFICIENT_POWER` as valid fail-closed outcomes.

## Immediate material gate

1. Recover the exact current source files and candidate configurations from the canonical TALM/TALON repository or execution bundle.
2. Reproduce one Qwen and one Gemma historical row family with logits and receipts.
3. Map candidate commands to realized-transition fingerprints.
4. Quotient duplicate/near-duplicate candidates.
5. Freeze a BIFM collision/separator campaign before observing its confirmatory outputs.
6. Use TALM/TALON probe responses as candidate RDSS features only in a future-only successor.

No result from historical summary tables alone may be promoted to a new BIFM empirical claim.
