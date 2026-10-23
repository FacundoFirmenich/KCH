# BIFM–CertiClaim v0.12.1 — non-finite guardrail successor

Status:

```text
PASS_SOFTWARE_SUCCESSOR
+ PASS_FINITE_COMPATIBILITY
+ PASS_NONFINITE_FAIL_CLOSED
+ FRESH_CHINESE_GATE_OPEN
```

This directory is a future-only successor to frozen v0.12.0. It does not rewrite the historical branch or its evidence.

## Build

```bash
python research/bifm/v0.12.1-alpha0/build_successor.py
pytest -q research/bifm/v0.12.1-alpha0/test_nonfinite_guardrail.py
```

The materializer copies the frozen predecessor and applies the exact committed patch. It exits non-zero if the predecessor no longer matches.

## Result

- 24 finite canonical arm-by-shape cases remain bit-identical to v0.12.0.
- Two adversarial non-finite families pass fail-closed mask and top-1 checks.
- Historical Spanish/Phi-4 evidence remains unchanged.
- Authority remains `NONE`.
- Combined scores remain `PROHIBITED_NOT_COMPUTED`.
- Coefficient transport remains `NOT_AUTHORIZED`.
- Fresh InternLM/C-Eval execution remains open.

## Claim ceiling

This is a software guardrail correction only. It does not establish empirical performance, transportability or branch authority.
