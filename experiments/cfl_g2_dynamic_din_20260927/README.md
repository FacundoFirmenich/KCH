# CFL–UEP G2 — dynamic DIN cross-phantom material gate

This isolated branch executes the first material test of **diagonal informational re-entry under real dynamics**. It uses the measured `DataDynamic_128x15.mat` cross-phantom dataset and aborts unless the published MD5 checksum matches.

The supplied 128×128 physical forward operator is reduced to a 64×64 piecewise-constant model by an explicit 2×2 prolongation. This is a declared computational reduction, not synthetic data.

## Split

- frames 0–7: history/training;
- frames 8–11: held transition regime for configuration selection;
- frames 12–15: sealed future evaluation;
- three of fifteen projection positions are withheld in every frame;
- no random row split is permitted.

## Candidate DIN operation

At frame `k`, the six earlier acquisition positions form `O1` and the six later positions form `O2`. Directed transports `O1→O2` and `O2→O1` produce a closure state, reliability lens, holonomy and content-addressed lineage receipt. At frame `k+2`, proper DIN re-enters the `O1→O2` closure as a spatially weighted future lens. Two adversarial ablations reverse the directed order and shuffle the source lineage while preserving the no-future-leakage rule.

This is a proto-DIN operator. It is not the canonical CFL `TOS\\/DIN` implementation.

## Fail-closed status

Authority is `NONE`; promotion, canonization and merge remain blocked. A single resolution cannot promote DIN even if local support appears.
