# Kwan External Conformance Gate

This harness executes official external engines under a SHADOW-only gate:

- Cedar CLI and OPA differential policy conformance;
- `@ipld/dag-cbor` and `multiformats` byte/CID conformance;
- Wasmtime execution inside a Linux namespace/read-only-filesystem enclosure;
- ORAS OCI-layout round-trip, offline Cosign blob signature, and python-tuf rollback rejection.

The resulting report is evidence only. It grants no KCH authority, installs no ACTIVE capability, and performs no promotion.
