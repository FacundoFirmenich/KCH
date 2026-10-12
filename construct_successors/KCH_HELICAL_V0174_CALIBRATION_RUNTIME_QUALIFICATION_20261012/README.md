# KCH Helical v0.17.4 — full runtime qualification, no test access

This successor consumes the deterministic v0.17.3 specification-derived runtime
and executes the entire frozen 6,376-job schedule **twice** on deterministic
structural fixtures.

This is a software/runtime qualification gate, not a scientific experiment.
The fixtures exist only to exercise every frozen operator, dependency class,
seed, job identity, result-record contract, and final adjudicator. They must never
be described as observations, calibration data, evidence for helicity, or a
substitute for the real calibration input gate.

PASS requires:

1. exact v0.17.3 runtime-contract, ledger ID, ledger SHA-256, and 6,376-row census;
2. exact qualified v0.16 operator source;
3. execution of every scheduled job in each of two passes;
4. non-empty content hashes and operator diagnostics for every PASS record;
5. byte-identical result JSONL across both passes;
6. v0.17 qualification adjudication = `RUNTIME_QUALIFICATION_PASS`;
7. zero sealed-test access and zero scientific result;
8. historical v0.13 identity transfer remains forbidden.

The next gate, if PASS, is not sealed-test scoring. It is a separate finite-authority
binding of **real calibration inputs only** to the qualified runtime while preserving
the test firewall.
