# Sequential–sharded equivalence protocol

The original v0.11 collector and the v0.11.1 sharded successor implement the same scientific design through different compute graphs.

## Objects compared

For each layer and intervention index:

- item ID order;
- answer keys;
- content-level top-1;
- four-choice rank signature;
- 8-bin choice-probability signature;
- full-vocabulary top-8 token IDs;
- full-vocabulary top-32 token IDs;
- captured layer-output hidden vectors;
- model and dataset revisions.

## Exact fields

The following must match byte-for-byte after normalization of container metadata:

- IDs and answer keys;
- top-1;
- rank-4;
- quantized choice signatures;
- vocabulary top-k IDs.

## Floating fields

Hidden arrays are generated with the same model revision, CPU dtype, prompt order and batch size. Exact byte equality is expected on the same numerical stack. If exact equality fails but every discrete signature agrees, the discrepancy must be quantified by maximum absolute and relative error before any result is accepted.

No averaging or silent tolerance is permitted.

## Result equivalence

The exact collision table, control-coordinate frontiers and sample manifest must match exactly.

Effect-normalized frontiers and posterior tables must match within a preregistered numerical tolerance only if floating hidden arrays differ. The tolerance and cause must be recorded prospectively in an adverse-history successor before comparison.

## Failure states

- `MISSING_SHARD`
- `METADATA_MISMATCH`
- `DISCRETE_SIGNATURE_MISMATCH`
- `HIDDEN_ARRAY_MISMATCH_UNEXPLAINED`
- `SUMMARY_MISMATCH`
- `PASS_EXACT`
- `PASS_NUMERIC_WITH_BOUNDARY`

The existence of a faster sharded result does not authorize promotion when the slower sequential implementation disagrees.
