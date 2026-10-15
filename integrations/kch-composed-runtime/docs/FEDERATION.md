# Original KCH SuperMCP federation

This integration calls the original KCH SuperMCP over its stdio transport. It
does not replace Studio, flatten its components into a new catalogue, or bypass
its governing dispatch. The composed runtime adds an explicit host allowlist,
scope binding, canonical JSON Schema validation and a durable invocation audit.

## Executable source and observed coverage

The subprocess executes `kch_studio.super_mcp_overlay` from AIO2 Studio 0.3.16,
with the frozen corrected KCH 0.11 source in `work/KCH_0.11_REEXTRACT_FINAL/src`.
Its seven packaged dependencies are loaded from that release's bundled pure
Python wheels. No bootstrap script, global installation, external model or
remote service is executed by federation startup.

The original process currently advertises **294 canonical tools**. Discovery
returns all original descriptors, while `schemas()` exposes only the tools named
in the host's policy. Tool counts represent discovery coverage, not verified
execution of all capabilities. Real subprocess tests execute the independent
base status, Studio status and constitutional lock-list surfaces. In these
tests, the original runtime verifies 23 governance source nodes and 8 compiled
artifacts, and reports the seven base component packages available.

The first real invocation exposed a pre-existing Git checkout transport issue:
five compiled governance artifacts have LF bytes where their original lock
records CRLF bytes. The bridge stages a private copy and permits LF-to-CRLF
reconstruction **only if the exact SHA-256 and byte length match the unchanged
original lock**. It never recalculates, repairs or weakens that lock. Modified
artifacts that cannot meet it are rejected. The original runtime additionally
checks source-node hashes, graph identity and governing semantics. Vendored
source files remain unchanged.

## Host configuration

`kch_config(repository, workspace, state_dir, principal, session, allowed_tools)`
builds the JSON configuration without starting a process or granting authority.
`FederationBridge.from_config(config, audit_path)` validates and freezes a copy.

| Field | Contract |
|---|---|
| `schema` | `kch.composed.federation-host.v1` |
| `namespace` | 1–24 letters/digits/underscores, starting with a letter |
| `repository` | Absolute path to the KCH checkout containing the original AIO2/frozen base |
| `workspace` | Absolute existing workspace; subprocess working directory |
| `state_dir` | Absolute dedicated runtime state, permanently bound to this configuration |
| `principal`, `session` | Exact host identity; neither is selected by tool arguments |
| `allowed_tools` | Map keyed by exact canonical native names; no wildcard grants |
| `timeout_seconds` | Positive transport deadline, at most 300; default 30 |
| `max_message_bytes` | 1 KiB–64 MiB per message; default 8 MiB |

Each tool policy requires `read_only: true` or `false`, and can provide
`fixed_arguments` plus an additional `argument_schema`. Native schema and host
schema must both validate. Fixed arguments are removed from model-facing
properties and required fields; the caller cannot supply them, even with the
same value. They are inserted from host configuration immediately before native
schema validation. External schema references are rejected without lookup.
Identity, session, workspace and authority argument names are reserved, including
inside nested caller payloads. If a native tool requires such a field, the host
must supply it through fixed arguments; model-supplied variants are denied.

`read_only: true` requires the canonical upstream descriptor's
`annotations.readOnlyHint` to be exactly `true`. The host cannot relabel an
upstream mutation. The hint alone never enables a tool: exact host policy is
also required. Read-only status calls may initialize local runtime metadata;
this is not a promise of zero local writes.

`read_only: false` additionally requires a trusted Python `authorize` callback.
The callback receives the exact request, call ID and binding and must return
the Boolean `True` immediately before dispatch. The CLI does not manufacture
such a callback. Its configuration alone therefore cannot enable mutations.
The upstream KCH permission and authority checks still run after this host gate.

## Runtime interface

| Method | Result |
|---|---|
| `discover()` | Detached copy of canonical descriptors; handles pagination and rejects duplicate names |
| `schemas()` | OpenAI function descriptors for the explicitly allowed subset |
| `binding()` | Configuration/catalogue hashes, namespace, exact scope and state path; no credentials |
| `invoke(alias, arguments, call_id=...)` | `{result: original_MCP_result, receipt: audited_receipt}` |
| `audit()` | Hash-chain and completed-result consistency validation, state counts |
| `close()` | Terminates and reaps the original child process |

Aliases use `namespace + '_' + sha256(canonical_name)[:32]`. They are stable,
at most 57 characters, and checked for collisions within the discovered
catalogue. Original names remain in descriptors and invocation receipts.

The host must bind `binding()` into the session's immutable tool configuration
and compare its scope with the active session before exposing tools. Distinct
principals, workspaces or sessions cannot share the same runtime state directory.
The returned catalogue/configuration copies cannot mutate active policy.

## Recovery and failure semantics

The SQLite audit commits `STARTED` and an append-only event before transport
dispatch. Successful replies retain the exact MCP result with request, result,
binding and event hashes. A completed call can return its original receipt after
restart without calling the native tool again. Reusing an ID for another request
is denied; catalogue changes do not create a fresh idempotence namespace.

Timeout, child death, protocol errors and missing completion receipts yield
`FederationUncertain`. A `STARTED` or `UNCERTAIN` call cannot automatically run
again. This is intentionally conservative: an error may occur after an effect.
There is no blind retry and no automatic reconciliation that asserts whether an
unobserved effect happened. The host must inspect original state before issuing
a distinct, explicitly adjudicated operation.

`FederationDenied` denotes pre-dispatch validation/authority rejection. Native
tool results with `isError: true` remain completed original MCP results; their
error semantics are not rewritten into success. MCP notifications are bounded;
server requests for client capabilities, sampling or elicitation are rejected.
Both writing and reading have deadlines, stdout frames are bounded, and stderr
is drained with a bounded retained tail. Ambient user credentials and KCH
settings are not inherited by the subprocess.

The audit is checked before dispatch. Completed results are cross-checked with
their corresponding chain events, not just their locally editable digest field.
Cached receipt envelopes also require their exact key set, canonical schema and
the literal Boolean `authority_inherited: false`; added or altered authority
metadata is rejected before a cached receipt can be returned.
Every call row is reconstructed from the retained dispatch events, including
started and uncertain calls; missing, extra or inconsistent projection rows fail
the audit. A separately persisted event head detects a truncated event tail.
This detects inconsistent edits; it is not external signing or protection
against a malicious host administrator who can replace all state and code.

## Verification and limits

Run the real original-process integration suite with:

```bash
python -m unittest discover -s integrations/kch-composed-runtime/tests -p test_federation.py -v
```

The package must be installed or its `src` added to `PYTHONPATH`. The federation
extra supplies JSON Schema, NumPy and SciPy dependencies. Tests explicitly skip
when these prerequisites are absent; a skipped suite is not verification.

Coverage includes live catalogue discovery, actual base/Studio/lock calls,
fixed-argument rejection, canonical and host schema enforcement, unlisted-tool
denial, mutation relabelling rejection, exact scope isolation, completed replay,
conflicting IDs, real child death, uncertain-call non-replay, governance-lock
corruption and audit-chain tampering. No surrogate MCP server or fabricated
model response is used.

This process transport is not an OS sandbox. It does not prove every native
tool's path confinement, external credentials, business authority, tool quality
or every KCH surface operational. Those tools require their own host policy and
domain-specific gates. No live external mutation or paid inference was performed
for this federation increment.
