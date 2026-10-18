# Adverse history — BIFM v0.11.1

## AH-0111-001 — sequential collector wall-clock bottleneck

The original v0.11 collector runs baseline plus nine interventions sequentially on one CPU job per layer. It remained valid but too slow for the interactive gate.

Correction: v0.11.1 partitions the identical scientific design into 30 independent `(layer, intervention)` shards. No model, data, prompt, sample, intervention, operator, threshold or posterior choice changed.

## AH-0111-002 — first-page job wrapper hid the final job

The GitHub connector wrapper returned only the first 30 jobs, exactly the shard matrix. This initially made the final `assemble-and-summarize` job appear absent.

Correction: the full API page with `per_page=100` confirmed job 31 completed successfully. No rerun or data mutation occurred.

## AH-0111-003 — source files were hashed but omitted from the result artifact

The final workflow recorded hashes for five source scripts, but the uploaded artifact contained only assembled data, receipts, tables and logs. Result hashes verify locally; source bytes must be recovered from the frozen commit.

Correction: the consolidated release preserves the original artifact, records the source commit and hash list, and treats this as a packaging defect. It does not affect the executed results.

## AH-0111-004 — NumPy JSON serialization adapter

The frozen summary can produce NumPy scalar types in result dictionaries. A separate adapter converts only NumPy scalars/arrays at serialization time.

No equality test, sample, threshold, posterior, seed or result value was changed.

## AH-0111-005 — correlated cells

Cells across epsilon, sample size and cumulative operator are correlated. The local Beta-Binomial hierarchy is therefore secondary sensitivity analysis, not a set of independent scientific replications.

Correction: a shared-weight Bayesian bootstrap preserves all block-level dependencies and the exact partial order in every draw.

## AH-0111-006 — below-grid frontiers represented as zero in bootstrap summaries

When no nonzero tested epsilon is invisible, the exact frontier is below 0.05 and stored as missing. The bootstrap substitutes zero solely to summarize the grid-censored empirical frontier.

This is not a claim that the continuous frontier is exactly zero.

## AH-0111-007 — source hash verification from the downloaded artifact is partial

The downloaded final artifact locally verifies every data, receipt, table and log hash listed in its manifest. The five source hashes cannot be checked from that ZIP because the source files were not included.

Their provenance is the frozen commit `30d2366b46657395ca4b106eae7c0667195fcb4d`.

## AH-0111-008 — one model/domain remains

Six disjoint blocks quantify local sample variation, but all blocks come from one ARC pool and one Qwen revision. The posterior remains conditional on that empirical support.

No claim over all prompts, domains, model families or deployments is authorized.

## AH-0111-009 — no global identifiability scalar

The result varies sharply by layer, operator, sample size, block and intervention. Any global average would erase the principal finding.

Decision: report jurisdictional tables, exact certificates, frontier distributions and local posteriors; prohibit a sole grand score.
