from __future__ import annotations

import helical_v011_directional_pretest_core as core

# Content-addressed correction from the actual upstream v0.10 receipts.
# The predecessor aborted before acquisition because an inter-session summary
# carried stale IDs and counts.  No protocol, threshold, cohort, source or
# scientific operator is changed here.
core.EXPECTED_SELECTED_TOTAL = 61_555
core.EXPECTED_SELECTED_COUNTS = {
    "BAY_AREA_HAYWARD_CALAVERAS": 37_853,
    "PARKFIELD_CENTRAL_SAF": 23_702,
}
core.EXPECTED_ELIGIBILITY_ID = "h10elig:8126dfea8302dd5c9ea15c04afb5d4e7d1407c2bdb47b24cea34c91efbb37ed0"
core.EXPECTED_UNSEAL_REQUEST_ID = "h10unsealreq:1e886dc0c068df426f52295b860a64948f085a4bdcc16f89a953432c9cc959c0"

if __name__ == "__main__":
    raise SystemExit(core.main())
