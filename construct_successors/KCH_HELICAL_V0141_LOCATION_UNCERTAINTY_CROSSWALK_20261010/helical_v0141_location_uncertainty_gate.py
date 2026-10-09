from __future__ import annotations

import helical_v014_location_uncertainty_gate as predecessor

# Narrow software repair only: v0.14 compared a set with the predecessor's
# list-valued REMAINING_SEALED constant. Converting that immutable allow/deny
# collection to a set restores the intended firewall operation. No cohort,
# threshold, matching rule, source, scientific operator or test boundary changes.
predecessor.CORE.REMAINING_SEALED = set(predecessor.CORE.REMAINING_SEALED)

if __name__ == "__main__":
    raise SystemExit(predecessor.main())
