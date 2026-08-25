---
name: kch-constitutional-locks
description: Protect selected files, paths or tool operations against accidental agent mutation with exact one-use user authorization. Use when the user requests lock keys, inviolable resources, change proposals, or guarded CONSTRUCT work.
---

# KCH Constitutional Locks

Locks are optional and disabled by default. They are preventive interposition, not a general permission system.

## Contract

1. Define an `EXACT`, `PREFIX` or `GLOB` resource pattern through the trusted interactive admin surface.
2. When a matching PreToolUse event occurs, block before the effect.
3. Materialize a proposal bound to session, tool name, exact canonical arguments and their SHA-256.
4. The agent supplies reason, impact and recovery. This does not authorize the change.
5. The user types the exact challenge in a local interactive terminal.
6. Permit only the exact authorized attempt; consume authorization atomically before execution.
7. Any changed argument, tool, session or second attempt blocks again.

## Non-equivalences

RUN, CONSTRUCT, tool approval, session consent, general permission and automation never unlock a constitutional key. Do not offer “always this session” for locked mutations.

## Limit

The guarantee covers only tool calls exposed to the compatible PreToolUse hook. Detect external writes as drift when a baseline exists; do not claim they were prevented.
