# CFL–UEP G1: real measured tomography discovery execution

This branch executes the first material gate of `CFL-UEP-0.1.0` without merging into `main` and without granting scientific authority.

## Data

The workflow downloads the exact 8,083,003-byte `Data82.mat` file from the UBC MATH307 mirror at commit `e50e49baf8915a2fa4991b490101ee04222b732f`. Execution aborts unless its MD5 equals the FIPS/Zenodo published checksum:

```text
5698942708300bc34b87931c6d91f6b6
```

Canonical upstream DOI: `10.5281/zenodo.1254206`.

## Discovery design

Three deterministic angular folds are used. In each fold:

- 20 angles are sealed as test projections;
- 20 different angles are used only for hyperparameter selection;
- the remaining 80 angles are split into complementary `O1` and `O2` sublattices;
- matched joint baselines and the proto-TOS arm receive exactly the same 80 measured angles;
- the withheld test block is evaluated only after parameter selection.

The proto-TOS arm is deliberately labelled **protoform**. It preserves the two partial reconstructions, constructs a `Phi12` field from their shared edges and disagreements, and performs an adaptive graph-Laplacian `O3` closure solve. It is not claimed to be the final canonical Transmuter or a universal implementation of `TOS\`.

## Outputs

The workflow emits a GitHub Actions artifact containing:

- the exact measured `.mat` snapshot;
- data audit and cryptographic hashes;
- fold-level tuning traces;
- held-out metrics;
- reduced Fisher/null-space diagnostics;
- false-closure checks;
- perturbation persistence;
- montage;
- run/environment manifest;
- explicit adjudications and limitations.

Allowed authority remains `NONE`; promotion and confirmation remain blocked.
