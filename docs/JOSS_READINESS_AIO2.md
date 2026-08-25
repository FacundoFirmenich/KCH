# JOSS readiness programme for KCH AIO2

AIO2 is structured so the repository can mature toward a Journal of Open Source Software submission without rebuilding its software architecture. It is not yet described as JOSS-ready.

## Already in place

- A versioned, recoverable source distribution.
- Separate complete release assets for Codex and Cline.
- Reproducible build and host-bundle builders.
- Functional host gates, adverse-result preservation, rollback and explicit claim boundaries.
- Citation metadata, contribution guidance, changelog and automated source checks.
- Public repository publication explicitly authorized for AIO2.
- Complete binaries published as release assets; reproducible source accepts an external dependency wheelhouse to avoid bloating Git history.
- A documented separation between capability, permission, authority, execution and training.

## Blocking decisions and evidence

1. Select and publish an OSI-approved license compatible with the intended LIBRESOURCE and commercial model. The repository currently has no root software license; inventing one would be legally and constitutionally invalid.
2. Confirm author names, affiliations, ORCIDs and contribution roles.
3. Add independent-user installation reports on clean Codex and Cline hosts.
4. Add longitudinal task benchmarks that evaluate utility and failure reduction, not only packaging and conformance.
5. Add public API documentation and a stable semantic-versioning policy.
6. Freeze the exact scientific scope and write `paper.md` against the validated software rather than against prospective claims.
7. Archive a citable release with a DOI.

A paper skeleton is deliberately not populated with unknown affiliations, citations or outcomes. `paper/README.md` records the activation gate.