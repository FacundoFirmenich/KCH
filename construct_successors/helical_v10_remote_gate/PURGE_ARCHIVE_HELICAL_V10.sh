#!/usr/bin/env bash
set -euo pipefail
usage(){ echo "Usage: $0 --workspace DIR" >&2; exit 64; }
workspace=""
while (($#)); do
  case "$1" in
    --workspace) workspace=${2-}; shift 2;;
    *) usage;;
  esac
done
[[ -n "$workspace" ]] || usage
mkdir -p "$workspace/receipts"
exact="$workspace/exact_sources"
cache="$workspace/cache"
exact_present=false; cache_present=false; exact_bytes=0; cache_bytes=0
if [[ -d "$exact" ]]; then exact_present=true; exact_bytes="$(du -sb "$exact" | awk '{print $1}')"; fi
if [[ -d "$cache" ]]; then cache_present=true; cache_bytes="$(du -sb "$cache" | awk '{print $1}')"; fi
rm -rf "$exact" "$cache"
python - "$workspace/receipts/RAW_PURGE_RECEIPT.json" "$exact_present" "$cache_present" "$exact_bytes" "$cache_bytes" <<'PY'
import hashlib, json, pathlib, sys
body = {
    "format": "KCH_HELICAL_V0_10_UNCONDITIONAL_RAW_PURGE",
    "exact_sources_present_before_purge": sys.argv[2] == "true",
    "cache_present_before_purge": sys.argv[3] == "true",
    "exact_sources_bytes_before_purge": int(sys.argv[4]),
    "cache_bytes_before_purge": int(sys.argv[5]),
    "exact_sources_present_after_purge": False,
    "cache_present_after_purge": False,
    "raw_uploaded": False,
    "directional_fields_unsealed": False,
    "authority_ceiling": "NONE",
}
canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
body["receipt_id"] = "h10purge:" + hashlib.sha256(canonical).hexdigest()
pathlib.Path(sys.argv[1]).write_text(json.dumps(body, sort_keys=True, indent=2) + "\n")
PY
test ! -e "$exact"
test ! -e "$cache"
test -z "$(find "$workspace" -type f \( -name '*.pickle' -o -name '*.part' \) -print -quit)"
cd "$workspace"
paths=(receipts)
for candidate in blind eligibility; do [[ -e "$candidate" ]] && paths+=("$candidate"); done
tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  -czf helical-v10-result-without-raw-sources.tar.gz "${paths[@]}"
sha256sum helical-v10-result-without-raw-sources.tar.gz \
  > helical-v10-result-without-raw-sources.tar.gz.sha256
