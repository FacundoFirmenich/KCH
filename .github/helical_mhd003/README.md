# KCH MHD003 — Global-disk helicity–radiative gate

MHD003 is a disjoint successor to MHD001 and MHD002. It does **not** relax, reinterpret, or overwrite either predecessor gate.

MHD001 closed `INSUFFICIENT_REGION_LEVEL_POWER` because its frozen calibration partition contained 6 positive HARPs, below the pre-access minimum of 10. MHD002 closed `PROSPECTIVE_PILOT_INSUFFICIENT_POWER` with 94 unique HARPs and 12 positive HARPs against frozen minima of 100 and 15. In both predecessors, helicity keywords, vector segments, and scientific models remained unopened.

MHD003 changes the observation unit rather than the thresholds. One daily observation is the quality-filtered global-disk aggregate of all admitted definitive SHARP active-region patches at 00:00 TAI. The target is whether any exact NOAA/NCEI GOES M/X flare starts strictly after the snapshot and within the following 86,400 TAI seconds. This removes the sparse HARP-to-NOAA-region association bottleneck while preserving chronological and causal direction.

## Frozen scientific comparison

- `M0`: development prevalence climatology.
- `MB`: prelocked global nonhelical magnetic-complexity block.
- `MH`: exactly the same baseline plus the prelocked photospheric current-helicity proxy block.
- Training: 2010-05-01 through 2017-12-31 TAI.
- Calibration: 2018-01-01 through 2021-12-31 TAI.
- Sealed test 1: 2022-01-01 through 2023-12-31 TAI.
- Sealed test 2: 2024-01-01 through 2025-12-31 TAI.
- A 28-day embargo is applied on both sides of each internal boundary.
- Selection is frozen and content-addressed before either sealed-test metric is evaluated.
- Null families execute only after the full prelocked materiality screen passes.

## Claim ceiling

A positive result could support only: **incremental prospective information in global-disk photospheric current-helicity proxy aggregates beyond the frozen nonhelical magnetic baseline**.

It cannot establish causality, full coronal relative helicity, physical monodromy, universal helicoidal dynamics, operational forecasting efficacy, canonical promotion, or external deployment readiness.

## Data and artifact firewall

Exact NOAA/NCEI annual flare-report bodies and JSOC SHARP chunks exist only in ephemeral runner storage. The uploaded artifact is aggregate-only and may contain receipts, hashes, partition counts, model-selection metadata, aggregate metrics, null summaries, and the locked protocol. Raw sources, row-level features, row-level labels, predictions, HARP identities, and test records are forbidden from the artifact.

## Authority

```text
authority_ceiling = SOFTWARE_CANDIDATE_LOCAL_SHADOW
promotion = BLOCKED
canonicalization = BLOCKED
merge = NOT_PERFORMED
```
