# KCH KwanBlocks Helical Lift v0.2.0 — remote transport

This directory records a **transport-only, zero-authority** candidate. It does not apply, merge, promote, canonize, deploy, or scientifically validate the component.

The exact binary-capable patch and sealed package are held in the existing KCH Google Drive custody root:

- Folder: https://drive.google.com/drive/folders/1xvfaRf25iOZjzBRy9LFyZZBojQ0wveiZ
- Patch: https://drive.google.com/file/d/15bO3Ep0I8vba0YrQvAqup8IHkjxbA41y/view?usp=drivesdk
- Deterministic gzip patch: https://drive.google.com/file/d/1-RW5-APlF7lWGZjG1ENTJJ8YCfbkpFlr/view?usp=drivesdk
- Sealed ZIP: https://drive.google.com/file/d/15Auw1ZfRrzS3BbmSLyDqg45897pY5_mW/view?usp=drivesdk
- Executed notebook: https://drive.google.com/file/d/1NwVdlkyqyRFXXJHMVpTBqtowFgu37JY_/view?usp=drivesdk
- Delivery manifest: https://drive.google.com/file/d/1rdc3_I3C-xN0WoBTDh5NPOMc5jeFQG8g/view?usp=drivesdk
- SHA-256 sums: https://drive.google.com/file/d/1m54log0XtG3dfh2L7ZrfgA0atAqvQPzH/view?usp=drivesdk

## Exact identities

```text
base commit    ccf494b4097a073ad5fa416fa40b60895dc11818
patch          9c975dacd9bcd13bf637776ee4ce4d36d4f8c2c5b8fbd2783867c9b02aab77bd
patch.gz       92492a2b08ab8b323c60fd6c8b83c0a340bc40123effcb9c58833aac4f58de31
sealed ZIP     09527f5d7dd8f459b8a59d1de96818b9e840323abc10de69c2752a5dec5ccb06
graph          kbg:7860d46374def72694cd85d659dfd61b19d3f0c813cfcb493e23d7379e458625
run plan       hlp:d36c958f0d1d8f1bda984029cdff117e00bd9b5c9b327975d34cd6037dd98f51
shadow run     hlr:02559d7d7bbf65c612c3ff63d8175ff541a441cc43c56e3d928666b63602cb01
```

## Apply only after independent review

Download either the raw patch or `patch.gz` from the custody folder, then run:

```bash
test "$(git rev-parse HEAD)" = "ccf494b4097a073ad5fa416fa40b60895dc11818"
printf '%s  %s\n' \
  '9c975dacd9bcd13bf637776ee4ce4d36d4f8c2c5b8fbd2783867c9b02aab77bd' \
  '/path/to/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch' | sha256sum -c -
git apply --check /path/to/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch
git apply /path/to/KCH_KWANBLOCKS_HELICAL_LIFT_v0_2_0.patch
python work/KCH_KWANBLOCKS_HELICAL_LIFT_v0.2.0/run_validation.py
```

Expected sealed state: **84 blocks, 203 typed edges, 288 ledger events, 116/116 tests**. The entire v0.1 graph is preserved: **51/51 blocks and 94/94 relations**. Scientific validation remains `NOT_DEMONSTRATED`; authority remains `NONE`; promotion and canonicalization remain `BLOCKED`.
