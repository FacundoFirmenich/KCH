# Cross-Store Continuity for Genealogical Information Systems

## Research question
Can a release be persisted across heterogeneous stores while preserving a distinction between byte identity, lineage, freshness and promotion authority?

## Result
A conservative three-surface rule was implemented. Exact agreement across Library, Google Drive and GitHub is required for strong promotion. A verified conflicting copy blocks promotion even if the other two agree. Two matching verified copies provide a recovery hint only.

## Relation to CFL/KCH/SCA
The experiment turns persistence into a governed transformation. The artifact can recur on a new surface without becoming a new semantic release; conversely, a surface can contain authentic bytes that are no longer current. Genealogy travels with the release rather than being inferred from filenames.

## Limits
The design does not create administrative independence among providers, does not prove scientific truth, and does not solve whole-account rollback.
