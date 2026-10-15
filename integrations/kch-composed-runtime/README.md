# KCH composed runtime 0.2.0

An additive execution layer for KCH: durable sessions, an explicit model/tool cycle,
recoverable memory, SCO execution and typed decision sensors. The existing full KCH
distribution remains the owning platform. This package does not replace SuperMCP,
Jarvis/Telegram, CSI, KwanDocs, KwanBlocks, CONSTRUCT or their native implementations.

This increment is implemented against KCH main `714892929ff7d840746ae568d7217af588159053`,
SCO release stage v0.1.1 and Native r33 0.11.33. It requires Python 3.11+ and Linux/POSIX
(`flock`, directory `fsync`); there is no claim of Windows portability.

## Connected components

```mermaid
flowchart TD
    H["Host identity and selected platform"] --> S["SCO roles and dependent orders"]
    H --> M["Additive MCP stdio"]
    S --> B["Explicit model handler"]
    B --> C["KCH execution cycle"]
    M --> T["Bound tool service"]
    C --> J["Durable session journal"]
    C --> T
    T --> V["Scoped original memory and folds"]
    T --> O["Jev-family typed observations"]
    T --> G["Native KCH exact write gate"]
    T --> F["Allowlisted original SuperMCP"]
    J --> P["Evidence-only portable checkpoint"]
    D["DeepSeek native plugin"] --> G
    G --> R["Effect and native receipt"]
```

- `runtime.py` connects preserved provider messages to real tools. A response is
  persisted before tool execution. The selected endpoint/model/options bind to the
  session. There is no implicit provider switch, retry, model or key.
- `journal.py` retains exact JSON messages and call receipts with a scoped hash chain
  and checked projections. Reusing a call ID with different arguments fails. A call
  left STARTED cannot be repeated automatically. This is conservative recovery, not
  a promise of universal exactly-once external effects.
- `checkpoint.py` exports only the bound session and scoped original memory. Import
  archives evidence and optionally materializes selected sources; it never activates
  source messages, grants, model bindings or pending effects. A sealed outbox reconciles
  publication across memory and journal databases. See [checkpoints](docs/CHECKPOINTS.md).
- `federation.py` launches the original SuperMCP and validates its locked governance.
  Discovery preserves the canonical catalog; an explicit host allowlist, canonical
  schemas, fixed authority arguments and trusted authorization constrain execution.
  Four read-only native tools have executed against the 294-tool catalog. Discovery
  is not verification of every tool. See [federation](docs/FEDERATION.md).
- `memory.py` retains original bytes, revision/provenance seals, contiguous and nested
  fold manifests, exact unfolding, scoped search, budgeted views and transitive
  invalidation after correction. Folding is an index operation; it is not a learned
  semantic summarizer and does not silently compress provider conversation history.
- `coordinator.py` extends the existing SCO ledger with bounded parallel execution,
  dependency scheduling, reservations and recoverable receipt publication.
  `bindings.make_model_handler` connects its orders to the KCH model cycle. Trusted
  adapters are required; arbitrary Python handlers are not sandboxed.
- `sensors.py` connects host-registered System One callables and historical RDSS
  receipts. Choice/Score/Noul remain observations with authority NONE. See
  [Jev integration](docs/JEV.md).
- `plugins/deepseek` invokes the existing KCH hook at DeepSeek's real guard boundary,
  with source pins and final native receipts. The SDK launcher now requires the KCH
  plugin and fails startup when native locks are disabled. See its own README.
- `mcp.py` exposes only connected tools over newline-delimited stdio JSON-RPC. It is
  an additive server for OpenClaw, QwenPaw, Codex, Cline or another conforming client;
  original OpenClaw/QwenPaw client components have passed real subprocess acceptance.
  Complete host activation remains separate. See [profiles](profiles/README.md).

## Run locally

The core uses the standard library. To execute every federation test, install the
optional original-runtime dependencies from this directory first:

```sh
export PYTHONPATH="$PWD/src"
python -m pip install '.[federation]'
python -m unittest discover -s tests -v
python -m kch_composed --help
```

Every CLI command requires explicit `--repository`, `--workspace`, `--state` (a
directory), `--principal` and `--session`. These are trusted local host settings;
`principal` is not a login or remote authentication mechanism. `inspect` reports
the configured tools, call states and derived native authorization session ID.
`invoke --call-id ID --tool NAME --arguments-file FILE` invokes an actual tool.
`recover-tools` completes persisted calls without requesting a model. `cancel` and
`resume` control the bound session. Cancellation is checked before each new operation
and immediately before a native-authorized write; it cannot undo an effect underway.

`run --endpoint URL --model ID --prompt-file FILE` makes real model requests.
For remote HTTPS, supply `--api-key-env ENV_NAME`; the key remains in the request header.
Provider options are explicit through `--options-file FILE`. `--retry-model`
acknowledges uncertain model delivery, never uncertain tool execution. Native provider
reasoning fields stay with that session. See [transport contract](docs/MODEL_TRANSPORT.md).

Default tools read workspace files and maintain session-local memory. `--enable-write`
adds exclusive **new-file** creation only. It also requires `--native-data`, existing
native locks enabled, an exact `tool:write` lock, and an exact consumable KCH grant.
The adapter never creates grants or enables locks. A denied proposal is a terminal
attempt: after an actual user grant, submit a **new call ID** with the same authorized
arguments. The native session is a hash of principal/workspace/session, exposed by
`inspect`, not the bare CLI session name. Overwriting, shell execution and remote
delivery are not exposed by this package's own loop.

`checkpoint-export --output FILE` creates a scoped portable evidence archive;
`checkpoint-import --input FILE --source-id ID` imports explicitly selected sources.
The optional global `--federation-config FILE` connects a host-owned SuperMCP allowlist.
`federation-discover` reports its actual catalog and exposed subset. Mutation cannot
be enabled by relabeling a tool as read-only; the CLI supplies no trusted mutation
authorizer. An embedding host must provide one at the native execution boundary.

For SCO model handlers, order authority must include `MODEL_INFERENCE` and
`tool:<name>` for each exposed tool. Backend factory, principal and tool selection are
host-bound. A model's declaration of completion is retained as such; it does not prove
scientific correctness or satisfy an independent reviewer gate.

## Evidence and boundaries

Run the Python suite above for local behavior. The tests use real repository files,
actual SQLite state and explicit contract/adversarial fixtures. Provider transport
tests use loopback HTTP; sensor tests use labeled primary-document examples. These
are not model benchmarks or simulated claims of live inference. DeepSeek tests use
the original upstream AgentLoop and filesystem tools; their pinned checkout and
commands are in `plugins/deepseek/README.md`.

The own generative cycle passed one preregistered local case with official Qwen3-0.6B
Q8_0 on llama.cpp: actual model-generated read, ingest and recall calls, exact source
bytes, and reopening a completed session without another request. This is bounded
integration evidence, not a quality benchmark. See [model acceptance](docs/LIVE_MODEL_ACCEPTANCE.md).
The SCO model-handler path still needs its own real-model case. Original OpenClaw and
QwenPaw clients passed discovery, read/denial and memory restart checks; full apps are
not activated on user hosts. MCP exposure does not intercept unrelated native tools.

Local state can contain exact source material and provider-native reasoning. Place
it outside source control and bind access to the intended OS user. Hashes detect
accidental corruption and inconsistent projections, not a malicious owner rewriting
the whole database and its seals. Shared-machine authentication, hardened sandboxes,
semantic memory evaluation, automatic compaction policy, cloud deployment and audited
mutation coverage across the full KCH catalog remain separate integration work. Mechanisms and source
attribution are listed in [INTEGRATION_MAP.md](INTEGRATION_MAP.md).
