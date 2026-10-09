# Verification of the composed runtime 0.2.0

Cutoff: 2026-10-09. These are distinct integration gates, not independent scientific
model experiments. The prior 0.1 record is retained below as historical evidence.

| Current executed gate | Result | Established boundary |
|---|---|---|
| Python suite, federation dependencies installed | 158/158, zero skipped | Actual tools, native authority, sessions, memory, recovery, checkpoint and federation contracts |
| Profiles and diagnostic admission | 6/6 | Independently selectable hosts, strict configuration and read-only launch admission |
| Original SuperMCP | 294 discovered; 4 read-only tools executed | Original handlers and locked governance: 23 nodes, 8 compiled artifacts |
| Original QwenPaw client | 8 checks, 5 durable calls | Actual read, escape/write denial, exact memory after subprocess restart |
| Original OpenClaw client/schema/resolver | 9 checks, 5 durable calls | Same gates plus original schema; compiled original process owner retains cleanup enforcement |
| Original DeepSeek SDK launcher | Positive and disabled-lock negative gates PASS | Mandatory KCH, handshake, read, denied overwrite and shutdown; 2 native receipts, 4 valid events |
| KCH in original DeepSeek tool pipeline | 10/10 rerun | Actual AgentLoop/FS admission, monotonic guard, identity and final receipts |
| Real local Qwen3-0.6B Q8_0 | PASS_BOUNDED_LOCAL_CASE | Model generated read_file, memory_ingest and memory_recall; exact source/read/recall bytes |
| Completed-session replay | PASS, zero steps | Same/new process, server stopped; no request or changed journal/calls |

The actual model case used official Qwen/Qwen3-0.6B-GGUF revision
`23749fefcc72300e3a2ad315e1317431b06b590a` and llama.cpp CPU b11514.
Two model responses and three tool calls completed in 59.08764981 seconds.
The then-current pyproject.toml snapshot was 444 bytes, SHA-256
`3666f1013177769cde668e3b731202b6a5d96f21df8590169788786135b5f080`.
Later dependency additions changed the file; adjudication uses that exact saved
source, not the final checkout. No API key or paid inference was used.

Source pins:
- QwenPaw: `7147731d582fdd106af6ca7e3a3a5dc650183755`.
- OpenClaw: `c9a0c00b8691bda5bd7a38ee494b5edd8ecb9254`.
- DeepSeek: `5badb15009ae1756c3afe0ae0cef1faafc290ccc`.

## Reproduce current gates

From this package:

```sh
python -m pip install '.[federation]'
PYTHONPATH=src python -m unittest discover -s tests -v
python -m unittest discover -s profiles -p 'test*.py' -v
```

The federation extra is required for zero skipped tests. The profile diagnostic can
use `pip install '.[host-probe]'`. Original upstream checkouts are not fake clients.
See `tests/host_acceptance/README.md`, `plugins/deepseek/README.md`,
`docs/FEDERATION.md`, `docs/CHECKPOINTS.md` and `docs/LIVE_MODEL_ACCEPTANCE.md`
for reproduction, pinned dependencies, receipts and exact limits.

## Corrections verified in 0.2

- Persist assistant messages and model receipt atomically; legacy recovery requires
  an exact prior-message hash and unambiguous persisted response.
- Reopen a completed session without requesting inference; stopped sessions reject
  new prompts. Check cancellation after tool/model return and close resources.
- Strictly pair provider tool calls and reject refusal/truncation while preserving
  native fields. Drain an entire oversized MCP frame before another request.
- Require KCH at DeepSeek SDK startup. Optional-plugin failure cannot silently
  leave the source launcher running without the guard.
- Reconstruct federation call projections from events, reject missing/altered rows
  and truncated ledger heads, and validate the complete cached receipt envelope.
- Seal the complete checkpoint import outbox receipt, check expected input,
  archive bytes, revisions/provenance/invalidations and exact journal equality.
  Unsealed prerelease outboxes fail closed without a migration that blesses them.
- Publish imports idempotently across the two databases, retain overlapping-source
  revision maps and synchronize the checkpoint parent directory before success.

Independent review reproduced missing federation projections and tampered import
receipts before correction. Current delivery includes the separate recheck receipt.
The 38 original DeepSeek upstream tests below were not rerun for 0.2; the 10 KCH
component tests were. Current CI belongs to the new PR head, not the prior run.

## Current remaining boundaries

Complete OpenClaw/QwenPaw UI, gateway, remote identity and user-host activation remain
unexecuted. DeepSeek source SDK launch passed; its published package, headless startup
and generative SDK turn remain separate gates. SCO real-model execution and a live
Jev-family backend need their own acceptance.

One local Qwen case is not a model-quality benchmark or proof of every interruption
scenario. Folding is reversible indexing, not learned semantic compression.
Checkpoint import is EVIDENCE_ONLY; it transfers no authority or active conversation.
Four executed tools do not accredit the other 290 tools or their mutating effects.
There is no remote authentication, hostile-plugin sandbox, global security ranking
or universal exactly-once guarantee. Private evidence remains outside public source.

## Historical 0.1 record — superseded where 0.2 closes a gate

Research cutoff: 2026-10-08. KCH base:
`714892929ff7d840746ae568d7217af588159053`.
DeepSeek Harness source pin:
`5badb15009ae1756c3afe0ae0cef1faafc290ccc` (`0.2.1-alpha.1`).

| Executed gate | Passed | What the result establishes |
|---|---:|---|
| Python suite | 104/104 | Actual local tools, scoped durable state, native authorization, parser/transport contracts, recovery and coordinator behavior |
| Portable profile generator | 3/3 | Concrete config shapes, existing interpreter/source paths, separate sessions, no host activation |
| KCH plugin in original DeepSeek tool pipeline | 10/10 | Actual AgentLoop/FS tools, native hook/database, admission, monotonic guard, identity and final receipts |
| Focused original DeepSeek suites | 38/38 | Upstream tool guard/scope behavior and compaction tool-call pairing at the pinned revision |

Python breakdown: bindings 1, coordinator 12, journal 13, MCP 3, memory 18,
model transport 16, runtime 12, sensors 13, workspace/native tools 16.
The 104-test suite finished with `OK`; the profile suite finished with `OK`.
Both DeepSeek JSON reporters recorded zero failed tests. Compile checks and
staged whitespace checks passed. These are different test populations and must
not be presented as 155 independent scientific model experiments.

## Reproduce

From `integrations/kch-composed-runtime`:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m unittest discover -s profiles -p 'test*.py' -v
```

DeepSeek reproduction requires its pinned upstream checkout and dependency
installation. See `plugins/deepseek/README.md` for the exact test entry points.
No upstream dependencies are vendored into this integration.

## Concrete review findings corrected

- Native authorization IDs now bind principal, workspace and session together.
- Cancellation is checked again after native admission and before file creation.
- New file data and its parent directory are synchronized before success receipt.
- Invalid fold items and overflowing offsets are rejected before storage/file work.
- The coordinator redacts adapter exception messages and verifies lifecycle metadata,
  original order, granted authority and published native receipt together.
- Memory detects missing or regressed derived heads instead of silently hiding sources.
- Workspace tools cannot read runtime or native authority state, including via symlinks.
- MCP tests generate their own portable profiles; no ignored local file is needed in CI.

## Explicit limits

No paid model calls, new training, live Jev evaluation or new model benchmark was
performed. Sensor fixtures are documented protocol examples; loopback HTTP tests
exercise transport, not an inference service. Runtime replay inputs are labelled
contracts and actual filesystem/memory effects are inspected.

The own generative cycle and SCO model binding are implemented but have not been
accepted against a real provider endpoint. DeepSeek's full SDK launch/profile path
has not been accredited by these tool-pipeline tests. OpenClaw/QwenPaw host imports
and live workflows remain unexecuted. There is no global security-superiority claim,
remote authentication, hostile-plugin sandbox, semantic memory-quality claim or
universal guarantee of exactly-once external effects.

Private own experimental evidence is maintained outside this public code proposal.
