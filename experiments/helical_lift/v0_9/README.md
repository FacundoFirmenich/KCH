# KCH / KwanBlocks Helical Lift v0.9
## Exact-byte acquisition → hardened extraction → blind eligibility

This package is an operational successor to the v0.8 acquisition-sandbox boundary. It does **not** alter the frozen v0.8 scientific protocol and does **not** claim a physical helical result.

## What changes materially

v0.9 replaces the single-shot, memory-heavy transport path with one auditable transaction:

```text
explicit network flag
        ↓
versioned Mendeley snapshot
        ↓
resumable exact mechanism download
        +
immutable-commit fault GeoJSON download
        ↓
all-or-none atomic commit
        ↓
networkless read-only sandbox
        ↓
streaming pickle opcode scan + single deserialization boundary
        ↓
safe NPZ re-opened with allow_pickle=False
        ↓
external Git-blob and SHA-256 lineage checks
        ↓
blind count-only cohort eligibility
        ↓
content-addressed directional-unseal request, only after ELIGIBILITY_PASS
```

The scientific protocol remains exactly:

```text
h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f
```

## Exact source locks

### Mechanism catalog

```text
Provider  Mendeley Data / Digital Commons Data
Dataset   2np9vw5v7w
Version   2
DOI       10.17632/2np9vw5v7w.2
File      focmec_ca_final.pickle
```

Its SHA-256 is deliberately `null` in the source lock until observed from the official response body. No plausible value has been manufactured.

### Independent fault network

```text
Repository  GEMScienceTools/gem-global-active-faults
Commit      56816508ad92fd6846dad1163b1c8c01376a2cd1
Path        geojson/gem_active_faults_harmonized.geojson
Git blob    fb164770b529695544fa864abe2cc9dd8aa5793d
Bytes       10622730
```

A fault file is accepted only if both its byte length and Git object identity match.

## Safety and governance

- Network execution is disabled unless `--execute-network` is explicit.
- Known secret-bearing environment names are removed before acquisition.
- URL query values are never written into receipts.
- Partial downloads live only in a resume cache and cannot satisfy the all-or-none gate.
- The pickle is opened once, inside a new user, mount, network and PID namespace.
- Root, source, program and support code are read-only; only an empty output bind is writable.
- `/proc` and `/dev` are absent; capabilities are dropped; `no-new-privileges` and resource limits are enforced.
- The extractor never materializes the complete pickle as a Python `bytes` object.
- Directional fields remain sealed throughout selection.
- `ELIGIBILITY_PASS` prepares a distinct successor request; it does not authorize model fitting, interpretation, publication, promotion or canonization.

## Execute on a networked Linux host

From the package root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --disable-pip-version-check -r requirements-runtime.txt
python runtime/RUN_EXACT_BYTE_TO_BLIND_GATE_V0_9.py \
  --workspace "$PWD/run-v09" \
  --execute-network \
  --network-timeout-seconds 600 \
  --sandbox-timeout-seconds 5400 \
  --sandbox-memory-mib 8192
```

Exit semantics:

```text
0   ELIGIBILITY_PASS and directional-unseal request prepared
4   dry-run, no effect
10  exact-byte acquisition blocked
20  pickle sandbox blocked
21  blind eligibility execution failure
22  eligibility passed but successor-request construction failed
30  legitimate NOT_IDENTIFIABLE mechanism-coverage outcome
```

## GitHub Actions route

Copy:

```text
ci/GITHUB_ACTIONS_EXACT_BYTE_TO_BLIND_V0_9.yml
```

to:

```text
.github/workflows/kch-helical-v09.yml
```

The workflow uses immutable action commit SHAs, performs all stages in one ephemeral job, exports only receipts/safe derived artifacts and removes the raw sources before artifact creation.

## Current observed state

```text
Local live network attempt     BLOCKED_EXACT_BYTE_ACQUISITION
Failure class                  DNS resolution unavailable in this runtime
Transaction committed          false
Pickle opened                  false
Blind eligibility executed     false
Directional fields unsealed    false
Model fitting performed        false
Physical helicity              NOT_EVALUATED
Authority                      NONE
Promotion                      BLOCKED
Validation                     59/59 PASS
```

The network block is preserved as evidence. It is not interpreted as a negative scientific result.
