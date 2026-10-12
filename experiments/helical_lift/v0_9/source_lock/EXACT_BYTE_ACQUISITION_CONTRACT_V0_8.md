# Exact-byte acquisition contract — Helical Lift v0.8

## Frozen identities

```text
protocol
h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f

locked before real mechanism-angle access
2026-09-27T03:22:11.303310Z
```

This contract transports evidence into the already locked v0.8 protocol. It may not
modify candidate cohorts, quality filters, fault-assignment rules, model families,
null budgets, uncertainty budgets, thresholds, seeds, or aggregate decision rules.

## Required exact sources

### A. Focal-mechanism marks

- Provider: Mendeley Data / Digital Commons Data.
- Dataset: `2np9vw5v7w`, version `2`.
- DOI: `10.17632/2np9vw5v7w.2`.
- Required file basename: `focmec_ca_final.pickle`.
- Download must be resolved from the public dataset snapshot or public file redirect;
  a page-rendered reconstruction is forbidden.
- Preserve the response entity body exactly and record bytes, SHA-256, response
  headers, effective URL, redirects, content type, and retrieval timestamp.

### B. Independent fault network

- Repository: `GEMScienceTools/gem-global-active-faults`.
- Commit: `56816508ad92fd6846dad1163b1c8c01376a2cd1`.
- Path: `geojson/gem_active_faults_harmonized.geojson`.
- Retrieval must use the immutable commit URL, not a moving branch.
- Preserve exact bytes and record Git blob identity plus SHA-256.

## All-or-none rule

Let `A_M` denote acceptance of the mechanism body and `A_F` acceptance of the
fault-network body. Eligibility execution is authorized only if

\[
A_{\mathrm{elig}}=A_M\land A_F=1.
\]

No partial run, substitute catalog, browser extraction, mirror with unproved byte
identity, or silent text normalization is admissible.

## Pickle boundary

Python pickle is code-capable. The acquired mechanism pickle must not be opened in
the acquisition process or in a network-enabled analysis process. It is passed to a
disposable extraction sandbox with:

- network disabled;
- read-only root filesystem;
- source mounted read-only;
- only an empty output directory writable;
- no secrets or repository credentials;
- dropped Linux capabilities and `no-new-privileges`;
- CPU, memory, process and wall-clock limits.

The sandbox emits a safe, non-executable `blind_columns.npz` containing only the
fields enumerated in the locked protocol. Directional fields remain absent. A
second SHA-256 receipt binds the NPZ to the exact pickle.

## Blind eligibility barrier

Before the cohort-selection receipt is sealed, the process may inspect only:

```text
num, nc_sc, ev_bl,
year, month, day, hour, minute, second, time_utc,
evid, lat_reloc, lon_reloc, dep_reloc, mag,
uncer, npol, prob
```

It must not load or summarize:

```text
strike, dip, rake,
strike_orig, dip_orig, rake_orig,
ftype, p_azi, p_dip, t_azi, t_dip
```

Selection is determined solely by the frozen quality filter, bounding boxes,
external-fault assignment, event count, test count, temporal support, and assignment
coverage. The result must declare `angle_fields_accessed=false`.

## Valid successor states

```text
ELIGIBILITY_PASS
NOT_IDENTIFIABLE_MECHANISM_COVERAGE
NOT_IDENTIFIABLE_FAULT_ASSIGNMENT
BLOCKED_EXACT_BYTE_ACQUISITION
BLOCKED_PICKLE_SANDBOX
```

Only `ELIGIBILITY_PASS` can authorize a distinct directional unsealing process. It
does not itself authorize model fitting, physical interpretation, promotion, or
canonization.

## Authority

```text
PROMOTION        BLOCKED
CANONICALIZATION BLOCKED
AUTHORITY        NONE
```
