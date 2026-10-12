# KCH Helical v0.17 — specification-derived nonidentical null runtime

The historical v0.8.4 `null_runtime.py` and `test_null_runtime.py` were not
recoverable byte-for-byte from the available Git and Actions transports. The exact
historical freeze compiler was recovered, and the v0.13 contract, ledger census,
operator semantics and governance boundaries remain preserved as derivation inputs.

v0.17 is therefore a **new successor**, not a restoration. It must never inherit or
reuse the historical runtime contract ID, ledger ID, ledger SHA-256 or freeze ID.

The successor provides:

- a pure, no-I/O structural runtime;
- deterministic content-addressed seeds and job IDs;
- the exact frozen 6,376-job census;
- explicit bindings to the qualified v0.16 operator surface;
- a train/calibration-only partition firewall;
- strict qualification adjudication with `PASS`, `NOT_EXECUTED` and `FAIL_CLOSED`;
- adversarial tests for missing, duplicate, tampered and test-accessing records;
- an explicit proof that every v0.17 identity differs from the historical v0.13
  identity;
- no observations, no parent edges, no directional rows and no model score.

A successful freeze authorizes only the next finite gate:

`CALIBRATION_ONLY_FULL_RUNTIME_QUALIFICATION_6376_JOBS_NO_TEST_ACCESS`

It does not validate physical helicity, monodromy, predictive value, publication,
promotion or canonization.
