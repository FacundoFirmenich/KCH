---
name: kch-data-persistence
description: Preserve and structure chats, memories, files, clipboard items, post-its, audio transcripts and datasets with bidirectional traceability. Use for KwanData, KwanDocs, session continuity, archives, token-budget handoffs or persistent working memory.
---

# KCH Data Persistence

## Layered record

Maintain linked layers rather than replacing one with another:

1. immutable raw source: chats, files, audio, images and exact inputs;
2. normalized universal representations such as TXT plus format-specific bytes;
3. structured entities, tables, graphs, tags and classifications;
4. working views, folders, ranked boxes, conceptual maps and user groupings;
5. memory projections optimized for future tasks;
6. manifests, hashes, versions and recovery instructions.

## Persistent-memory governance

- Treat Codex memory, rollout summaries and task history as native continuity surfaces.
- Preserve their source URI, generation time, scope and possible staleness.
- When memory conflicts with a native chat or original artifact, return to the primary source and retain the contradiction.
- Never update user-level persistent memory without explicit authority.
- A session handoff must record its exact unread boundary; a summary is not a full-conversation replica.

## Durability

Autosave every editable box through an append-safe or transactional path. Use reconstructible event graphs for normal work and offer full checkpoints with an explicit storage warning. Never delete the last recoverable version.

## Budget-aware rollover

Track available token, money or account percentage only from observable host data or explicit user input. Use thresholds to recommend or trigger governed persistence and task rollover; never invent quota values.
