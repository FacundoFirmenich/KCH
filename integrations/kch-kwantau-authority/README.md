# KCH ↔ KwanTau Constitutional Authority Broker 0.1.0

This additive integration exposes the authority that already exists in KCH Native 0.11.33 to KwanTau without minting a second authority system.

## Source-of-truth boundary

KCH Native currently authorizes one exact attempt by binding `(session_id, tool_name, args_sha256)` to a user-approved proposal. The predecessor database does not natively prove the richer KwanTau identifiers such as RDSS decision ID, CAS support certificate, AAD assurance ID, reservation ID or lease ID.

This broker therefore makes two separate statements:

1. **KCH-attested:** an unconsumed KCH authorization exists for the exact session, tool and canonical arguments.
2. **Envelope-bound:** the broker atomically binds that KCH authorization to one KwanTau envelope hash and records the richer identifiers in the KCH event chain.

The second statement does not retroactively make those richer identifiers independently KCH-validated.

## Transaction protocol

Enforce mode uses a one-shot claim:

```text
AUTHORIZED (existing KCH)
  -> PREPARED
     -> COMMITTED
     -> ABORTED
     -> IN_DOUBT
```

A proposal can receive at most one bridge claim. PREPARED is therefore not a reusable bearer token.

### prepare

`kch.authority.prepare` verifies the live KCH hash chain, starts `BEGIN IMMEDIATE`, finds an unconsumed user authorization matching exact session/tool/args hash, atomically creates one short-lived claim bound to the envelope hash, and appends `KWANTAU_AUTHORITY_PREPARED` to the existing KCH event chain.

No side effect is executed and the predecessor authorization is not yet consumed.

### commit

`kch.authority.commit` is called **before** KwanTau dispatches the remote side effect. It atomically consumes the predecessor authorization, binds one KwanTau dispatch identity, marks the original proposal `CONSUMED`, marks the claim `COMMITTED`, and appends a KCH event. Only after this commit may KwanTau call the remote executor.

### receipt

After Gateway acceptance, `kch.authority.receipt` attaches the remote `runId` and acceptance/receipt hash to the already-consumed claim. Receipt binding can also resolve an `IN_DOUBT` claim after external reconciliation.

### abort

`abort` is permitted only when the caller can establish that no external side effect occurred. It makes the claim and proposal non-reusable. A fresh attempt requires a fresh user authorization.

### indoubt

If dispatch may have occurred but the remote run/receipt is uncertain, `indoubt` moves an already COMMITTED claim to `IN_DOUBT`. The underlying user authorization remains consumed. Recovery must reconcile the same claim; it can never mint a second attempt.

## Shadow verification

`kch.authority.verify` is read-only and never reserves or consumes authority. It is suitable for shadow campaigns only. Enforce mode must use prepare, because read-only verification has a time-of-check/time-of-use race.

## Transport

`kch-kwantau-authority` is a line-delimited JSON-RPC-like stdio process. It opens no TCP listener and creates no credentials. A future KwanTau managed-native adapter should own its process lifecycle, analogous to existing stdio RPC adapters.

## Evidence and provenance

Every PREPARE/COMMIT/ABORT/IN_DOUBT transition is appended to the existing KCH `events` hash chain. `generation` in responses is the current KCH event-head hash.

The broker does not replace the KCH ledger, user gesture, lock system or proposal workflow.

## Validation

Run:

```bash
python -B -m unittest discover -s tests -v
```

The tests create a fixture matching the existing KCH Native schema and exercise replay, conflicting envelopes, exact authorization matching, commit consumption, abort, in-doubt, expiry and event-chain integrity. Fixture results are tests, not evidence of a live user authorization.
