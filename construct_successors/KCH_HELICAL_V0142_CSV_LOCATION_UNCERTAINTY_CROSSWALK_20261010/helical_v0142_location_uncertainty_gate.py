from __future__ import annotations

import helical_v014_location_uncertainty_gate as predecessor

# Preserve the v0.14.1 narrow software repair. The scientific delta of this
# successor is explicit and limited to the observation adapter supplied through
# --crosswalk-runtime: USGS FDSN CSV bulk instead of GeoJSON summary.
predecessor.CORE.REMAINING_SEALED = set(predecessor.CORE.REMAINING_SEALED)

if __name__ == "__main__":
    raise SystemExit(predecessor.main())
