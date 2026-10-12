#!/usr/bin/env bash
set -euo pipefail
usage(){ echo "Usage: $0 --input FILE --expected-sha256 HEX --output-dir EMPTY_DIR [--memory-mib N] [--timeout-seconds N]" >&2; exit 64; }
input=""; expected=""; output=""; memory_mib=8192; timeout_seconds=2700
while (($#)); do
  case "$1" in
    --input) input=${2-}; shift 2;;
    --expected-sha256) expected=${2-}; shift 2;;
    --output-dir) output=${2-}; shift 2;;
    --memory-mib) memory_mib=${2-}; shift 2;;
    --timeout-seconds) timeout_seconds=${2-}; shift 2;;
    *) usage;;
  esac
done
[[ -n "$input" && -n "$expected" && -n "$output" ]] || usage
[[ "$expected" =~ ^[0-9a-f]{64}$ ]] || { echo "invalid expected SHA-256" >&2; exit 64; }
base=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$output"
"$base/NETWORKLESS_SANDBOX_ENGINE_V0_9.sh" \
  --input "$input" \
  --program "$base/HARDENED_PICKLE_EXTRACTION_V0_9.py" \
  --support-dir "$base" \
  --output-dir "$output" \
  --timeout-seconds "$timeout_seconds" \
  --memory-mib "$memory_mib" \
  --output-limit-mib 4096 -- \
  --input /in/source --expected-sha256 "$expected" --output-dir /out
"$(command -v python)" "$base/VERIFY_SAFE_NPZ_V0_9.py" \
  --npz "$output/blind_columns.npz" \
  --extraction-receipt "$output/EXTRACTION_RECEIPT_V0_9.json" \
  --output "$output/SAFE_NPZ_VERIFICATION_RECEIPT_V0_9.json"
