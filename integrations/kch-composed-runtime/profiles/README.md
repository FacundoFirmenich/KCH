# Alternative host profiles

`generate.py` produces two additive configuration fragments for the destination checkout supplied by the operator. Generated files contain resolved absolute paths and the actual Python interpreter running the generator, with no credentials, fabricated model identifiers or variable-expansion assumptions. Generation **never starts a host or modifies its configuration**. Their transport/configuration shape is supported by the primary sources below; a saved configuration is not a successful host integration.

| File | Consumer | Exact insertion boundary |
| --- | --- | --- |
| `qwenpaw.local.json` | QwenPaw Console, Agent → MCP → Create/import | Supported `mcpServers` import format; current upstream persists driver cards and migrates legacy `mcp.clients` |
| `openclaw.local.json` | OpenClaw configuration | Merge the single `mcp.servers.kch_composed` entry into existing configuration |

Do not replace the host's complete configuration with either fragment. Do not replace the existing KCH SuperMCP configuration, Jarvis transport, scheduler, voice services, KwanDocs/KwanBlocks stores or installed skills. The server name is intentionally separate. Existing native tool permissions remain in force.

## Generate for the destination

The generator uses only Python's standard library. Run it with the Python interpreter that will run the composed runtime. From the repository root, `python integrations/kch-composed-runtime/profiles/generate.py --help` prints the interface.

| Required argument | Value and validation |
| --- | --- |
| `--repository` | Existing KCH checkout containing `integrations/kch-composed-runtime/src/kch_composed/__main__.py` |
| `--state` | Destination state directory; the generator records its resolved path but does not create or initialize it |
| `--workspace` | Existing working-space directory bound to the runtime |
| `--principal` | Explicit nonempty local principal; never inferred from a model response |
| `--session-prefix` | Explicit binding identifier; sessions become `qwenpaw-` and `openclaw-` followed by this value |
| `--output` | Directory in which to write the two JSON fragments; existing generated profiles are not overwritten |
| `--host` (optional) | `qwenpaw`, `openclaw` or `both` (default); generate either composition independently |

The generator prints a JSON receipt listing generated files and explicitly reporting `host_activated: false` and `host_configuration_modified: false`. Relative input paths resolve against the invoking process's working directory. The runtime `cwd` derives from the specified repository, so copying the generator alone does not substitute for a real checkout. Generated `*.local.json` files are deployment-specific and should not be committed as portable source.

Run `python -m unittest discover -s integrations/kch-composed-runtime/profiles -p 'test_*.py' -v` from the repository root to check output syntax, selection, distinct session bindings, real entry-point paths, diagnostic admission, absence of host/state activation, and overwrite rejection. These generator checks do not start either host.

## Local profile diagnostic

`doctor.py --profile /absolute/path/to/qwenpaw.local.json --read integrations/kch-composed-runtime/README.md` starts the generated KCH subprocess with the official MCP Python SDK, negotiates the protocol, discovers the actual read-only catalog, compares the requested file's first 65,536 bytes with the real workspace file, and closes the subprocess. Use the OpenClaw fragment to probe that separate session. Install the optional `mcp>=1.28,<2` dependency in the interpreter running the diagnostic; the generated command still selects the actual KCH interpreter.

The report is JSON with `PASS`, `FAIL`, or `BLOCKED`; failures exit nonzero. This diagnostic accepts the unmodified, read-only generated shape, rejects extra environment fields instead of ignoring them, makes no inference requests, and never imports either host configuration. Starting the KCH subprocess initializes its explicitly selected local state. It does not activate the user host, assert authenticated user identity, or establish control over the host's unrelated tools.

## Scope and deployment boundary

The profiles run the Python module from this package's `src` directory in the selected repository. Repository, state, working space, principal and session identifier come from explicit generator arguments. The principal is a **local namespace label**, not authenticated proof of the human user. Each profile binds a distinct fixed session. Neither profile passes `--enable-write`; the runtime's default tool set applies.

This fixed binding is suitable for one explicitly isolated host agent/session during integration acceptance. It is not a multi-user gateway configuration. A shared host with several users or conversations needs a trusted adapter that supplies the actual principal, workspace and session, or a separate server instance per isolated binding. Passing caller-provided labels is not authentication. Switching host profiles does not silently transfer grants, unfinished effects or model-native sessions.

MCP discovery exposes the tools that this Python server actually returns. It does not capture every host event, enforce KCH over unrelated native host tools, unify all pre-existing KCH tools, activate Telegram, or install the separate DeepSeek guard. The DeepSeek plugin under `../plugins/deepseek` is a different integration boundary.

## Acceptance on a real host

1. Generate the profiles on the destination with its actual interpreter, checkout, state, workspace and scope arguments. Inspect the resulting command, arguments and working directory before import; regenerate when the deployment moves.
2. Confirm `python -m kch_composed` is the implementation in this package and that its CLI accepts the argument list in the selected fragment. Run the local package tests and its protocol smoke check before host import; consult the delivery verification report for the results actually executed.
3. Import/merge only the new entry. For QwenPaw, refresh its MCP page and verify the entry persists; inspect the returned tools. For OpenClaw, run `openclaw mcp doctor kch_composed --probe` and inspect the returned catalog. A successful import alone does not close this check.
4. Perform one permitted read and one deliberately rejected operation in the isolated working space, then confirm the real host session, KCH receipt and final tool outcome agree. Stop/restart the host and verify the scope and saved state remain the same. The original client-component checks below are now closed; complete host UI, gateway, permissions, and model invocation checks on the destination remain separate.
5. Preserve the existing KCH services and credentials. Enable only one owner of any external-effect task; running both interfaces must not duplicate Telegram deliveries or scheduled work.

## Primary configuration sources

- [QwenPaw official MCP guide](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/mcp.zh.md): three supported import formats; `command`, `args`, `env`, `cwd`, transport and per-agent configuration. Retrieved 2026-10-08.
- [QwenPaw current configuration code](https://github.com/agentscope-ai/QwenPaw/blob/main/src/qwenpaw/config/config.py): `MCPClientConfig` and `MCPConfig`; source inspected 2026-10-08. Current code recognizes `stdio`, `streamable_http` and `sse` and validates nonempty commands for stdio.
- [OpenClaw native MCP client guide](https://docs.openclaw.ai/tools/mcp): `mcp.servers`, stdio command/args/cwd, discovery and `doctor --probe`. Retrieved 2026-10-08.
- [OpenClaw MCP CLI](https://docs.openclaw.ai/cli/mcp): distinguishes outbound client registry from `openclaw mcp serve`, which exposes OpenClaw in the reverse direction. The fragments use the outbound client registry, not the reverse bridge or the separate mcporter registry.

## Executed original-client acceptance, 2026-10-09

| Host source pin | Executed boundary | Result |
| --- | --- | --- |
| QwenPaw `7147731d582fdd106af6ca7e3a3a5dc650183755` (`2.2.2b4`) | Original `drivers/handlers/mcp_stateful_client.py:StdIOStatefulClient`, MCP Python `1.30.0`, real KCH subprocess | 8 checks passed, 5 durable calls |
| OpenClaw `c9a0c00b8691bda5bd7a38ee494b5edd8ecb9254` (`2026.9.9` package version) | Original `createMcpStdioClient`, original server schema and launch resolver, MCP SDK `1.31.0`, compiled original Linux process owner, real KCH subprocess | 9 checks passed, 5 durable calls |

Both clients discovered KCH tools, read an actual repository file byte-for-byte, received a denied out-of-workspace read and a disabled write without producing a file, archived the actual file, closed, restarted a fresh subprocess in the same session, recovered the exact original bytes, and closed again. The KCH journal verified after those calls. OpenClaw additionally parsed the profile with its original `McpServerSchema` and resolver. No inference, model output, native host events or chat identity was simulated.

The OpenClaw Linux process owner initially refused source-loader execution. Acceptance compiled the unchanged upstream owner and used upstream's `registerSealedRuntimeProcessEntrypoint` registration API; its ownership and descendant-cleanup checks were retained. These are component-level integrations with genuine upstream client code, not activation of the full host apps. QwenPaw's package bootstrap is intentionally not loaded, because it loads persisted user environment; its client module and relative dependency sources are unchanged.

Reproducible acceptance scripts, dependency locks, source pins and executed receipts live in `../tests/host_acceptance/`. Upstream source trees and binaries are not vendored. Rolling documentation and a passing pinned component test do not certify a different installed host release.
