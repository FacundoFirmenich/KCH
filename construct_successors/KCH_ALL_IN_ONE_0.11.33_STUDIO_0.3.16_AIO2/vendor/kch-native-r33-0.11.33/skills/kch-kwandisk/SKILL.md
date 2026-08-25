---
name: kch-kwandisk
description: Inspect, classify and optimize local and cloud storage under KCH custody and recovery rules. Use for disk pressure, duplicate or regenerable files, Drive/GitHub/local synchronization, download cleanup, archive migration, backup verification, or any proposal to free space without losing evidence.
---

# KCH KwanDisk

Use the embedded `kwandisk` runtime for inventory and planning. Separate observation,
recommendation, authorization, execution and verified recovery.

## Procedure

1. Define local volumes, cloud stores, repositories and excluded jurisdictions.
2. Inventory bytes, pressure, duplicates, regenerables, sensitive candidates, inaccessible paths,
   active worktrees and files still used by live processes.
3. Classify each candidate as canonical, replicated, backed-up, regenerable, sensitive, transient,
   inaccessible or unknown. Unknown never becomes deletable by inference.
4. Require remote identity, exact size and preferably cryptographic checksum before recommending
   removal of the final local copy. Disclose when a connector exposes metadata but no remote hash.
5. Produce a reversible action plan ordered by safety and recovered space. Keep deletion disabled
   until separately authorized for exact targets.
6. After any authorized action, verify source/destination state, manifests, hashes and recoverability.

Never automate deletion merely because storage is scarce. Do not clean a dirty worktree, active
scientific evidence, a live process output or the sole verified copy. Report useful space gained,
remaining pressure, custody boundary and next safe action.
