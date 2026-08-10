---
name: kch-kch-prepilot-failures-operating-protocol
description: Apply the evidence-derived KCH-PREPILOT-FAILURES operating protocol. Use whenever work in this scope needs its dated steps, known failures, decisions, claim limits, provenance, or handoff discipline.
compatibility: KCH staged candidate; no automatic host installation
---

# Protocolo operativo — KCH-PREPILOT-FAILURES

Read `references/PROTOCOL.md` completely before acting. Read `references/PROVENANCE.json` when a claim, failure, correction, secret reference, or historic case affects the task.

## Operating sequence

1. Identify the active workspace, session and governing objective.
2. Match the case against the dated protocol; do not infer missing steps.
3. Apply the admitted steps in order and check the recorded failure modes before each consequential action.
4. Preserve raw evidence, pre-hashes, post-hashes, adverse results and claim ceilings.
5. Refer to secrets only through `SECRET_REF` handles. Never copy a secret value into outputs, logs or skill files.
6. Return what changed, evidence boundary, unresolved points and next decision-critical action.

## Abstention rule

If the protocol reports `NOT_ESTIMABLE`, conflicting evidence or missing authority, preserve that state and request only the minimum missing input. Do not fill gaps with plausible values.

## Lifecycle

This skill is `STAGED_UNEVALUATED`. Generation does not install, activate, benchmark or promote it. Promotion requires separate evaluation and user authority.
