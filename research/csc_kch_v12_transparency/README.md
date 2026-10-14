# CSC–KCH v12 — Cross-Runner Transparent Quorum

This research package is an additive successor to CSC–KCH v11 external
conformance. It does not replace OPA/Cedar policy conformance or the TLC gate.
It binds a concrete transition to:

- the SHA-256 of the v11 portable support vectors;
- a Merkle transparency checkpoint and inclusion proofs;
- an explicit active-key registry;
- a one-use reservation intent for a non-idempotent effect;
- independently signed witness votes from separate CI runner jobs;
- a two-of-three quorum with trust-domain diversity;
- an exactly-once crash/recovery receipt.

The third configured witness is deliberately offline in the canonical workflow.

## Claim boundary

The workflow demonstrates cross-runner process isolation on GitHub-hosted
runners. It does **not** demonstrate organizationally independent witnesses,
physical-host diversity, BFT consensus, hardware attestation, public
transparency, or production execution safety. Test private keys are committed
fixtures and must never be used outside conformance experiments.
