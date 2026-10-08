# Verification of the composed runtime increment

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
