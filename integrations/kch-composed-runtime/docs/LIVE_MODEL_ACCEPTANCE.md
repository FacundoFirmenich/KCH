# Real local model acceptance

The composed runtime completed one real local inference/tool/memory case on
2026-10-09 UTC. This is an integration result, not a model benchmark or a claim
that a 0.6B model is sufficient for production orchestration.

The model was **Qwen3-0.6B Q8_0**, from Qwen's own repository. Inference ran on
four CPU threads through **llama.cpp b11514**, with no paid API, credential,
mock completion, injected tool call or rewritten assistant message. Both the
639,446,688-byte GGUF and the downloaded CPU release archive were checked
against their publishers' SHA-256 identifiers.

## Executed case

`scripts/acceptance_model.py` registered the prompt and acceptance checks before
calling the model. The source was the existing KCH composed runtime
`pyproject.toml`, 444 bytes at capture time, SHA-256:

`3666f1013177769cde668e3b731202b6a5d96f21df8590169788786135b5f080`

The runner captured those bytes before inference and checked actual tool
results against that captured value. Other work subsequently changed the source
file; the preserved snapshot and receipts, rather than today's working-tree
contents, define this execution's source. The initial evidence records a Git
base revision, **not an assertion of a clean working tree or a fully committed
code snapshot**.

The first genuine server response requested `read_file`, `memory_ingest`, and
`memory_recall` in that order within one assistant message. Runtime executed the
three calls sequentially and supplied their real receipts. The second response
was a final answer containing the correct source hash.

| Check | Observed result |
|---|---|
| Real provider responses | 2 |
| Model-requested tools | 3, all completed |
| Read bytes equal captured source | PASS |
| Ingest hash equals captured source | PASS |
| Recall bytes equal captured source | PASS |
| Journal integrity | PASS |
| Runtime terminal state | COMPLETED, 2 steps |
| Runner elapsed time | 59.08765 seconds |

The elapsed time is an observation of this shared CPU environment, not a
performance comparison. Server-reported token counts are preserved in the
receipts, including cached-token fields; none were estimated.

A separate registered check reopened the completed session in a new Python
process after stopping the server. `run(client, None)` returned the persisted
answer in zero steps, with no journal or tool-receipt changes. This verifies
completed-session replay. It does not establish recovery from every possible
in-flight interruption.

## Evidence

From the repository root, see `next-evidence/model/`:

- `provenance.json`: exact model revision, artifact digests and server settings.
- `attempt-01/preregistration.json`: task and checks fixed before inference.
- `attempt-01/request-*.json` and `response-*.json`: actual wire data.
- `attempt-01/receipt.json`: acceptance adjudication, including every check.
- `attempt-01/tool-receipts.json` and `journal-events.json`: execution records.
- `attempt-01/source-snapshot.bin`: exact source bytes decoded from the retained
  read receipt; its separate provenance file explains that derivation. Future
  runner invocations write this snapshot before calling the model.
- `checkpoint-preregistration.json` and `checkpoint-receipt.json`: completed
  session reopening check.
- `server-output.txt`: original inference server output.

Weights, inference binaries and mutable SQLite state are not committed. Raw
provider response fields remain untouched. The runtime's conservative
`CLIENT_RETURNED_NOT_INDEPENDENTLY_VERIFIED` attestation is also preserved; this
local gate supplies separate provenance, not remote cryptographic attestation.

## Reproduce with an explicit local server

Use a real Chat Completions server listening on a loopback address. For the
recorded engine, the relevant server arguments are:

```sh
llama-server -m /absolute/path/Qwen3-0.6B-Q8_0.gguf \
  --host 127.0.0.1 --port 18743 --alias kch-qwen3-0.6b-q8 \
  --threads 4 --threads-batch 4 -c 8192 --parallel 1 --jinja --reasoning off
```

Then, from the repository root:

```sh
python integrations/kch-composed-runtime/scripts/acceptance_model.py \
  --endpoint http://127.0.0.1:18743/v1 \
  --model kch-qwen3-0.6b-q8 \
  --weights /absolute/path/Qwen3-0.6B-Q8_0.gguf \
  --output /absolute/path/new-acceptance-directory
```

The runner requires a fresh output directory and an explicitly configured
loopback endpoint. It does not discover services, download models, start a
server, read credential stores, retry an uncertain request, or manufacture
responses. The source snapshot will reflect the version actually present during
the new run. In execution environments that isolate network namespaces per
command, start the server and runner under the same parent process.

## Primary sources

- [Qwen model at the executed revision](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/tree/23749fefcc72300e3a2ad315e1317431b06b590a).
- [llama.cpp b11514 release](https://github.com/ggml-org/llama.cpp/releases/tag/b11514).
- [llama.cpp function-calling implementation guidance](https://github.com/ggml-org/llama.cpp/blob/b11514/docs/function-calling.md).

Still unverified by this case: multi-model generalization, large-task quality,
remote provider compatibility, interruption during a native external write,
long-horizon memory quality, and live activation on the user's hosts.
