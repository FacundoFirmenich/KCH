# Acceptance with original host clients

This is a pinned, executable integration check. It uses real KCH subprocesses, real repository files, the original QwenPaw stdio client and original OpenClaw strict stdio client. There are no fabricated model responses, synthetic performance data, replacement transports or simulated clients. It does not launch the full QwenPaw console, OpenClaw gateway, chat channels, or model inference.

## Reproduce

Run `python integrations/kch-composed-runtime/tests/host_acceptance/run_acceptance.py --work /tmp/kch-host-acceptance` from the KCH repository root. The work directory must be outside that repository. The runner downloads the pinned public upstream commits and locked dependencies, then writes command logs and JSON receipts there. `--host qwenpaw` or `--host openclaw` runs only the chosen composition. It supports an already prepared work directory when tracked upstream source is unchanged and its commit matches exactly; an existing unrelated checkout is rejected rather than modified.

The executed environment was Linux, Python 3.12 and Node 24.19.0. This is not Windows/macOS acceptance. Node, npm, git and Python with venv must be available. The acceptance suite is opt-in because it downloads upstream dependencies; ordinary KCH tests retain the lightweight standard-library path.

`requirements-qwenpaw.txt` records the actual installed Python dependency versions, including MCP 1.30.0. `node/package-lock.json` freezes the Node dependency graph; `npm ci --ignore-scripts` installs that graph. The direct OpenClaw dependencies use the versions required by its pinned `package.json`; esbuild 0.28.2 is the acceptance compiler. The runner never reads a model key or persisted host account.

## Boundaries and checks

| Component | What actually executes | Boundary that remains open |
| --- | --- | --- |
| QwenPaw | Unmodified `StdIOStatefulClient` and its relative upstream imports; official MCP Python SDK; original KCH module subprocess | Complete app bootstrap, Console import, driver policy prompts, channel identity and inference |
| OpenClaw | Original `McpServerSchema`, `resolveStdioMcpServerLaunchConfig`, `createMcpStdioClient`, lifecycle/transport/process-ownership modules; compiled original Linux process owner; original KCH subprocess | Complete native config load, gateway/session mapping, host tool policy and inference |
| KCH | Real tool discovery, workspace read, two denials, byte-preserving memory ingest, process restart and exact recovery; real durable journal verification | Cross-host effect ownership, authenticated remote principals and other KCH tool federations |

Both clients must pass all of: catalog discovery, exact source bytes, rejection of a read outside the workspace, rejection of an unavailable write without creating a file, ingestion of a real file, first client close, exact recall through a new client/process in the same bound session, and second close. OpenClaw adds validation with its original config schema and launch resolver. Each run checks five durable KCH tool calls and the journal chain after restart. Eight or nine checks is a contract-acceptance count, not a model or security score.

The QwenPaw component loader creates namespace-package search paths to its original source tree. It intentionally skips the application's `__init__`, which otherwise loads persisted environment values. No client behavior is reimplemented. The MCP Console still accepts `mcpServers`; current QwenPaw storage migrates legacy `mcp.clients` to driver cards. Acceptance here does not certify Console persistence.

OpenClaw's Linux process owner refuses source-loader execution. The runner compiles that unchanged original entry point and registers the resulting JavaScript with the original `registerSealedRuntimeProcessEntrypoint` API. The original admission, subreaper and descendant-cleanup checks remain enabled. `createMcpStdioClient` obtains cwd from its caller; acceptance applies the generated cwd before launching it. It supplies an empty environment to the KCH child. The source loader itself is used only by the parent test process.

## Source custody

| Source | Pin | Primary entry |
| --- | --- | --- |
| QwenPaw | `7147731d582fdd106af6ca7e3a3a5dc650183755` | [Original client](https://github.com/agentscope-ai/QwenPaw/blob/7147731d582fdd106af6ca7e3a3a5dc650183755/src/qwenpaw/drivers/handlers/mcp_stateful_client.py), [Console import](https://github.com/agentscope-ai/QwenPaw/blob/7147731d582fdd106af6ca7e3a3a5dc650183755/console/src/pages/Agent/MCP/index.tsx), [migration](https://github.com/agentscope-ai/QwenPaw/blob/7147731d582fdd106af6ca7e3a3a5dc650183755/src/qwenpaw/drivers/adapters/mcp_legacy_config.py) |
| OpenClaw | `c9a0c00b8691bda5bd7a38ee494b5edd8ecb9254` | [Original client](https://github.com/openclaw/openclaw/blob/c9a0c00b8691bda5bd7a38ee494b5edd8ecb9254/src/agents/mcp-stdio-client.ts), [schema](https://github.com/openclaw/openclaw/blob/c9a0c00b8691bda5bd7a38ee494b5edd8ecb9254/src/config/zod-schema.mcp-server.ts), [Linux ownership](https://github.com/openclaw/openclaw/blob/c9a0c00b8691bda5bd7a38ee494b5edd8ecb9254/src/process/supervisor/linux-child-subreaper.ts) |

`receipts/` contains the execution results obtained for these pins, with source hashes and actual file-range hashes. New runs produce their own receipts in the chosen work directory. A receipt proves the recorded component boundary at that source pin; it is not a claim that either complete host is active on the user's machines or that a later upstream release passes.
