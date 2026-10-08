# KCH/KwanBlocks Helical Lift v0.9 — federated handoff

**Date:** 2026-10-08  
**Outcome:** `ELIGIBILITY_PASS_SELECTION_FROZEN_DIRECTIONAL_FIELDS_STILL_SEALED`  
**Authority:** `NONE`  
**Promotion/canonicalization:** `BLOCKED`

## Closed material gates

- Exact official Mendeley focal-mechanism catalogue acquired and verified: 528,904,117 bytes; SHA-256 `cc13d9e4335bb20579d224c52ea2936d3251719c381c830c23b2abfd0a1eedeb`.
- GEM fault GeoJSON verified against commit/path/blob: 10,622,730 bytes; SHA-256 `37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1`; blob SHA-1 `fb164770b529695544fa864abe2cc9dd8aa5793d`.
- Networkless schema-resolved extraction PASS; safe NPZ opens with `allow_pickle=False`.
- Blind eligibility PASS without focal-angle access.
- Exact selected membership and chronological train/calibration/sealed-test partitions frozen.
- Package-only replay reproduced eligibility and selection byte-for-byte.

## Eligibility

| Cohort | Assigned | Coverage | Eligible |
|---|---:|---:|---|
| Bay Area–Hayward/Calaveras | 34,479 | 0.751078 | yes |
| Parkfield–Central SAF | 23,563 | 0.829537 | yes |
| Mendocino Triple Junction | 7,510 | 0.650160 | no |
| Northern Walker Lane | 9,002 | 0.634301 | no |
| Geysers stress control | 87,042 | 0.727612 | no |

Selected total: **58,042 events**.

## Identities

- KwanBlock: `kb:e6eeb6e8aa806ad06fa71a225f6587bc03a4433e36aead7ed74a42e926f89ab2`
- Event hash: `1696b9183979b23ba6f9e1adf2a0bb923fd3ae7a984f39beb16131bb9406ad0d`
- Ledger receipt: `h9ledger:ff97018aaafaca89b0246fafb03aafdfc6fe8f28ecece029ee8b78d3d1a81cd1`
- Selection receipt: `h9selectionidentity:eb73cb15e4620cb6ea5ac6fc77ffc3b04864fa1ea1ca079f87c755e90a105626`
- Replay receipt: `h9replay:9292a46ec2cc11421371c4a500972a44c62cd171d37028e57c05f1fc35dda0db`
- Validation: `127/127 PASS` — `h9val:31b17b8ffe35b7520a022924c47626f628781598a97f4be3a61672dc0dc61ddd`
- Release: `h9release:1dc0053fb50dfbccc8b6989b5c3941b239911e04f89ac1727c67a7b991abf108`
- ZIP SHA-256: `dc82982034b81f1dc20427628e9707557d4b7081d17f3c51755cf48471c6459a`

## Boundary

No directional field was unsealed; no sealed-test mark was accessed; no ETAS/Hawkes or helicoidal model was fitted; no physical monodromy or helicity claim was evaluated. The next admissible action is a **separate successor** governed by `h9unsealcontract:505420dd928ffb4b06473f294da5026e4c5f9e312973d0b31f57b568c821b069`.
