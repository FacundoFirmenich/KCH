# KCH Helical v0.16.4.3 — forensic exact-runtime recovery

This successor begins from the successful v0.16.4.2 recovery of the independently
transported historical compiler. Its sole purpose is to recover the companion
`null_runtime.py` and `test_null_runtime.py` from the valid, checksummed TAR prefix
inside the historically damaged v0.8.4 transport.

The recovery is not a reconstruction, rewrite, approximation, or repair of source
bytes. The forensic reader:

- verifies the three frozen Git blob identities at commit
  `e458afe20b8172db5a04194224cf21df5ec00dc4`;
- performs strict Base64 decoding;
- inflates only the valid raw-DEFLATE prefix after the parsed gzip header;
- accepts only complete TAR members with valid header checksums and safe paths;
- rejects incomplete members, invalid headers, absolute paths, traversal, symlinks,
  and hardlinks;
- requires all independently recoverable candidate representations to agree on the
  SHA-256 of each admitted target;
- requires the recovered compiler to match the independent v0.16.4.2 compiler
  SHA-256 `5a22e574f1d88f057b85f5b6dd3589f7ad14128ba6e6cd3e807d752a677a6134`.

Only three complete Python members may cross the gate:

1. `tools/freeze_null_perturbation_runtime.py`;
2. `src/kch_helical_dynamic_v08/null_runtime.py`;
3. `tests_v0_8_4/test_null_runtime.py`.

The gate compiles and AST-parses those exact bytes without importing them. It emits
content-addressed receipts and persists no decompressed prefix, compressed suffix,
scientific catalogue, event row, parent edge, directional mark, test value, or model
score.

PASS authorizes only a distinct successor for exact 6,376-row ledger regeneration
and identity comparison. It does not authorize calibration execution, sealed-test
access, scientific interpretation, publication, promotion, or canonization.
