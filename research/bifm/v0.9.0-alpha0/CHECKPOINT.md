# BIFM–CertiClaim v0.9.0-alpha0 checkpoint

**Status:** `PASS_QWEN_FRONTIER + PASS_OLMO_COLLISION_WITH_WEAK_EFFECT_BOUNDARY`

**Frozen source commit:** `295bc23638788256c0cbb16f4555dd97aaad806b`

**GitHub Actions run:** `39075393041`

## Material gains

### 1. Invisibility is now mapped, not merely exhibited

The Qwen track estimates a grid-limited intervention invisibility frontier across three layers and four nested observation-set sizes. The result demonstrates that the maximum invisible MLP scaling is strongly layer- and sample-dependent.

### 2. Observation refinement matters materially

At Qwen layer 14, the largest invisible epsilon is 2.00 for 12 observed items but only 0.35 after adding four more items. The observation family, rather than behavior in the abstract, determines what is identifiable.

### 3. Top-1 is a coarse observation operator

At layer 24, a scale of 3.00 produces approximately 50.4% relative hidden-state displacement and nonzero full-distribution divergence while preserving all observed and counterfactual top-1 decisions. Identifiability therefore depends on which behavioral statistic is retained.

### 4. Inter-model replication remains asymmetric

OLMo reproduces an exact top-1 collision under a scale-3 MLP intervention, but the measured post-residual displacement is only approximately 2.99e-05 and no counterfactual flip occurs. This is retained as a weak-boundary result, not promoted to a strong M4 replication.

## Closed gates

- real open-weight intervention execution;
- permutation-controlled observation operator;
- layer-by-sample frontier on Qwen;
- exact receipts and frozen revisions;
- independent-family narrow collision on OLMo;
- artifact hashing and clean CI execution.

## Open gates

- observation-operator lattice and empirical monotonicity;
- substantive-effect inter-model replication;
- multiple observation samples and uncertainty;
- third model family;
- intervention-family diversity;
- connection to TALM/TALON and KCH authority tracks.

## Claim ceiling

The release establishes only observation-relative non-identifiability of declared intervention-state properties. It does not establish global mechanistic equivalence, biological equivalence, consciousness, understanding, agency or authority.
