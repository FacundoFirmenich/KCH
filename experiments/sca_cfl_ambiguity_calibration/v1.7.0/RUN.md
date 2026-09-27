# Reproduction

The v1.7 directory is a delta over the v1.6 robust-POMDP experiment already present on this branch.

```bash
PYTHONPATH=experiments/sca_cfl_ambiguity_calibration/v1.7.0/src:experiments/sca_cfl_robust_pomdp/v1.6.0/src \
pytest -q experiments/sca_cfl_ambiguity_calibration/v1.7.0/tests
```

The full archived release in Library/Drive additionally contains the Monte Carlo runner, deterministic manifest, full 18-test suite, and a snapshot of the minimal v1.6 planner modules for standalone reproduction.
