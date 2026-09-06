# KCH Operational Supervision 0.1.0

Two bounded tools for KCH: read-only Linux VPS resource observation and evidence-bound agent supervision. This additive package does not replace KCH or claim a fully implemented marketplace, a continuously running global supervisor, or useful-work validation from CPU counters.

## VPS observation

`scripts/kch_ops.py vps-ssh` accepts one JSON object on stdin with `profile` and optional `measurement`. The profile requires `host`, `user`, `identity_file`, `authorization_ref`, and future timezone-aware `expires_at_utc`; optional `port` defaults to 22 and `timeout_seconds` to 85 (5–85 seconds, below the adapter deadline). Existing OpenSSH host keys must match. The package never creates credentials or disables host-key verification.

`measurement` accepts `interval_seconds` (0.25–10), optional nonempty `allowed_uids`, and an explicit `services` list (at most 20). Default collection is host-aggregate only: CPU consumed, I/O wait, CPU steal, memory, swap, PSI, root disk and inodes. Individual processes are not inspected without the UID allowlist. A UID can span unrelated projects: the operator must establish project scope before supplying it. Never use a root UID allowlist to circumvent a shared-host exclusion.

For admitted processes, PID plus start counter protects against PID reuse. Sleeping is not treated as useless, parent PID 1 is not treated as proof of abandonment, and CPU activity is not proof of application progress. Application-health checks and project-specific progress receipts are separate requirements. No process arguments, environments, credentials, kill signals, restarts or remote installation are collected/performed.

One bounded SSH invocation transports this module on stdin. On timeout the local SSH client is terminated and the failed receipt is retained; remote process termination is not claimed. Connection failure, invalid output and measured observations have distinct gates. An authorization reference is provenance, not a substitute for host or user authorization.

## Agent supervision and Construct

The same CLI provides `status`, `observe`, `dispatch-preflight`, `review`, and `preregister`. State is an SQLite event ledger at `.kch/operational-supervision/agents.sqlite3`, relative to the operating workspace unless `--database` is supplied. Read-only status does not create a database. Writes preserve an event hash chain, reject conflicting replay, and retain adverse evidence. Hashes establish integrity checks, not the authenticity of a supplied source.

Native observations must include `event_id`, `source_ref`, `host`, `scope`, timezone-aware `observed_at`, and an `agents` list. Each agent needs `agent_id` and `status`; model and governor role must come from admitted native context. Missing or stale observations do not prove a dead or stalled agent. Costs and useful progress remain unavailable unless supported by actual receipts.

Auxiliary worker plans require explicit Luna or Terra, a bounded turn budget and role, obligation, topology, source and stop-condition references. Replicated worker lanes use Luna. User-owned tasks are not subagents and retain the user's model and reasoning choices. A passing dispatch plan does not dispatch a worker.

Reviews bind a separate attributed reviewer to actual artifact hashes within admitted roots. A successful review plus a complete `GENERALIZABLE` and `TOPIC_SPECIFIC` role specification can preregister a candidate under the supplied authorization. Failed and inconclusive reviews remain visible. The two branches retain reciprocal hashes. Preregistration is not proven generalizability, installation, publication or automatic promotion. No valuable archetype is invented from an empty registry.

## Host integration

Codex discovers the companion hooks under `hooks/`. `PreToolUse` guards auxiliary `spawn_agent`; it does not constrain user-owned `create_thread`. `PostToolUse` ingests the supported `list_agents` native response only when session, directory and call identifiers are present. Unsupported payloads are explicitly unobserved. Prompt routing points to the local CLI. There are no scheduled model calls, polling loops, or chat-report loops in this package. Native hook event coverage must be verified in the actual installed host.

The Cline adapter in `plugin/index.js` declares `kch_vps_diagnose` and `kch_agents_observe`. It invokes the same Python implementation without a shell, with output and time bounds. It does not claim native Cline multiagent dispatch. `KCH_OPS_PYTHON` can select an existing Python executable. The adapter contract test alone is not evidence that an interactive Cline session has loaded the plugin.

## Validation and custody

Run `python -B -m unittest discover -s tests -v` and `node --test tests/test_bridge.mjs` from this package. Unit fixtures and mocked failure paths are explicitly tests, not real VPS or agent observations. Validate `.codex-plugin/plugin.json` with the installed Codex plugin validator before installation. Preserve host-loading and live observation receipts separately from this public package.

Do not commit databases, native chats, SSH profiles, keys, tokens, private review artifacts or operational reports. Reverting this additive package does not require deleting evidence or replacing the KCH predecessor. Installation, public Git publication, live host loading and effective operational coverage are separate states and must be reported separately.
