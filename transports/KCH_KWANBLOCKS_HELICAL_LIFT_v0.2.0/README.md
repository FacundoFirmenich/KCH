# KCH KwanBlocks Helical Lift v0.2.0 — remote transport

This directory carries the exact, binary-capable additive Git patch for the sealed v0.2.0 package as bounded base64 chunks. It does not apply, merge, promote, canonize or deploy the component.

## Reconstruct and verify

```bash
TRANSPORT=transports/KCH_KWANBLOCKS_HELICAL_LIFT_v0.2.0
cat "$TRANSPORT"/patch_b64/CHUNK_*.b64 | base64 -d > /tmp/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch.gz
printf '%s  %s\n' '92492a2b08ab8b323c60fd6c8b83c0a340bc40123effcb9c58833aac4f58de31' '/tmp/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch.gz' | sha256sum -c -
gzip -dc /tmp/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch.gz > /tmp/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch
printf '%s  %s\n' '9c975dacd9bcd13bf637776ee4ce4d36d4f8c2c5b8fbd2783867c9b02aab77bd' '/tmp/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch' | sha256sum -c -
git apply --check /tmp/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch
git apply /tmp/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch
python work/KCH_KWANBLOCKS_HELICAL_LIFT_v0.2.0/run_validation.py
```

Expected sealed state: 84 blocks, 203 typed edges, 288 ledger events, 116/116 tests, graph `kbg:7860d46374def72694cd85d659dfd61b19d3f0c813cfcb493e23d7379e458625`. Scientific validation remains `NOT_DEMONSTRATED`; authority remains `NONE`.
