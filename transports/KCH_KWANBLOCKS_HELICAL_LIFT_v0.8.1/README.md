# KwanBlocks Helical Lift v0.8.1 — directional material gate

This transport records the append-only material successor of the locked v0.8 dynamic marked-point-process protocol.

## What is closed

```text
EXACT_BYTE_ACQUISITION          PASS
BLIND_EXTRACTION                PASS
BLIND_ELIGIBILITY               PASS
SELECTED_DIRECTIONAL_OPENING    PASS
DIRECTIONAL_PREFLIGHT           PASS
```

The exact Mendeley version-2 catalog contains 1,574,113 events. Blind eligibility was performed without reading or emitting focal-mechanism angles. It selected exactly two primary cohorts under the frozen count, time-span and external-fault-assignment rule:

- Bay Area–Hayward/Calaveras: 37,853 events;
- Parkfield–central San Andreas: 23,702 events.

Only after the selection receipt was sealed were `strike`, `dip` and `rake` opened for those 61,555 events. The remaining 1,512,558 catalog rows and the fields `strike_orig`, `dip_orig`, `rake_orig`, `ftype`, `p_azi`, `p_dip`, `t_azi` and `t_dip` remain unopened by this gate.

## Preflight

```text
selected mechanisms       61,555
axially observable        60,577  (98.411%)
Bay Area sealed test       9,320
Parkfield sealed test      5,825
combined sealed test      15,145
```

The conservative same-segment parent diagnostic found candidate-parent support for 89.219% of Bay Area observable events and 96.060% of Parkfield observable events. This diagnostic is not the final ETAS/Hawkes graph.

## What is not claimed

```text
DYNAMIC_MODEL_EXECUTION         NOT_PERFORMED
SCIENTIFIC_RESULT               NONE
PHYSICAL_HELICITY               NOT_EVALUATED
PROMOTION                       BLOCKED
CANONICALIZATION                BLOCKED
AUTHORITY                       NONE
```

The material gate authorizes the next execution stage. It is not itself evidence of signed helical transport.

## Append-only state

```text
base graph
kbg:1c3baf7a496ad5d45ff6954904a0b778ad991636fda1478407344f79af18628a

successor graph
kbg:1fad41342aae06b558998903815df57eb08d4f24f408c6967c53ba7fd1413edb

ledger head
2e23b081d256404fc82340fc4dca206c329b7cb97e5a27fd139b3cae6751e31d

blocks / edges / events
190 / 372 / 567

validation
6,338 / 6,338 PASS
```

The 629 v0.8.0 files remain byte-exact. Detailed source hashes, cohort counts, receipts, remote-run identities and release hashes are in `REMOTE_RESULT_INDEX.json`.

This transport is not merge, publication or deployment authority.
