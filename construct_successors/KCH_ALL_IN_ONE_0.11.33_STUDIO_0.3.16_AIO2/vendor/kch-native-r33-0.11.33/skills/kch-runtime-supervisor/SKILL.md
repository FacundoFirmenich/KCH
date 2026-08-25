---
name: kch-runtime-supervisor
description: Supervise every live command, process, campaign, upload, build or long-running tool call until a verified terminal state. Use whenever a tool yields a running cell, background PID, redirected log, asynchronous job, upload, benchmark, experiment, build or any promise to monitor results.
---

# KCH Runtime Supervisor

Never wait for the user to request results from a process already launched.

## Procedure

1. Record process or cell identity, command jurisdiction, start time, expected outputs, logs and
   terminal criteria immediately after launch.
2. Poll the process, stdout, stderr and material artifacts at intervals short enough to detect early
   failure while keeping the user informed at least every minute.
3. Distinguish running, blocked, failed, inconclusive and terminal success. A marker, partial file or
   empty process list alone is not success.
4. On failure, preserve logs and partial evidence; localize the cause before relaunching. Obey
   one-launch/no-relaunch contracts when present.
5. After a repair, monitor the new attempt under a new identity and reconcile old artifacts so they
   cannot masquerade as the new outcome.
6. At terminal state, verify exit status, stderr, receipts, expected artifacts and hashes, then
   explain what the result means and what remains unvalidated.

An explicit user order to stop terminates persistence immediately. Do not reinterpret it as a need
for more monitoring.
