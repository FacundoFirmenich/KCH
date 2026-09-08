---
name: kch-kwandisk
description: Inspect, classify, synchronize and safely clean local and cloud storage under KCH custody rules, including ad hoc task folders, Documents/Codex, agent state roots and tmp/temp.
---

# KCH KwanDisk

Use the embedded kwandisk runtime. Separate observation, recommendation, authorization, execution and verified recovery.

## Canonical storage chain

1. Google Drive is the default durable custody target.
2. GitHub is the second replica for every compatible file within provider limits, after secret scanning.
3. Local disk or VPS storage is allowed only when the user explicitly requests it or it is indispensable for active execution.
4. VPS is not an automatic backup destination and local is not the canonical archive.

## General jurisdictions

KwanDisk must discover and classify, without creating missing roots:

- explicit ad hoc task folders;
- the user Documents/Codex tree;
- declared agent roots, including .codex and .agents;
- TEMP, TMP, TMPDIR, the platform temp directory and explicit tmp/temp roots.

## Procedure

1. Run discover-general and record exact roots and storage priority.
2. Run plan-general with active process/worktree paths and an age threshold.
3. Classify known derived caches as REGENERABLE, known temporary suffixes as TRANSIENT, and explicit Drive plus GitHub plus recovery receipts as REPLICATED_CUSTODY.
4. Treat unknown, active, protected, dirty, sensitive, inaccessible or changed paths as blocked.
5. Never infer that an old temp file, generated image, session database, log, task folder or agent state is disposable.
6. execute-general requires actor USER, a non-empty exact authorization ID, and the exact plan SHA-256. It revalidates every target before removal and is idempotent for already absent paths.
7. After execution report exact bytes freed, remaining disk pressure, custody boundary and recovery path.

## Protected state

Do not automatically clean AGENTS.md, auth/config files, sessions, archives, memories, skills, plugins, rules, automations, attachments, Git metadata, live SQLite databases or thread locks. Do not clean a dirty worktree, active process output, scientific evidence or the sole verified copy.

Automatic deletion remains false. Discovery and planning may be proactive; execution never is.
