from __future__ import annotations

import argparse
import json
from pathlib import Path

from common_v09 import content_id, sha256_file, utc_now, write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare—but do not execute—the distinct directional-unsealing successor")
    parser.add_argument("--eligibility-result", required=True, type=Path)
    parser.add_argument("--acquisition-receipt", required=True, type=Path)
    parser.add_argument("--extraction-receipt", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    eligibility = json.loads(args.eligibility_result.read_text(encoding="utf-8"))
    acquisition = json.loads(args.acquisition_receipt.read_text(encoding="utf-8"))
    extraction = json.loads(args.extraction_receipt.read_text(encoding="utf-8"))
    if eligibility.get("outcome") != "ELIGIBILITY_PASS" or eligibility.get("execution_authorized") is not True:
        raise SystemExit("directional-unseal request cannot be created without ELIGIBILITY_PASS")
    if eligibility.get("angle_fields_accessed") is not False:
        raise SystemExit("blind barrier was not preserved")
    if extraction.get("sealed_fields_emitted") != []:
        raise SystemExit("sealed fields were emitted before selection")
    selected = eligibility.get("selected_primary_cohorts") or []
    if len(selected) < 2:
        raise SystemExit("fewer than two primary cohorts were selected")

    body = {
        "format": "KCH_HELICAL_V0_9_DIRECTIONAL_UNSEAL_SUCCESSOR_REQUEST",
        "created_at_utc": utc_now(),
        "scientific_protocol_id": eligibility.get("protocol_id"),
        "eligibility_result_id": eligibility.get("eligibility_result_id"),
        "eligibility_transport_receipt_id": eligibility.get("transport_receipt_id"),
        "selected_primary_cohorts": selected,
        "acquisition_receipt_id": acquisition.get("receipt_id"),
        "extraction_receipt_id": extraction.get("receipt_id"),
        "protocol_file_sha256": sha256_file(args.protocol),
        "directional_fields_authorized_for_distinct_successor_only": [
            "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
            "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
        ],
        "directional_unsealing_performed": False,
        "model_fitting_authorized": False,
        "scientific_interpretation_authorized": False,
        "requires_new_finite_authority": True,
        "requires_new_append_only_successor": True,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    body["request_id"] = content_id("h9unsealrequest", body)
    write_json_atomic(args.output, body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
