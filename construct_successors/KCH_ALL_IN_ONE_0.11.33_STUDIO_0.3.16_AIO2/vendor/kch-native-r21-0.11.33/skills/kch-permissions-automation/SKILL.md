---
name: kch-permissions-automation
description: Govern proactive tool launching, scheduled work, account access and finite permission leases. Use when KCH should act automatically, ask consultatively, schedule tasks, access terminals or external accounts, or manage SSH, GitHub, Colab, Kaggle or Drive authority.
---

# KCH Permissions and Automation

## Decision layers

For every action classify capability, host support, required permission, granted authority, intended execution and persistence. A tool may exist without being authorized or runnable.

## Activation policy

Evaluate relevant tools proactively. The default consultative surface offers exactly:

- `Sí`
- `No`
- `Nunca en esta sesión`
- `Siempre en esta sesión`

Session choices never create general or future-session authority. A direct programmed policy may run without consultation only when explicitly configured, scoped and announced at session start.

## Finite account access

Request the narrowest feasible scope and a finite duration: punctual, daily, weekly, monthly, quarterly or custom. Never request indefinite authority. Prefer a local terminal authentication flow when supported; otherwise use the host-native web flow. Do not capture or persist credentials in KCH artifacts.

## Scheduling

Define one-shot or recurring trigger, timezone, inputs, authority lease, observable completion, retry ceiling, cancellation, notification and evidence. Monitor scheduled executions until terminal state.

Before a risky customization, warn and record the overridden warning; do not censor the user. Preserve a recoverable stable configuration.
