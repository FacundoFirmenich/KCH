# VPS collector precision 0.1.1

This bounded runtime repair keeps the package at 0.1.0 and reports the collector version separately. No hook or permission definition changes.

Unrequested process inventories now return null counts, not zero. Existing consumers of these counts must handle null as unavailable. An explicitly requested empty inventory still returns zero. This is a deliberate correction of the result contract.

The collector preserves the Linux PSI averages and additionally measures pressure counter deltas over its sampling window. CPU uses `some`; CPU `full` is undefined at system scope. Missing counters and resets retain explicit unavailable/reset states, not invented zeroes. See the [Linux kernel PSI documentation](https://docs.kernel.org/6.10/accounting/psi.html).

Neither low utilization nor process counters prove application health, useful progress or that a process should be terminated. The collector remains read-only, with individual processes excluded unless an explicit UID allowlist is supplied. No daemon, model call, signal or restart is added.

The precision tests use deterministic unit fixtures, not fabricated observations. The original VPS tests are retained. Private operational observations, conversation data and access profiles are not part of this public package.
