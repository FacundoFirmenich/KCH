# KCH native policy inside DeepSeek Harness

This is an executable Cordis plugin for DeepSeek Harness, not a prompt recipe.
It runs the unmodified KCH r33 native hook against an explicitly selected native
SQLite state. The host's final monotonic tool guard enforces the resulting
decision; the final immutable result is written back to the KCH hash-chain ledger.

## Verified source boundary

- DeepSeek Harness: `5badb15009ae1756c3afe0ae0cef1faafc290ccc`,
  `0.2.1-alpha.1`, MIT, developer preview. Compatibility with a different revision
  is not established.
- KCH: repository base `714892929ff7d840746ae568d7217af588159053`,
  `construct_successors/KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2/vendor/kch-native-r33-0.11.33`.
  `native_bridge.py` verifies exact SHA-256 hashes of `kch_native_hook.py` and
  `kch_native_state.py` on every invocation. It does not modify either source.
- Tested surface: local filesystem composition, real upstream `AgentLoop`,
  `ToolRuntime`, `LocalFileSystem`, and `dsh-tool-fs`. No model provider, paid API,
  replayed assistant answer, or substituted DSH runtime was used.

## What it enforces

1. The calling Agent must be the exact object in the host's live agent registry.
   Its workspace must match the configured absolute workspace. The KCH session
   identity is the host-configured namespace plus that Agent's id. Arguments
   supplied by the model cannot select another actor or session.
2. `tools/pre-execute` sends the exact mapped arguments to KCH `PreToolUse`.
   The response is retained against DSH's registry-owned execution token.
3. `ctx.tools.guard()` runs after every extensible pre-execute listener. Missing,
   failed, skipped or denied admission stays denied even if another pre-execute
   listener returns `allow`.
4. `tools/result` writes the final immutable outcome synchronously to the actual
   KCH ledger as `DSHToolResult`, including the original tool, arguments, host
   session, attempt UUID, admission and result. Failure to persist latches a
   failure and blocks following calls. A failed receipt cannot undo an effect
   that has already completed.
5. Plugin activation requires native locks already enabled and a valid existing
   ledger chain. It neither enables locks nor issues authorizations. Native
   single-use authorization consumption remains in KCH.

## Explicit mapping

| DSH tool | KCH name | Boundary |
|---|---|---|
| `read` | `read_file` | Read semantics; native mutation locks do not block reads. |
| `read_image` | `view_image` | Mapping implemented; image-provider execution not tested here. |
| `write` | `write` | Native lock matching on exact `file_path`; tested on real files. |
| `edit` | `edit` | Exact edit arguments and canonical path; tested including a symlink alias. |
| `bash` | `exec_command` | Requires an enabled exact `tool:exec_command` lock, because static path extraction cannot bound arbitrary shell effects. Shell-provider execution not tested here. |
| Any other tool or alias | None | Denied until its actual effect contract is mapped and tested. |

The plugin restricts writes to its configured workspace and protects its native
source, data directory and own plugin directory. It does not invent a read-only
classification from tool-name prefixes. An alias of the actual upstream write
tool with a read-like name is denied.

## Use

Python 3 and the tested DSH runtime must be present. Select an existing KCH native
state through the native owner's setup/admin workflow first. Run
`python3 prepare_patch.py --help` for the required paths and namespace. The command
creates a new exact JSON/YAML patch; it refuses to replace a file or silently
enable native locks.

Mount that generated file with the supported DSH launcher:
`dsh --profile sdk --patch /absolute/path/to/generated.patch.json`.
For Python SDK callers, pass the same absolute path through `patches=(path,)`
and select an explicit `dsh_home`. The profile's agent workspace must equal the
workspace used when generating the patch. A full SDK/profile launch and a live
model turn have not been established by the component integration tests.

## Reproduce the integration test

Set `DSH_SOURCE` to the pinned upstream checkout with its locked dependencies
installed. From that checkout, run its `pnpm exec vitest run --config` with the
absolute path of this plugin's `tests/vitest.config.mjs`. The config resolves
the upstream source graph; it does not replace upstream classes. Add Vitest's
JSON reporter/output arguments to retain the complete result.

The tests create temporary local files and a fresh KCH database. They cover a
protected read, denied overwrite/edit, actual permitted file creation, exact
ledger receipts/hash verification, policy ordering/short-circuiting, symlink
identity, forged actor identity, missing actor/workspace, an unmapped alias,
disabled locks and protected control paths. They grant no authorization and
make no model-quality or scientific-improvement measurement.

## Remaining boundaries

- This is a local tool-effect adapter, not the completed KCH agent federation,
  Telegram migration, memory integration or a finished user-facing platform.
- DSH plugins and the Python executable are trusted same-user process code.
  A plugin able to write files directly or unload policy is outside this tool
  boundary. Keep DSH sandbox/OS confinement; this plugin is not a replacement.
- A call admitted before a concurrent policy change is not atomically coupled to
  the filesystem effect. Native authorization consumption is atomic in SQLite;
  the complete policy-to-effect transaction is not a cross-process transaction.
- Paths are canonicalized before dispatch, but hostile filesystem replacement
  between checking and use requires filesystem/sandbox enforcement.
- Removing the plugin removes its Cordis effects. A deployment must own profile
  composition; this code does not claim persistence against an administrator.
- The bridge runs a bounded Python process for admission and another for final
  receipt. It favors explicit evidence over latency; no throughput claim is made.
- DSH tool/agent APIs are pre-stable. The allowlist deliberately blocks unmapped
  scheduler, browser, subagent, MCP and PTC tools; integrating those requires
  their effect and authority contracts, not just adding their names.

## Reuse by the KCH composed runtime

`native_bridge.py` accepts one JSON object on stdin and returns one JSON object
on stdout. Required top-level fields are `nativeRoot`, `dataDir` and `action`.
`host` is the closed enum `deepseek | kch-composed`, defaulting to `deepseek`;
the host selects it from trusted configuration, never from model tool arguments.

- `action: probe` returns `locksEnabled`, `chainValid`, `events` and
  `exactToolLocks`. No enablement or authorization is performed.
- `action: pre` takes `payload` with native `PreToolUse`, nonempty host-bound
  `session_id`, `tool_use_id`, `tool_name`, absolute `cwd`, and exact `tool_input`.
  It returns `allowed`, `reason` and `nativeOutput`. For host `kch-composed`,
  a `write` additionally requires an enabled exact `tool:write` lock.
- `action: receipt` logs the exact payload as `DSHToolResult` or
  `KCHComposedToolResult`, according to the host enum. It returns `recorded` and
  `eventHash` after the native commit.

The caller must bind session identity and effect arguments to its actual live
execution. The helper is a local trusted transport, not an identity server or
an authorization grant endpoint. `write` resource matching and single-use
authorization consumption remain the pinned native KCH implementation.
