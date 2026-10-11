# Scientific interpretation — MHD signed-helicity forecast gate v1.1

## Question

The gate asks a deliberately narrower question than whether magnetic helicity exists or matters physically:

> Do signed SHARP helicity proxies add replicated out-of-sample predictive information for M1+ flares beyond nonhelical magnetic predictors and unsigned helicity magnitude controls?

Three nested families were compared:

\[
\mathcal M_B,
\qquad
\mathcal M_U=\mathcal M_B+|H|,
\qquad
\mathcal M_H=\mathcal M_U+H_{\rm signed}.
\]

The signed family contains `MEANJZH`, `MEANALP`, their six-hour increments and hemispheric interactions. The unsigned control contains `ABSNJZH` and `TOTUSJH`. The nonhelical baseline contains flux, shear, current, free-energy, neutral-line and area predictors.

The unit of independence is the NOAA active region. No active region crosses train, calibration, TEST_A or TEST_B. Hyperparameters are selected using train and calibration; both tests are then evaluated once.

## Result

The pretest power gate passed for all three horizons and both test periods. Nevertheless:

```text
replicated positive horizons     0 / 3
required for family claim        2
outcome                          UNSIGNED_MAGNITUDE_OR_NONHELICAL_RIVAL_SUFFICIENT
```

### M1+ within 12 hours

```text
TEST_A  signed-minus-unsigned log-score gain  -0.0000377841
TEST_B  signed-minus-unsigned log-score gain  -0.000124183
```

The signed extension is directionally worse in both periods. Its AUPRC gain is small and positive in TEST_A but negative in TEST_B; neither bootstrap lower bound is positive and neither Holm-adjusted test passes.

### M1+ within 24 hours

```text
TEST_A  signed-minus-unsigned log-score gain  -0.00420549
TEST_B  signed-minus-unsigned log-score gain  -0.00457906
```

This is the clearest negative horizon. The signed family loses in log score, RMSE and AUPRC in both periods. It is not merely below the material threshold; its direction of effect is adverse.

### M1+ within 48 hours

```text
TEST_A  signed-minus-unsigned log-score gain  -0.0000449748
TEST_B  signed-minus-unsigned log-score gain  +0.000506833
```

TEST_B contains the only positive signed-minus-unsigned log-score difference, but it is approximately twenty times smaller than the locked 0.01-nat material threshold, does not replicate in TEST_A, has a negative 95% cluster-bootstrap lower bound and fails the required bootstrap-positive fraction.

## Reproducibility

The canonical execution used Python 3.11, NumPy 2.1.3 and scikit-learn 1.5.2. An independent replay used Python 3.12, NumPy 2.3.5 and scikit-learn 1.8.0. It reproduced:

- the aggregate outcome;
- the positive/negative status of every horizon and period;
- every selected model family and material gate;
- all reported numerical quantities within a maximum absolute difference of
  \(4.30049\times10^{-12}\).

The result is therefore not attributable to the numerical software environment within the tested versions.

## What the negative result means

Within this fixed scalar-feature model class, the sign of the selected SHARP helicity proxies does not add material and replicated forecasting information beyond their unsigned magnitude and ordinary magnetic complexity predictors.

This supports none of the following stronger claims:

- magnetic helicity is physically absent;
- magnetic helicity is dynamically irrelevant;
- spatially resolved helicity transport cannot matter;
- helicity-injection estimates based on vector velocities would also fail;
- signed helicity cannot help different outcomes, cadences or active-region populations.

The tested object is a predictive increment of two scalar signed proxies, not the full gauge-aware magnetic-helicity content of the coronal field.

## Decision

The scalar signed-proxy M1+ forecasting line is closed under the tested specification. Reopening it on the same tests by adding interactions, changing targets, changing thresholds or selecting a favorable horizon is prohibited.

A scientifically distinct successor would require a new prelock and a more direct observable, such as spatially resolved helicity flux or injection derived from vector magnetograms and a frozen velocity estimator, evaluated on active regions not used here.
