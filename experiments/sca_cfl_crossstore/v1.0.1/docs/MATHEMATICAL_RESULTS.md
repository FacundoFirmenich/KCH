# Mathematical results — Cross-store continuity v1.0.1

## Four operational observation states
For each persistence surface, the verifier returns one of four operational states: absent, present-unverified, verified-noncurrent, verified-current. This is not asserted to be identical to CFL's ontological quaternary states; it is a typed four-state transport contract.

## Conservative promotion
Strong promotion occurs iff every required surface supplies a verified observation whose release digest and parent digest equal the expected manifest. Any verified incompatible observation yields HOLD.

A 2/3 majority cannot overrule a verified conflicting third observation. A 2/3 match may be emitted only as a recovery hint, with authority=false.

## Parent binding
A release is not current merely because its payload digest matches. It must also bind the expected parent manifest.

## Scope
These are release/persistence guarantees. They do not establish truth of scientific claims inside the artifact, production Byzantine consensus, or independence of vendors/accounts.
