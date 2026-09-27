# KwanBlocks Helical Lift v0.8.2 — ComCat location-uncertainty material gate

This successor closes the location-uncertainty dependency discovered after v0.8.1 directional materialization. It does **not** execute the dynamic marked-point-process model and does not consume the sealed scientific test.

## Material result

```text
OUTCOME                         LOCATION_UNCERTAINTY_CROSSWALK_PASS
DIRECTIONAL FIELDS ACCESSED     FALSE
SCIENTIFIC MODEL EXECUTION      NOT_PERFORMED
PHYSICAL HELICITY               NOT_EVALUATED
PROMOTION                       BLOCKED
CANONICALIZATION                BLOCKED
AUTHORITY                       NONE
```

The statewide focal-mechanism catalog supplies mechanism uncertainty but not event-location covariance/error fields. The locked v0.8 protocol names USGS ANSS ComCat as the external validation provider. ComCat CSV provides `horizontalError` and `depthError`, which are used here solely to materialize the future fault-assignment perturbation operator.

## Crosswalk

The event-matching contract was frozen in the preceding GeoJSON material attempt and inherited unchanged by the CSV successor. The GeoJSON representation matched events well but did not expose the error fields in those responses; that adverse result is preserved rather than deleted.

```text
Bay Area selected                 37,853
Bay Area matched                  37,458   98.9565%
Bay Area both errors              37,458   98.9565%
Bay Area sealed-test coverage              99.9034%

Parkfield selected                23,702
Parkfield matched                 21,331   89.9966%
Parkfield both errors             21,330   89.9924%
Parkfield sealed-test coverage             99.7082%
```

Every train/calibration/test partition remains above the predeclared material coverage floor of 80%.

## Important limitation

ComCat's `horizontalError` and `depthError` are not a full covariance matrix. They are conservative scalar projections of the location-error ellipsoid. v0.8.2 therefore authorizes construction and calibration of a conservative fault-assignment perturbation operator, **not** a claim that full event covariance has been recovered.

## Next gate

```text
FULL_FAULT_NETWORK_PARENT_GRAPH_AND_LOCATION_PERTURBATION_OPERATOR_LOCK
```

The full network-distance graph, ETAS/Hawkes parent candidate machinery and the conservative mapping from ComCat error scalars to fault-assignment perturbations must be frozen and qualified before the sealed test can be used.

Detailed identities and distributions are in `REMOTE_RESULT_INDEX.json`.
