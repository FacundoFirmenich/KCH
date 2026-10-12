# KCH Helical v0.17.5 — real TRAIN+CALIBRATION input binding

v0.17.4 qualified the complete 6,376-job runtime twice on deterministic structural
fixtures. v0.17.5 crosses the next material boundary: real public inputs.

The gate intentionally separates two domains:

1. **partitioning enclave** — re-acquires the exact immutable mechanism catalogue
   and fault network; reproduces v0.11/v0.12 observability, partitioning, topology,
   TRAIN-only ETAS/Hawkes parameter lock and CALIBRATION diagnostics; it may
   temporarily see selected strike/dip/rake because the historical split depends on
   directional observability;
2. **v0.17 runtime domain** — receives no row values and executes no null job in
   this gate. It is bound only to content-addressed TRAIN+CALIBRATION lineage,
   counts, locked parameters and parent-edge digest.

This distinction is explicit. We do not call the whole workflow "zero test access":
the partitioning enclave necessarily re-evaluates directional observability over the
selected events. We instead prove that the sealed TEST partition is never scored,
never exported, never passed to the v0.17 runtime and is purged before the gate
terminates.

PASS requires exact reproduction of the immutable v0.12 central invariants:
- mechanism SHA-256 and byte length;
- fault SHA-256 and Git-blob identity;
- v0.11 event/observability/split counts;
- v0.12 parent-graph lock ID;
- v0.12 parent-graph gate ID;
- v0.12 location-operator ID;
- ephemeral parent-edge SHA-256.

The separate ComCat location-uncertainty layer is a mutable observation vintage and
is not falsely required to reproduce historical response bytes here. It remains a
separate successor binding gate after this immutable-source binding passes.
