#!/usr/bin/env bash
set -euo pipefail

HEX="${1:-CHP_V12_BENCH.ino.hex}"
EXPECTED="d836150d52346e94d0bd1645968f9241befc4caa2723a501637b2762f23e3c39"

[[ -f "${HEX}" ]] || { echo "missing HEX: ${HEX}" >&2; exit 20; }
ACTUAL="$(sha256sum "${HEX}" | awk '{print $1}')"
[[ "${ACTUAL}" == "${EXPECTED}" ]] || {
  echo "HEX hash mismatch: ${ACTUAL}" >&2
  exit 21
}
command -v teensy_loader_cli >/dev/null 2>&1 || {
  echo "teensy_loader_cli not found" >&2
  exit 22
}
if [[ "${CHP_FLASH_ARM:-}" != "I_UNDERSTAND_THIS_FLASHES_PHYSICAL_HARDWARE" ]]; then
  echo "FAIL-CLOSED: set CHP_FLASH_ARM only after physical safety preconditions are signed off." >&2
  exit 23
fi

echo "Frozen HEX SHA-256: ${ACTUAL}"
echo "Target: TEENSY41"
exec teensy_loader_cli --mcu=TEENSY41 -w -v "${HEX}"
