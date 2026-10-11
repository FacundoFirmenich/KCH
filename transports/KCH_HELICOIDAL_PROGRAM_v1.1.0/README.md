# KCH Helicoidal Program v1.1.0 — MHD result and terminal seismic gate

## MHD/solar result

The prelocked comparison was:

```text
B  nonhelical magnetic baseline
U  B + unsigned helicity magnitude controls
H  U + signed helicity proxies and hemispheric interactions
```

The census and pretest power gates passed. Held-out TEST_A and TEST_B were then opened once for M1+ forecasting at 12, 24 and 48 hours.

```text
OUTCOME                         UNSIGNED_MAGNITUDE_OR_NONHELICAL_RIVAL_SUFFICIENT
REPLICATED POSITIVE HORIZONS    0 / 3
PHYSICAL HELICITY               NOT DEMONSTRATED
```

No signed extension passed the locked 0.01-nat log-score, 5% RMSE, 0.02 AUPRC, calibration, bootstrap and Holm rule in both independent test periods. The 24-hour signed model was directionally worse in both tests. The small positive 48-hour TEST_B gain was far below materiality and did not replicate.

An independent numerical replay under Python 3.12 / NumPy 2.3.5 / scikit-learn 1.8.0 reproduced the outcome and horizon status. The maximum absolute numeric difference from the canonical Python 3.11 / NumPy 2.1.3 / scikit-learn 1.5.2 execution was `4.300490519248967e-12`.

The negative result applies to the locked SHARP scalar-proxy forecasting class. It does not prove that magnetic helicity is physically absent or causally irrelevant.

## Terminal seismic gate

Before opening new post-2021 focal angles, the complete external-fault junction graph was frozen. An overlap audit found that the original Bay Area and Parkfield bounding boxes shared 909 event IDs. Every overlapping event was abstained from both primary cohorts before angle access, preserving independent replication.

The disjoint blind cohorts are:

```text
Bay Area      4,466 assigned events; 1,117 sealed test events
Parkfield     1,023 assigned events;   256 sealed test events
```

The full-network graph raises conservative parent support to 1,041/1,117 Bay Area test children and 226/256 Parkfield test children. The terminal protocol, model grid, materiality thresholds and closure rule were locked before directional acquisition.

The seismic scientific result is not yet recorded in this transport until exact selected-event products finish acquisition and the one-time held-out test is adjudicated.

## Governance

```text
MHD PROMOTION          BLOCKED
SEISMIC PROMOTION      BLOCKED
CANONICALIZATION       BLOCKED
MERGE                  NOT PERFORMED
AUTHORITY              NONE
```

Detailed MHD identities are in `MHD_SIGNED_HELICITY_RESULT_INDEX.json`. The terminal seismic result will be added append-only after completion; the current lock and abstention state must not be overwritten.
