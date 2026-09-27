# KwanBlocks Helical Lift v0.6.0 — provider transport blocked

This transport records a **preinferential fail-closed state**. It does not report a positive, negative, or non-identifiable scientific result.

## Closed gates

- protocol locked before v0.6 source-byte acquisition;
- 450-run synthetic power study completed;
- zero detections in 90 null replicates;
- target-effect power: 29/30 at `n=800`, 30/30 at `n=1600`;
- v0.5 data replayed only as a development/false-rescue check;
- one-character base64 transport defect recovered solely by exact match to the prelocked SHA-256;
- inherited scientific runtime and thresholds unchanged.

## Blocked gate

The first official SCEDC provider request exhausted its retry budget at TCP port 443 and returned zero bytes. The all-or-none acquisition contract therefore prohibited requests from progressing to scientific inference. A separate no-analysis endpoint probe observed:

- `service.scedc.caltech.edu`: TCP 443 timeout, zero bytes;
- `stp2.gps.caltech.edu`: TCP 443 timeout, zero bytes;
- `scedc.caltech.edu`: HTTP 301 to the service frontend, followed by the same timeout, zero file bytes.

No mirror, browser-rendered text, normalized reconstruction, partial catalog, or substituted source was admitted.

## Canonical state

```text
OUTCOME                    BLOCKED_OFFICIAL_PROVIDER_TRANSPORT
PROTOCOL_LOCK              PASS
PRELOCK_POWER              PASS
V0_5_FALSE_RESCUE_CHECK    PASS
TRANSPORT_REPAIR           PASS
EXACT_SOURCE_BYTES         0 / 3
MODEL_EXECUTION            NOT_PERFORMED
SCIENTIFIC_RESULT          NONE
NOT_IDENTIFIABLE           NOT_EVALUATED
PHYSICAL_HELICITY          NOT_DEMONSTRATED
PROMOTION                  BLOCKED
CANONICALIZATION           BLOCKED
AUTHORITY                  NONE
```

The exact remote run IDs, artifact hashes, local release hashes, graph identity, and ledger head are recorded in `BLOCKED_GATE_INDEX.json`. The draft transport must not be merged as scientific evidence; it is an auditable successor state and a future resume point for the same locked protocol.
