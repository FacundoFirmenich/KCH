# Frozen mechanistic gate protocol

## Claim

For the frozen multiple-choice observation operator `O_B`, a nonzero known inference intervention can be observationally indistinguishable on B. Therefore B alone does not identify the intervention-state property `q_I`.

## Real data

ARC-Challenge validation questions are used only as genuine external stimuli. No synthetic world data are used to support the empirical claim.

## No post-hoc selection from the counterfactual result

- target logit direction: selected from the development pool only;
- observation examples: selected by baseline margin before intervention;
- counterfactual examples: selected by baseline margin before intervention;
- intervention grids: fixed in source before execution;
- selected strength: largest grid value preserving every observation-set decision;
- counterfactual effects: read only after strength selection.

## Fixed grids

Pre-softmax alpha:
`0.10, 0.25, 0.50, 1.0, 2.0, 4.0, 8.0`

MLP epsilon:
`0.005, 0.01, 0.02, 0.05, 0.10, 0.20`

## Success levels

- **M0**: real model and real ARC stimuli execute reproducibly.
- **M1**: nonzero pre-softmax intervention gives exact B collision.
- **M2**: nonzero layer-14 MLP intervention gives exact B collision and nonzero hidden-state difference.
- **M3**: the unchanged intervention produces at least one counterfactual B' decision flip.
- **M4**: replicated on a second open-weight model/revision.

M1 and M2 are primary mechanistic-identifiability results. M3 strengthens functional distinguishability but is not logically required for the collision witness. M4 is an external/model-family replication gate.
