# Adverse history — BIFM v0.12

## AH-012-001 — incorrect Belebele source extension

The first workflow attempted to download `data/<language>.json`. The resolved `facebook/belebele` source revision stores the language files as `data/<language>.jsonl`. Every language collector raised `EntryNotFoundError` before loading the model or producing observations.

## AH-012-002 — pipeline status masked by `tee`

The initial shell steps piped Python and `sha256sum` output to `tee` without `set -o pipefail`. GitHub therefore reported successful steps even though the left-hand commands had failed. Tiny artifacts containing only empty logs and partial hash files were uploaded, and the summary failed to find the required CSV files while its own exception was similarly masked.

Decision: the initial green workflow `39095951699` is invalid and cannot support any scientific claim. The repaired workflow uses `set -euo pipefail`, explicit nonempty-file assertions and JSON receipt validation before hashing or upload.

## AH-012-003 — autoconverted parquet ref was confused with source ref

A first repair attempted `<language>/test/0000.parquet`, which is the auto-converted Parquet layout exposed through a separate conversion history, not a file present at the frozen source revision `7899cdfa...`. The fail-closed workflow correctly rejected all four language jobs in run `39096242524`.

Decision: bind execution to the actual frozen source file `data/<language>.jsonl`. No model inference or scientific result occurred in either failed run.

## AH-012-004 — exact source identity remains unclaimed

The TALM/TALON configurations and provenance hashes are exact registry records. The operator formulas are a transparent registry-conformant reimplementation because the historical executable notebooks were not available as a directly importable frozen package in the recovered source tree.

Decision: all receipts and manuscripts must distinguish configuration identity from implementation identity. Byte-identical historical behavior remains an external replication gate.
