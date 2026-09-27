# G3 external-validity gate

## Purpose

Move RDSS from the internal ten-prompt micro-suite to public, objective, action-discriminating evaluation. The claim under test is paired uplift of fixed TALON mass-right (TMR) over the raw-logit baseline. SHADOW non-interference is a required invariant, not a substitute for uplift.

## Benchmark order

1. **LiveBench objective tasks** for math, reasoning, instruction following, and data analysis.
2. **LiveCodeBench code generation** for recent, automatically tested programming problems.
3. **EvalPlus HumanEval+ and MBPP+** as a secondary code sanity check.

Every source is pinned by immutable revision and exact task IDs. Dynamic leaderboards or unpinned “latest” datasets are forbidden in a reserve run.

## Execution gates

### G3A — adapter

- Normalize each example to benchmark, task ID, prompt, reference/scorer, split, source revision, and content hash.
- Freeze prompt rendering and answer extraction.
- Record model, tokenizer, Transformers, operator, CUDA/container, and benchmark revisions.
- Verify exact token identity between TMR and TMR+SHADOW on adapter smoke items.
- Generated code is evaluated only in the pinned benchmark sandbox.

### G3B — development headroom

- Development IDs and reserve IDs are disjoint before any operator comparison.
- Run baseline, TMR, TALON mass-left, and TALM mass-right-soft only on development IDs.
- Retain a family only when baseline success is between 5% and 95% and at least one preregistered action-discordant pair exists.
- Rescue results may determine whether a rescue study is worth preregistering; they cannot alter the always-TMR reserve policy.

### G3C — freeze

The freeze records exact item lists and hashes, prompt/scorer hashes, runtime revisions, seeds, decoding, checkpoints, compute limits, endpoints, multiplicity correction, stopping rules, and the one-shot output root. A reserve command must refuse to run if any field is absent or mismatched.

### G3D — one-shot reserve

- Execute only baseline, TMR, and the TMR+SHADOW identity pair.
- Score every frozen item; no selective family removal.
- Primary endpoint: macro-average paired success difference, TMR minus baseline.
- Confirmatory inference: exact McNemar plus paired bootstrap 95% CI; Holm correction across frozen families.
- Require at least 30 discordant baseline/TMR pairs for an uplift claim. Otherwise report the estimate as inconclusive even if positive.
- Any identity, provenance, hash, sandbox, or completeness failure invalidates the run and fails closed.

## Reporting rule

Report denominators, discordant pairs, exact paired differences, confidence intervals, adjusted p-values, harmful-item rate, token-identity failures, and compute. Oracle wins and margin capture remain descriptive. The consumed p07-p10 reserve is never reopened or used for tuning.

## Canonical public sources

- LiveBench: https://github.com/LiveBench/LiveBench
- LiveCodeBench: https://github.com/LiveCodeBench/LiveCodeBench
- EvalPlus: https://github.com/evalplus/evalplus
