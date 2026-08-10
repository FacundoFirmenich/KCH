# KCH SuperChats Orchestrators (SCO) v0.1.0

SCO is a KwanCode Harness orchestration plane for selecting sovereign chat/task sessions and composing them as a typed graph **without merging their native histories, contexts, memories, tools or lifecycles**.

## Operational boundary

Implemented:

- exact native references for Codex, ChatGPT, Cline, Cowork, OpenCode and custom providers;
- explicit node roles, responsibilities, capabilities, autonomy and authority ceilings;
- scoped disclosure references with mandatory prohibitions against context fusion, memory copying and implicit authority transfer;
- directed typed orchestration edges;
- dependency-aware work orders;
- success, failure, blocked and abstention receipts preserved as distinct states;
- explicit conflict records, with divergence retained;
- immutable hash-linked event ledger, command idempotency and stale-writer rejection;
- portable graph export with no native chat content;
- dispatch envelopes that fail honestly when a live provider bridge is unavailable;
- CSI lowering using only `OPEN_SESSION`, `SEAL_IDENTITAS`, `ADD_DATUM` and `MODE_ON`.

Not demonstrated in v0.1.0:

- live read/write bridges for Cline, Cowork or OpenCode;
- autonomous cross-provider dispatch;
- semantic quality gains over a baseline Projects implementation;
- distributed consensus or multi-host operation;
- universal CSI equivalence beyond the sealed lowering receipt.

Codex native selection was observed through the host bridge in the build run. The standalone package preserves and orchestrates references; it never claims to read or message a provider whose bridge has not passed its own gate.

## CLI

Install in editable mode or set `PYTHONPATH=src`, then:

```powershell
sco --state runtime\sco.sqlite3 create --json specs\superchat.json
sco --state runtime\sco.sqlite3 add-node --json specs\node.json
sco --state runtime\sco.sqlite3 add-edge --json specs\edge.json
sco --state runtime\sco.sqlite3 issue --json specs\order.json
sco --state runtime\sco.sqlite3 receipt --json specs\receipt.json
sco --state runtime\sco.sqlite3 schedule --sco-id my-sco
sco --state runtime\sco.sqlite3 envelopes --sco-id my-sco --output runtime\dispatch.json
sco --state runtime\sco.sqlite3 verify
```

Every mutating command accepts `--actor`, `--command-id` and `--expected-head`. Output files are never overwritten silently.

## Meaning of “superior”

The v0.1.0 claim is architectural and testable, not commercial: SCO has stronger explicit invariants than a shared project container—sovereign identity, context isolation, authority separation, causal lineage and adverse-result preservation. Actual outcome superiority requires comparative campaigns and is not claimed by this release.
