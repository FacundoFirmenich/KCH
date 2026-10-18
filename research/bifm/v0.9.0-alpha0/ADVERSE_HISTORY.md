# Adverse history — BIFM v0.9

## AH-009-001 — OLMo replication is formally valid but substantively weak

The preregistered OLMo layer-8 MLP scale-3 intervention preserves all 12 observation decisions. However, the measured post-residual hidden displacement is approximately 2.985e-05, the JS divergence is approximately 1e-08, and the frozen counterfactual set has zero flips.

Decision: retain the result, but downgrade its interpretation from a strong mechanistic replication to a weak-boundary intervention-state collision. A future inter-model gate must preregister a substantive-effect criterion in addition to nonzero intervention identity.

## AH-009-002 — Frontier estimates can be right-censored

Several Qwen epsilon-star values equal the largest tested grid value, 2.00. These are not point estimates of the true frontier; they are lower bounds within the tested range.

Decision: report `>= 2.00 on tested grid` in narrative interpretations and extend adaptively only in a future preregistered successor.

## AH-009-003 — Counterfactual top-1 recovery is not guaranteed by distributional divergence

At Qwen layer 24, the intervention produces substantial hidden displacement and nonzero full-distribution divergence but zero counterfactual top-1 flips.

Decision: do not equate absence of top-1 flips with functional identity. Build an observation lattice in the next release.

## AH-009-004 — One deterministic observation ordering does not provide sampling uncertainty

The nested B4/B8/B12/B16 sets are deterministic and balanced by baseline predicted class. The resulting frontier is a valid property of those frozen sets, but not a population estimate across possible ARC samples.

Decision: the next confirmatory design must include multiple independently hashed real-data observation samples or a prospectively specified resampling design.

## AH-009-005 — Layer comparisons are intervention-relative

The layer-4, layer-14 and layer-24 values compare identical scaling semantics but not necessarily equal causal magnitudes, because raw MLP contribution scales differ by layer.

Decision: report hidden displacement and distributional divergence alongside epsilon, and avoid reading epsilon alone as a cross-layer causal effect size.
