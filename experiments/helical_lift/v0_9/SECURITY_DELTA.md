# Security delta — v0.8 → v0.9

| Boundary | v0.8 | v0.9 |
|---|---|---|
| Large response download | Whole-body read | Chunked stream with `.part` resume |
| Transaction semantics | Files written directly | Both sources atomically committed together |
| Fault identity | SHA-256 after transport | Exact bytes + SHA-256 + Git-blob SHA-1 + fixed byte count |
| Redirect receipt | Effective URL retained | Query values suppressed; URL hash and parameter names retained |
| Environment | Reset in sandbox | Secret-name scrub before acquisition plus sandbox reset |
| Pickle pre-scan | Complete source loaded into `bytes` | Streaming `pickletools.genops(handle)` |
| Catalog scalar handling | All arrays forced to one length | `num` may be verified as catalog scalar without vector fabrication |
| Event identity | Forced integer | Exact integer/text identity transported as Unicode |
| NPZ commit | Direct write | fsync + atomic rename + external verification |
| End-to-end execution | Separate scripts | One resumable state machine with explicit exit semantics |
| Remote execution | Incomplete template | One ephemeral job; raw inputs excluded from artifacts |
| Post-eligibility action | Narrative rule | Content-addressed successor request, no automatic unseal |

The package still does not provide seccomp filtering or claim protection against every kernel-level exploit. The boundary is defense-in-depth with explicit residual risk, not an absolute sandbox theorem.
