# Independent event-code corroboration

This tool compares the safe blind mechanism NPZ against immutable public NCEDC and SCEDC earthquake catalogs. It is independent of the frozen scientific gate and cannot authorize eligibility, directional access or fitting.

Before the join, `freeze` records the script hash, NPZ hash, exact catalog commits and all 82 annual Git blob identities for 1981–2021. `run` checks those identities, downloads the exact files, and evaluates the two network-code bijections and two event-code bijections. A record requires the producer's exact event ID and a UTC calendar origin within one second. The sole acceptable corroboration is one unique candidate with 100% coverage and 100% label agreement, without parsing errors. Unknown source types, duplicates, missing IDs and disagreements retain HOLD. No source labels replace catalog values.

Only nine allowed blind fields are accessed. The script never loads pickle or directional arrays. Operational tests elsewhere use software fixtures; this corroboration uses real public records.

```bash
python CORROBORATE_EVENT_CODES_V0_9_2.py freeze \
  --npz /path/to/blind_columns.npz --output /path/to/new-evidence \
  --nc-repo /path/to/pinned-ncedc-clone --sc-repo /path/to/pinned-scedc-clone
python CORROBORATE_EVENT_CODES_V0_9_2.py run \
  --npz /path/to/blind_columns.npz --output /path/to/new-evidence \
  --cache /path/to/catalog-cache
```

The clones must point to the commits in `SNAPSHOTS`; no checkout is needed to obtain the blob identities. Output uses exclusive creation to preserve prior evidence. A reanalysis must retain the original contract and prior attempt, and must not relax its acceptance rule after observing results.

The recorded execution returned HOLD. The diagnostic candidate 1→NC / 2→SC and 0→earthquake / 1→blast has 2,438 label disagreements, 12,107 missing IDs, 6,820 origin-time mismatches and 1,370 unsupported types. No bijection passed. This does not prove the producer's encoding is wrong; its meaning remains uncertified.

The frozen reader rejected 30 SCEDC source times with seconds 60.00 or 60.99. Its global type table includes `ex`, documented for NC; a separate complete SC type audit found no `ex` records, so that limitation did not affect this run. The original script is retained byte-for-byte for reproduction. Supplementary forensic scripts locate every label disagreement and unsupported type without changing the frozen result. Pass the continuation directory as their first argument; it contains `corroboration`, `catalog-cache` and `remote-run9/expanded/blind`. Their path adapters use the new byte-identical NPZ. `VERIFY_CONTINUATION_EVIDENCE.py` accepts the same continuation directory and verifies source hashes, array hashes, content addresses, the transition chain and conservation of row counts.
