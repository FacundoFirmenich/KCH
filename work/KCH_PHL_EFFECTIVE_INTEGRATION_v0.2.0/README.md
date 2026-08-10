# KCH PHL effective integration v0.2.0

Successor control plane for the bounded gate `GATE_PHL_EFFECTIVE_KCH_INTEGRATION_v0.2.0`.

It adds:

- one service-mediated SQLite writer for Codex/Cline clients;
- optimistic conflict detection through `expected_head_hash`;
- request idempotency and collision rejection;
- strict `kch.reviewable-decision.v0.2.0` envelopes;
- an evidence-linked `READ_ONLY`/`MUTATING` catalog;
- fail-closed dispatch for unknown methods;
- PHL lock enforcement around routed mutation;
- emitter inventory and bounded/full gate adjudication.

It does not collect user feedback, map `000..100`, train a policy, modify the personal state, or claim global KCH coverage.

Run tests:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

Run the loopback service only with an explicit state copy and secret token file:

```powershell
python -m kch_phl_integration.server --state runtime\shadow.sqlite3 --token-file runtime\token.txt
```

