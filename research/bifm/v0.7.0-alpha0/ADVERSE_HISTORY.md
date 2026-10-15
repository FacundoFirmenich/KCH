# Adverse history

## AH-001 — v0.6 nominal diversity inflation

The v0.6 benchmark reported 4,320 rows. Reproduction showed extensive structural duplication caused by rotations, proof-class reuse and family labels. Certificates remained valid, but row count overstated inferential diversity.

## AH-002 — coarse status mixed orthogonal properties

The v0.6 status enum mixed type/scope, structural identification, practical stability and recovery. v0.7 factors these into orthogonal axes with an explicit legacy mapping.

## AH-003 — Lean CI bootstrap failure

Initial Lean CI failed before proof checking because the action required a Lake manifest before lake update. The workflow was repaired by installing Lean explicitly and generating the manifest first.

## AH-004 — nanoda export failure

After successful Lean-kernel compilation, nanoda failed in lean4export while importing the project module. This is retained as an infrastructure failure, not converted to PASS.

## AH-005 — leanchecker / axiom-audit module-discovery failures

Subsequent auxiliary checks failed to find the project module although the preceding Lean build succeeded. These failures are not theorem refutations. v0.7 therefore uses Lean kernel compilation as the proof-assistant gate and the separately implemented Z3 solver as the independent finite decision-procedure cross-check.

## AH-006 — no diversity claim from renderings

Natural-language renderings, family labels, scalar instability magnitudes and world relabelings are never counted as distinct inferential structures unless their quotient class differs.
