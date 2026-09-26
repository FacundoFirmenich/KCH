# CFL–UEP G1.1 — carved-cheese object-level material gate

This branch executes the next material gate after the walnut G1 result revoked its initial positive interpretation under stronger adaptive baselines.

## What changes

The new `O3` is not an adaptive image regularizer. `BFTC` performs two order-sensitive transports between the approximate inverse fibers induced by `O1` and `O2`:

1. add information from `O2` while penalizing displacement visible to `O1`;
2. repeat with the order reversed;
3. fuse both transported states;
4. measure their normalized holonomy;
5. abstain unless cross-view gain, preservation, validation and holonomy gates all hold.

## Scientific status

- Independent measured physical object: yes.
- Strong self-adaptive and IRLS baselines preregistered: yes.
- Sealed angular test touched only after configuration freeze: yes.
- Canonical `TOS\` implementation: no.
- Authority, promotion and canonization: none / blocked.

The workflow downloads `DataFull_128x45.mat` directly from Zenodo and aborts unless MD5 equals `ab615bdafdf93d0c14df89c0e0dd5257`.
