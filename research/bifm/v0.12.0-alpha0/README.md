# BIFM–CertiClaim v0.12.0-alpha0 — Falcon3 × Belebele × TALM/TALON

This successor executes the strategic gate identified after v0.11.1:

1. a third independently developed open-weight model family;
2. a second real domain with fully parallel multilingual observations;
3. a second intervention family based on TALM/TALON pre-softmax modulation;
4. explicit separation of sensor, actuator and authority;
5. high-headroom/EIG-targeted jurisdictions versus low-headroom controls;
6. future-only routing selected on development data and evaluated on untouched confirmatory rows.

## Model and domain

- model: `tiiuae/Falcon3-1B-Instruct`;
- model revision: resolved and frozen at execution;
- dataset: `facebook/belebele`;
- dataset revision: resolved and frozen at execution;
- languages: English, French, Spanish and Portuguese;
- language codes: `eng_Latn`, `fra_Latn`, `spa_Latn`, `por_Latn`;
- 96 fully parallel question identities per language;
- 32 development and 64 confirmatory rows per language.

Belebele is a real, human-curated, fully parallel four-choice reading-comprehension benchmark. The same `link × question_number` key identifies the parallel item across languages.

## Answer-order control

Every item is rendered under all four cyclic answer-order permutations. Displayed A/B/C/D logits are mapped back to answer contents and averaged before choice metrics are computed.

## Operator portfolio

The public `EXACT_ACTION_REGISTRY_v1.0` supplies exact historical identities and configurations:

- `talm_mass_right_soft` — preserve-top-1 sensor;
- `talon_mass_right` — preserve-top-1 sensor;
- `talon_mass_right_no_preserve_exploratory` — source-declared ablation used only as an offline actuator.

The runtime formulas are a transparent, registry-conformant reimplementation from those fields. They are not claimed to be byte-identical to the historical notebooks.

## Matched controls

- TALM is compared with the raw-logit baseline because its registered temperature is 1.0.
- TALON is compared with a temperature-0.8 control because its registered temperature is 0.8.
- The no-preserve TALON actuator is compared with the same temperature-0.8 control.

This prevents a temperature effect from being attributed to TALON.

## Sensor–actuator separation

Sensor arms may supply telemetry to a router but do not alter the final decision in deployment logic. The actuator arm is evaluated offline. The experiment never grants authority or executes an external action.

The separation is:

`preserve telemetry -> sensor score -> recommendation -> [no authority in this release]`

and not:

`model capability -> permission -> execution`.

## Future-only routing

Development rows alone determine:

- local margin quantiles;
- sensor model fitting;
- sensor-family selection;
- language-local route thresholds;
- fail-closed abstention when no threshold has positive utility under the harm cap.

Confirmatory rows are scored only after those objects are fixed.

## Local claims

The primary unit is:

`language × headroom stratum × sensor family × routing policy × metric edge`.

No global TALM/TALON dominance claim is authorized. Pooled values are guardrails only.

## Claim boundary

The release can evaluate whether preserve-arm telemetry predicts local offline benefits or harms from a no-preserve actuator. It cannot establish semantic understanding, biological equivalence, consciousness, normative agency or execution authority.
