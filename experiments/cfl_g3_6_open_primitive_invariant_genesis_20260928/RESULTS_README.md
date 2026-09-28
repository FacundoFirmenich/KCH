# CFL–UEP G3.6 — Open Primitive & Invariant Genesis

G3.6 defines Closure(G0) exactly as the finite-field linear span of [1,u,v,u^2,v^2,u^3,v^3]. Every private constructive truth is a primitive equivalence class that raises full-domain rank beyond this closure. Development uses degree <=3 cross-term primitive classes; private evaluation uses degree >=4 classes, with zero class overlap.

Results:
- 64/64 private constructive truths are outside Closure(G0).
- 64/64 true primitive classes are retained before O3.
- TOS residual O3 closes 13/32 ambiguous reducible cases.
- Exact EIG closes 16/32.
- paired delta -9.375 pp; bootstrap CI [-21.875,+3.125] pp.
- discordant pairs: TOS-only 1, EIG-only 4; exact paired sign/McNemar p=0.375.
- every state-1 output from both exact methods passes the sealed invariant certificate.
- underidentified tasks return 0; contradictory tasks return -1.

Correct adjudication: no support for TOS superiority, with an inferior point estimate but interval crossing zero. Calling this a strong refutation would overstate the evidence.

The gate demonstrates primitive/invariant extension beyond G0, but not fully open-ended constructor invention because a generic monomial meta-language is still supplied. G3.7 removes that atomic extension catalogue.

Remote GitHub Actions run 36360442474 reproduces adjudication, summary, predictions, probability control, tasks, and exact audit byte-for-byte.

Authority NONE; promotion/canonization blocked.
