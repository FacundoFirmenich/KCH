# BIFM–CertiClaim v0.9.0-alpha0 — frontier + inter-model replication

This successor advances beyond a single constructive collision.

## Track A — M4 inter-model replication

Replicate the v0.8.1 permutation-averaged internal MLP collision on:

- allenai/OLMo-2-0425-1B-Instruct
- independently developed model family
- 16 transformer layers, hidden size 2048
- Apache-2.0 open weights

The exact Hugging Face model revision is resolved and frozen before loading the model, then written to the receipt.

## Track B — empirical invisibility frontier

For Qwen3-0.6B, estimate the grid-limited frontier

[
\epsilon^*(B,\ell,n)=\sup\{\epsilon:O_{B_n}(m_{\ell,\epsilon})=O_{B_n}(m_0)\}
]

over:

- layers 4, 14, 24;
- nested observation sizes 4, 8, 12, 16;
- a frozen epsilon grid;
- the permutation-averaged content-level top-1 operator from v0.8.1.

## Interpretation

The frontier is not a universal property of a model. It is explicitly conditional on:

- model revision;
- layer;
- intervention family;
- observation operator;
- observation sample and ordering;
- tested epsilon grid.

The scientific gain is to move from existence of a collision to a map of where finite behavioral observation ceases to reveal a known internal intervention.
