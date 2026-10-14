# BIFM–CertiClaim v0.6.0-alpha0

This successor makes the no-human formal core reproducible from the repository itself.

## Dual gate

1. **Formal validity:** a certificate establishes the stated formal claim in the declared admissible class.
2. **Semantic fidelity:** a controlled-language rendering must parse back to the same formal object.

Unrestricted prose remains `OPEN_WORLD_UNCERTIFIED`; proof checking alone is not treated as semantic adjudication.

Local reproduction artifact: `certiclaim_all_in_one.py` (to be committed separately on this branch).

Expected frozen invariants: 813,297 partition-pair checks; 22,207 identifiable; 791,090 non-identifiable; 4,320 balanced formal instances; zero checker disagreements; zero controlled-language round-trip failures.
