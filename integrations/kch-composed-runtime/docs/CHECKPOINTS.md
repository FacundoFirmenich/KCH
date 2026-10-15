# Scoped portable evidence checkpoints

`checkpoint.export_checkpoint(runtime, path)` exports one trusted host-bound
`Runtime.scope` to ZIP. `checkpoint.import_checkpoint_evidence(runtime, path,
source_ids=None)` imports evidence into the destination scope. Both functions
acquire `Runtime.lock()` and reject concurrent ownership.

This extends the composed runtime. It does **not** replace Studio's existing
`CheckpointManager`, structured checkpoints, full checkpoints or recovery vault.
The Studio implementation was inspected: its content-addressed blobs, exact-byte
reconstruction and SQLite backup approach are suitable for whole managed roots.
A whole-root copy is inappropriate here because shared SQLite databases contain
multiple principals/sessions and native state can contain authorization grants.
Consequently this adapter transports validated, scoped logical records instead.

## Export contract

The source memory and journal connections hold `BEGIN IMMEDIATE` transactions at
the same time while the snapshot is captured. Every memory revision is exported,
including invalidated originals, original provenance and predecessor links.
Folds, views, dependency edges, invalidation records, session configuration,
provider-native message fields, tool receipts and the original session hash chain
are preserved. Existing import audit outbox records, including pending delivery,
are also preserved as evidence; importing them does not enqueue source-side work.
Original content is stored as exact bytes in SHA-256 addressed
blobs. Immutable metadata and session events retain their source representation.

The ZIP contains only `manifest.json`, `snapshot.json` and referenced blobs. No
native state database, authorization grant database, environment variables,
credential store, workspace tree or other runtime scope is traversed. Deliberate
source content or message text may itself contain sensitive material: this is
exact transport, **not** an automatic secret scrubber. Keep archives private.
The file is written with private temporary-file permissions and linked atomically
without overwriting an existing target. Both file contents and the containing
directory are `fsync`ed before returning a success receipt. If the directory
sync fails after the link was created, export raises; the archive remains for
inspection and no success receipt is returned. Retrying with the same output
path refuses to overwrite it.

Export preserves uncertain `STARTED` receipts as evidence. It does not infer
completion or authorize a replay.

## Import contract

All archive entries and original memory/session invariants are validated before
any destination mutation. Paths, duplicates, symlinks, special files, encryption,
unsupported ZIP formats, unreferenced payloads and hash mismatches are rejected.
Limits: 256 MiB archive, 128 MiB expanded data, 64 MiB per member and 20,000
members. Larger evidence requires an explicitly designed successor format.
SHA-256 verifies internal consistency; it does not authenticate an unknown sender
who can rewrite both an archive and its manifest.

The original ZIP is stored as a binary memory source in the destination scope.
By default no other source is materialized. Explicit `source_ids=[...]` imports
all revisions of those logical sources into namespaced destination source IDs.
Original manifests, record hashes and source scope are retained in provenance;
destination revision IDs are new and their mapping is included in the receipt.
Original invalidations remain invalidated, including an invalidated latest
revision. Imported folds, views, sessions and provider fields remain intact in
the archived evidence; they do not become active destination folds or sessions.

The destination journal receives only a `checkpoint.imported` event. Original
messages are never appended as live prompts, system messages, model bindings,
call receipts or permissions. No tools execute, no native provider session is
activated, no leases move and no active continuation is claimed. All imported
material has `EVIDENCE_ONLY` status. Runtime scope must come from trusted host
configuration; archive metadata cannot select the destination principal.

## Atomicity and recovery

The memory archive, selected source revisions, preserved invalidations and an
import audit outbox record are committed in one memory transaction. The journal
has its own database; cross-database atomicity is not claimed. After that commit,
the outbox is delivered idempotently to the destination journal. A journal error
returns `audit_delivery=PENDING_RETRY_IMPORT`. Repeating the same import, with
the same scope and selected source IDs, retries delivery without duplicating
sources. A crash after journal delivery is also safe: receipt identity prevents a
second event. Successful delivery returns `audit_delivery=DELIVERED`.

The complete outbox receipt is sealed at insertion. A repeat import verifies
that seal, the exact destination scope/selection/contract, the unchanged archived
bytes and every selected original revision, provenance and invalidation. An
existing journal receipt must match the entire outbox receipt, not only its ID.
Corruption or divergence is rejected; it is never re-sealed, repaired or returned
as a delivered success. An older unsealed prerelease outbox requires explicit
migration and is not blessed automatically.

A receipt records source/destination scopes, archive digest, source/revision
mapping, destination archive source ID and explicit non-activation flags.

## Verification

`python -m unittest discover -s tests -p test_checkpoint.py -v` checks exact
repository bytes, corrected revisions, folds/views/session preservation, strict
scope separation, invalidated latest-source handling, immutable destination
message/call state, no replay, idempotence, concurrent-session refusal, output
collision refusal, corruption/traversal/duplicate rejection before mutation and
interrupted-audit recovery. Contract-authored metadata is labelled as such; no
model response or model inference is fabricated by these tests.
