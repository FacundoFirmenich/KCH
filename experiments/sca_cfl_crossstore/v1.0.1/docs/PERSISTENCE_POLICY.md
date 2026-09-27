# Persistence policy

The release distinguishes: (1) content identity, (2) location/provider identity, (3) lineage, (4) observed freshness, and (5) authority to promote.

- Library: durable user Library copy of complete release bundle and persistence ledger.
- Google Drive: complete release bundle and persistence ledger.
- GitHub: source code, tests, documentation, release manifest and persistence ledger. Large binary/data snapshots remain in Library/Drive unless source-control inclusion is functionally justified.
- Any verified divergence is HOLD, not majority repair.
- Missing copies are HOLD_INCOMPLETE for strong promotion; matching 2/3 copies may guide recovery only.
- No storage provider is treated as a truth oracle for the scientific content.
