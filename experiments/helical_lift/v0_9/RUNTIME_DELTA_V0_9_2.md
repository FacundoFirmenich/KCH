# Runtime 0.9.2: fail-closed semantic HOLD and reliable reruns

The real version-2 catalog contains numeric `ev_bl` categories. No numeric mapping is assumed. The frozen v0.8 protocol, cohort thresholds, quality filter and scientific operator remain unchanged.

The safe-NPZ runner verifies input receipt content addresses and vector lengths, finite numeric inputs, integral calendar components and valid calendar dates. Only explicit text labels `earthquake`, `blast`, and the frozen operator's `b` label are recognized, case-insensitively. Unknown text, numeric strings and numeric categories stop before cohort selection. A content-addressed semantic-HOLD receipt binds the protocol, source pickle hash and safe NPZ hash; exit 31 identifies this expected stop.

The orchestrator quarantines previous eligibility output before rerunning, verifies exit-code/result consistency and result lineage, and validates any proposed directional successor request. Old eligibility PASS files cannot authorize a failed current attempt. Transition chains are verified and continued. Requested raw-source cleanup runs in `finally`, including early returns and exceptions, and emits its own receipt. CI reports exit 31 as infrastructure completion with scientific eligibility explicitly blocked.

Tests use isolated software boundary fixtures, not scientific observations. The real-data recheck uses the previously verified 1,574,113-row NPZ and immutable GEM fault source. No values are imputed or rows removed. Network identifiers remain opaque; use `(nc_sc, evid)` as catalog identity because `evid` alone repeats across networks. Numeric `time_utc` is preserved without guessing its epoch; calendar validation checks the frozen fallback's inputs.

Independent record-level corroboration against immutable NCEDC and SCEDC snapshots is an evidence-gathering step. It does not select cohorts, replace labels, relax the frozen gate or grant directional access. Its own rule must be fixed before the comparison, and any missing, ambiguous or inconsistent records retain HOLD.
