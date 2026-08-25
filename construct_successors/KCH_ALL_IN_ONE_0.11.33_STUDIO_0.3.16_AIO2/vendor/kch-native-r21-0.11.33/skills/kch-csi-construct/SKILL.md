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
