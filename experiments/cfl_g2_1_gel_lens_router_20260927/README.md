# CFL–UEP G2.1 — DIN lens/router on dynamic gel measurements

This branch executes the next material gate after G2 refuted pixel-state re-entry. DIN is allowed to change only the **future observational lens**: which projection angles are acquired and which deployable temporal operator supplies the prior. Direct injection of an old closure state as the future state is forbidden.

## Physical data

The workflow downloads three official Zenodo files for the dynamic agarose-gel phantom:

- `GelPhantomData_b4.mat` — 17 frames, nominal 256×256 reconstruction scale;
- `GelPhantomData_b2.mat` — 17 frames, nominal 512×512 reconstruction scale;
- `GelPhantom_extra_frames.mat` — densely sampled frame 1 and independent frame 18 at b4.

Execution aborts unless all published MD5 checksums match.

## Why detector-angle space

The public files contain measured sinograms and complete geometry metadata, but no explicit supplied matrix. This gate therefore evaluates active acquisition and prediction directly in measurement space. It does not use a model-generated projector as empirical ground truth and makes no intrinsic image-space or non-Euclidean claim.

## Evaluation

- frames 0–7: historical archive;
- frames 8–11: configuration only;
- frames 12–16: sealed future evaluation;
- frame 18 dense: independent external confirmation;
- common sixty-angle masks are never selectable;
- acquisition budgets: 18, 30 and 45 angles;
- primary budget: 30.

DIN is compared with uniform acquisition, current-frame information gain, recent-history attention, a state-space prior, a low-rank-plus-sparse prior, and order/lineage/source-time ablations. A post-hoc oracle is reported only as a ceiling.

Authority remains `NONE`; promotion, canonization and merge remain blocked.
