# CSC–KCH v11 external conformance

This package executes three independent checks:

1. OPA/Rego syntax and semantic conformance over 3,456 portable support vectors.
2. Cedar syntax and semantic conformance over the same vectors.
3. TLC model checking of the PCGT state machine and safety invariants.

Portable policies return support only. They never mint authority, leases or effects.
The GitHub Action pins tool versions and verifies upstream checksums where available.
