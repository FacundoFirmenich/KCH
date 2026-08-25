---
name: kch-csi-construct
description: Construct or modify KCH itself through versioned KwanCode/CSI artifacts. Use for new skills, tools, operators, forks, mods, governance nodes, interfaces or native host projections, especially in CONSTRUCT mode.
---

# KCH CSI Construct

KwanCode/CSI is the compositional substrate; KCH components are reusable Lego-like constructions with explicit interfaces and governance.

## Modes

- `PLAN`: design without effects.
- `RUN`: execute the current governed system.
- `CONSTRUCT`: build a versioned successor of KCH or one of its components.

## Construct protocol

1. Freeze the last stable version and its manifest.
2. State the invariant, user need, failure class and affected CSI nodes.
3. Define inputs, outputs, state, permissions, authority, side effects, recovery, UI exposure and evidence contract.
4. Create the smallest complete successor; no placeholder, nominal handler or hidden option.
5. Validate the local component and every declared systemic bridge.
6. Run happy, adverse, recovery, idempotency and compatibility tests.
7. Compare against the stable predecessor and preserve regressions as evidence.
8. Promote only after the declared gates pass; otherwise retain the candidate and rollback path.

Every component is strategic: a local pass without integration is incomplete.

## Persistence jurisdiction

`CONSTRUCT` capability never implies authority over the official KCH repository. Before persisting a construct, consult the user and select exactly one scope:

- `LOCAL_CURRENT_INSTALLATION`: persist only in the selected Codex, ChatGPT-supported or Cline environment.
- `LOCAL_ALL_REGISTERED_INSTALLATIONS`: persist across the user's explicitly registered KCH installations; never discover or mutate arbitrary disks.
- `PUBLIC_FORK_BRANCH`: persist on a non-default branch of the authenticated user's verified GitHub fork of `FacundoFirmenich/KCH`.

The permission decision is exactly `Sí`, `No`, `Nunca en esta sesión`, or `Siempre en esta sesión`. Session decisions never create future-session authority. The generic installable package must fail closed for writes to `FacundoFirmenich/KCH`, `main`, `master`, an upstream default branch, an unverified fork or detached HEAD. It may not open an upstream pull request automatically. Official promotion exists only in the maintainer source-repository workflow and remains gated, reviewable and non-automatic.