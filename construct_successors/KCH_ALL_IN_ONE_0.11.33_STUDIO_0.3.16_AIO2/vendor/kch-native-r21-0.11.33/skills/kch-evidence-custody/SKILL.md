---
name: kch-evidence-custody
description: Read sources completely, preserve provenance and adverse results, verify hashes and close evidence chains without overclaiming. Use for native chats, long files, handoffs, audits, archives, experiments and release gates.
---

# KCH Evidence Custody

## Full-read protocol

1. Preregister sources and their native order.
2. Read every byte or paginate every turn to EOF. Search snippets only locate material.
3. Record byte count, physical lines or turns, method, source identity, transport boundary and SHA-256 where applicable.
4. Re-read or independently verify the receipt before asserting completeness.
5. Preserve the original order unless a different order is explicitly governed.

## Evidence classes

Keep separate: original source, immutable raw replica, structured derivative, execution receipt, interpretation, hypothesis, user decision and claim. Memory summaries and handoffs navigate; they do not replace the native source when full reading is required.

## Adverse evidence

Retain failed gates, abstentions, contradictions, missing spans and `NOT_ESTIMABLE`. State exactly what they block and whether they are reparable. Never convert a loss or unavailable fold into a global claim.

## Custody

Do not delete local material until every required remote copy, manifest and hash has been independently verified. A sync icon or successful upload command alone is not byte-complete custody.
