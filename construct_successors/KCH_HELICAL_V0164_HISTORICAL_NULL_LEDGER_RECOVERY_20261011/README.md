# KCH Helical v0.16.4 — historical null-ledger recovery

This successor consumes the successful v0.16.3.1 code-only source custody and
recovers the exact v0.8.4 compiler/runtime source from the frozen Git transport at
commit `e458afe20b8172db5a04194224cf21df5ec00dc4`.

The gate is deliberately code-only. It verifies all frozen Git blobs and canonical
source hashes, materializes the exact compiler/runtime/test files, compiles them,
freezes the compiler CLI and AST surface, and persists a content-addressed recovery
receipt. It also carries the exact v0.13 runtime contract, ledger summary and status
as verification targets.

The gate does **not** acquire earthquake observations, deserialize the mechanism
catalogue, reconstruct directional rows, regenerate parent edges, execute any of the
6,376 qualification jobs, access the sealed test, score a scientific model, publish,
promote, or canonize physical helicity.

A successful v0.16.4 recovery is only the prerequisite for a distinct successor that
will regenerate and verify the complete 6,376-row ledger and then execute the
calibration-only runtime under finite authority.
