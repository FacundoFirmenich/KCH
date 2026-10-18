# Adverse history — BIFM v0.12

## AH-012-001 — incorrect Belebele repository path

The first workflow attempted to download `data/<language>.json`. The resolved `facebook/belebele` revision exposes the language test data at `<language>/test/0000.parquet`. Every language collector raised `EntryNotFoundError` before loading the model or producing observations.

Decision: preserve the failed run `39095951699` in lineage. Add a data-layout adapter that redirects only the frozen dataset file path and loads the parquet records without changing item selection, prompts, model, operators, splits or metrics.

## AH-012-002 — pipeline status masked by `tee`

The initial shell steps piped Python and `sha256sum` output to `tee` without `set -o pipefail`. GitHub therefore reported successful steps even though the left-hand commands had failed. Tiny artifacts containing only empty logs and partial hash files were uploaded, and the summary failed to find the required CSV files while its own exception was similarly masked.

Decision: the initial green workflow is invalid and cannot support any scientific claim. The repaired workflow uses `set -euo pipefail`, explicit `test -s` assertions and JSON receipt validation before hashing or upload.

## AH-012-003 — exact source identity remains unclaimed

The TALM/TALON configurations and provenance hashes are exact registry records. The operator formulas are a transparent registry-conformant reimplementation because the historical executable notebooks were not available as a directly importable frozen package in the recovered source tree.

Decision: all receipts and manuscripts must distinguish configuration identity from implementation identity. Byte-identical historical behavior remains an external replication gate.
