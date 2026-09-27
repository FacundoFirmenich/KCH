# CFL–UEP G3S — StructuralBench exact-certificate kernel

This isolated gate operationalizes StructuralBench-CFL as a tribunal of structural sufficiency. Exact truth and certificates are computed **before** partial observations, obfuscation, adversarial pseudoforms or target-leak cases are generated.

`G3S` is intentionally namespaced away from the separate TALON/RDSS `G3 External Validity and Uplift` lane already present on `main`. This run does not load, select or consume any LiveBench, LiveCodeBench or EvalPlus reserve item.

## Exact domains

- graph topology and isomorphism-class certificates;
- zero-dimensional algebraic geometry with reduced Gröbner bases;
- finite primitive integer/Diophantine constraints;
- symbolic mechanics held out as OOD-domain, with Euler–Lagrange and Noether certificates.

## Structural states

The benchmark distinguishes:

- `1`: exact form;
- `+0`: realvirtual protoform, still ambiguous but correctable by one admissible third observation;
- `0`: operational nullity / non-identifiability;
- `-1`: adversarial anti-state;
- `MODEL_MISMATCH_OVERSUFFICIENT_ORIGIN`: target information preinstalled at origin.

## Primary test

On private held-out constructive tasks only, `TOS_FULL_PROTOFORM` competes against a matched formal exact solver allowed the same one-query budget. If that baseline reproduces the closure, the strong non-reducible `O3` claim is not supported even when the TOS arm solves every item.

Eligibility and origin-leak detection are reported separately from non-reducible closure. A benchmark can validate those constructs while returning `0_NO_NONREDUCIBLE_CLOSURE` for O3.

Authority remains `NONE`; no merge, promotion or canonicalization is authorized.
