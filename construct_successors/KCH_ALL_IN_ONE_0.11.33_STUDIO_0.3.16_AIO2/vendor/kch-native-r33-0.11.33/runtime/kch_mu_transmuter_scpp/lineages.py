from __future__ import annotations

from .contracts import OperatorLineage


LINEAGES = {
    "mu_eq": OperatorLineage(
        operator="mu_eq", version="EQ4-v0.1", normalized_source_sha256="1e1bb22798fda63827ca051f09cbe8a08ce16be4cf5983edaca707048e435eba",
        transport_source_sha256="38fa4533e9b42df595bf13ad361b65ac24f988477f577f6c08ecf49025671172",
        authority="SHADOW", lineage_id="MU_EQ_FROZEN_20260809", runtime_dependency="torch",
        historical_verdict="LOCAL_SIGNAL_PRESENT_BUT_NOT_GENERAL_GRU_REPLACEMENT",
        claim_boundary="Favorable local obsolete-memory signal and clean-bijection evidence; no global superiority.",
    ),
    "mu_qe": OperatorLineage(
        operator="mu_qe", version="field-v0.1", normalized_source_sha256="bb48f8104703a2ffaf87cf8c75101238af1146d3329d5251f1c6a8bbab58581d",
        transport_source_sha256="0b29b1eec2182efc424f666c31498522c8baf81fec9f3d027b811a04e8ba59f2",
        authority="SHADOW", lineage_id="MU_QE_FIELD_FROZEN_20260812", runtime_dependency="torch",
        historical_verdict="SHADOW_ONLY_8_OF_8_LOSSES_VERSUS_GRU_WITH_LOCAL_CALIBRATION_SIGNAL",
        claim_boundary="Dynamic field and layer order have local causal evidence; μ_QE has no router authority.",
    ),
    "transmuter_v02": OperatorLineage(
        operator="transmuter_v02", version="0.2", normalized_source_sha256="ad3b590e801b7b39174b91dbc5f275eda8b0008a8b0d62e7e4fef66cb9fb2b8b",
        transport_source_sha256="587c5e315c00f3b4b01eec26491973f00e587d8523dcab48771bc830e096a134",
        authority="NONE", lineage_id="CFL_TRANSMUTER_CANONICAL_V02", runtime_dependency="numpy",
        historical_verdict="SOFTWARE_VALIDATED_Q4_NO_MATERIAL_CONTRIBUTION_TRANSFORMER_LOCAL_ADVANTAGE",
        claim_boundary="Historical reproducible control; no empirical advantage in the frozen benchmark.",
    ),
    "transmuter_v032": OperatorLineage(
        operator="transmuter_v032", version="0.3.2", normalized_source_sha256="baaf193467fa4ee0cb4708af3b84c691944b575feaaea7f940962c9b99cc2714",
        transport_source_sha256="c4ab09084956c13bd00b819f3f0677c1f383b7b26a697d0fdf3e01a337afacc1",
        authority="LOCAL_OPERATIONAL", lineage_id="CFL_TRANSMUTER_V032_SEPARATE_LINEAGE", runtime_dependency="torch",
        historical_verdict="LOCAL_ARCHITECTURAL_ENVELOPE_7_TO_1_WITH_TRANSFORMER_LOSS_ADVANTAGE_IN_SEVEN_CELLS",
        claim_boundary="Local routing only in the eight frozen jurisdictions; no cross-domain or global authority.",
    ),
    "transformer_prenorm": OperatorLineage(
        operator="transformer_prenorm", version="SCPP-P0-control", normalized_source_sha256="3eef622e7c7a64beddb8184b5e261f99732c6fed77916ef6ffd109171641f56b",
        transport_source_sha256="105c3149b5012ff9340df43da2b31355d112867b5cbfe6a5393a9adeb0705eb5",
        authority="LOCAL_OPERATIONAL", lineage_id="TRANSFORMER_PRENORM_SCPP_P0_CONTROL", runtime_dependency="torch",
        historical_verdict="MANDATORY_BASELINE_AND_CLEAR_WINNER_IN_CURRENT_DELAY2_NOISE050",
        claim_boundary="Baseline authority is local; no winner-global claim.",
    ),
    "scpp_p0": OperatorLineage(
        operator="scpp_p0", version="0.1", normalized_source_sha256="484ee9d3b4a7ba00e6fc5d846275928ff1079096db99174e30c310f59adb23a5",
        transport_source_sha256="3807462b515a8e1e35fed1305d583d7d81b08424a1b1f9e57441c22830ece5ea",
        authority="LOCAL_OPERATIONAL", lineage_id="SCPP_P0_V0_1_20260813", runtime_dependency="python",
        historical_verdict="LOCAL_EXPLORATORY_CAUSAL_PREVENTION_8_OF_8_GATES_PASS_CONFIRMATION_PENDING",
        claim_boundary="Pre-action primitive prevention supported only in the frozen local benchmark.",
    ),
}

