# KCH Helicoidal Program v1.2.0 — Theory and Direct-Field MHD

v1.2 makes the separation between the abstract lift framework and domain-specific helicity explicit.

## Core theory

The formal claim hierarchy is:

```text
R0 projected recurrence
R1 nontrivial lifted return
R2 signed/chiral transport
R3 domain-defined physical helicity
```

No upward implication from R0 is authorized without extra assumptions. Seismic negative evidence is retained as a counterexample to overgeneralization, not as evidence against the abstract lift mathematics.

## Direct HMI vector-field observability

The 16-record TRAIN-only gate reconstructs the SHARP signed proxies from exact Br/Bt/Bp FITS using high-confidence masks, metric scale, parity control and propagated component uncertainties.

```text
Outcome
DIRECT_SIGNED_CURRENT_HELICITY_OBSERVABLE

MEANJZH sign agreement      1.000
MEANALP sign agreement      1.000
Spearman MEANJZH            1.000
Spearman MEANALP            1.000
median relative error Hc    4.49e-6
median relative error alpha 3.97e-6
informative-sign stability  1.000
parity control              PASS
```

This supports observability of the vertical photospheric current-helicity proxy. It does not establish full 3-D current helicity or coronal relative magnetic helicity.

## Hemispheric-sign replication

A second deterministic 32-region panel was locked before the direct FITS were acquired. The gate required at least 22/32 robust agreements, at least 9/16 in each hemisphere and one-sided exact binomial p<=0.05.

```text
Observed robust HSR agreements 15/32
North                          7/16
South                          8/16
p(one-sided)                   0.7016925521
MEANALP agreements             16/32

Outcome
HEMISPHERIC_SIGN_PREFERENCE_NOT_REPLICATED
```

The reconstruction gate passed again. Thus this is a negative for the population sign pattern in the locked panel, not a failure of vector-field observability.

## KwanBlocks

```text
graph
kbg:06b51c19e741ca0b74543f2a0076dd83b114178487954494ce6754dc2c6bf426

ledger head
1e906b77697554d31f02f4c37893e44e90ef0855e95674d932847f07118afda5

validation
244 / 244 PASS

validation ID
h12val:7afd2daf54677d7b073f3b9b2a79988e0f8f69f7df31ff859eed7967c177a99e
```

## Governance

```text
SEISMIC CATALOG LINE             CLOSED
CURRENT-HELICITY PROXY           DIRECTLY OBSERVABLE
HEMISPHERIC SIGN RULE            NOT REPLICATED IN LOCKED PANEL
FULL 3-D CURRENT HELICITY        NOT EVALUATED
CORONAL RELATIVE HELICITY        NOT EVALUATED
UNIVERSAL HELICOIDAL ONTOLOGY    NOT AUTHORIZED
POSTHOC RESCUE                   FORBIDDEN
PROMOTION                        BLOCKED
CANONICALIZATION                 BLOCKED
AUTHORITY                        NONE
```

The next legitimate gate must move to helicity injection/flux or coronal relative magnetic helicity with a new observation and gauge/boundary contract. Do not rescue the hemispheric rule by selecting another epoch after observing this result.
