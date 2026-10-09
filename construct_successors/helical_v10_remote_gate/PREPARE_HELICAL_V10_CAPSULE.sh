#!/usr/bin/env bash
set -euo pipefail

usage(){ echo "Usage: $0 --github-output FILE --receipts DIR" >&2; exit 64; }
github_output=""; receipts=""
while (($#)); do
  case "$1" in
    --github-output) github_output=${2-}; shift 2;;
    --receipts) receipts=${2-}; shift 2;;
    *) usage;;
  esac
done
[[ -n "$github_output" && -n "$receipts" ]] || usage
mkdir -p "$receipts" "$RUNNER_TEMP/capsule"
cd "$GITHUB_WORKSPACE"

cat > "$RUNNER_TEMP/capsule/PARTS.sha256" <<'PARTS'
c352abe67d9e338f4068db8e676916e211c24fdd0c99d7b56d95d8c343905356  construct_successors/helical_v10_capsule_parts/part-000.b64
f7ad095141b479654c62fc5cb71c51ff9c04b870e241bf8f2adde28b46554a03  construct_successors/helical_v10_capsule_parts/part-001.b64
0702feface0e886a246ab434571b4f092b08d3cf9cab562a17e38387e7ac7725  construct_successors/helical_v10_capsule_parts/part-002.b64
98d474a8f84da5145584b6b9ede0e224eab25fd23122ced6ab630dea243b7e4a  construct_successors/helical_v10_capsule_parts/part-003.b64
63413fc87e70ffb20a0bd8d8147f8753c5888434f010b98b53f29f1e0d7a8fbf  construct_successors/helical_v10_capsule_parts/part-004.b64
536de33319488137518d830cadbdc52517ac135588ce799a4e250b0447f44092  construct_successors/helical_v10_capsule_parts/part-005.b64
539730cb0bc7280eaf2aea577eeb83ec678c3336f21af66a3c5d1c52199aa6a3  construct_successors/helical_v10_capsule_parts/part-006.b64
PARTS
sha256sum -c "$RUNNER_TEMP/capsule/PARTS.sha256"
cat "$CAPSULE_PARTS_DIR"/part-{000..006}.b64 > "$RUNNER_TEMP/capsule/capsule.b64"
test "$(wc -c < "$RUNNER_TEMP/capsule/capsule.b64")" -eq "$CAPSULE_B64_BYTES"
test "$(sha256sum "$RUNNER_TEMP/capsule/capsule.b64" | awk '{print $1}')" = "$CAPSULE_B64_SHA256"
base64 -d "$RUNNER_TEMP/capsule/capsule.b64" > "$RUNNER_TEMP/capsule/capsule.tar.gz"
test "$(sha256sum "$RUNNER_TEMP/capsule/capsule.tar.gz" | awk '{print $1}')" = "$CAPSULE_ARCHIVE_SHA256"
tar -xzf "$RUNNER_TEMP/capsule/capsule.tar.gz" -C "$RUNNER_TEMP/capsule"
root="$RUNNER_TEMP/capsule/KCH_HELICAL_V10_REMOTE_EXECUTION_CAPSULE_2026-10-09"
test -f "$root/runtime/RUN_EXACT_BYTE_TO_BLIND_GATE_V0_9.py"
echo "root=$root" >> "$github_output"
python - "$receipts/CAPSULE_TRANSPORT_RECEIPT.json" <<'PY'
import json, os, pathlib, sys
body = {
    "format": "KCH_HELICAL_V0_10_CAPSULE_TRANSPORT",
    "capsule_parts": 7,
    "base64_bytes": 38012,
    "base64_sha256": os.environ["CAPSULE_B64_SHA256"],
    "archive_sha256": os.environ["CAPSULE_ARCHIVE_SHA256"],
    "outcome": "PASS",
    "authority_ceiling": "NONE",
}
pathlib.Path(sys.argv[1]).write_text(json.dumps(body, sort_keys=True, indent=2) + "\n")
PY

cat > "$RUNNER_TEMP/capsule/ACQUISITION_PATCH_PARTS.sha256" <<'PATCHPARTS'
5aa4d1bad23dcd89944d4869074bd1d4c2e07d4e3d5847c26c8a037c86f783ad  construct_successors/helical_v10_acquisition_patch/part-000.diff
323892119ef9cadb5f9063a0cffed0fb4f37fca308ca4ed82c1b946f8e1243bf  construct_successors/helical_v10_acquisition_patch/part-001.diff
PATCHPARTS
sha256sum -c "$RUNNER_TEMP/capsule/ACQUISITION_PATCH_PARTS.sha256"
cat "$ACQUISITION_PATCH_PARTS_DIR"/part-{000..001}.diff > "$RUNNER_TEMP/capsule/acquisition-successor.patch"
test "$(sha256sum "$RUNNER_TEMP/capsule/acquisition-successor.patch" | awk '{print $1}')" = "$ACQUISITION_PATCH_SHA256"
target="$root/runtime/ACQUIRE_EXACT_SOURCES_V0_9.py"
test "$(sha256sum "$target" | awk '{print $1}')" = "$ACQUISITION_PREDECESSOR_SHA256"
(cd "$root/runtime" && patch --batch --fuzz=0 -p0 < "$RUNNER_TEMP/capsule/acquisition-successor.patch")
test "$(sha256sum "$target" | awk '{print $1}')" = "$ACQUISITION_SUCCESSOR_SHA256"
python - "$receipts/ACQUISITION_TRANSPORT_SUCCESSOR_RECEIPT.json" <<'PY'
import json, os, pathlib, sys
body = {
    "format": "KCH_HELICAL_V0_10_ACQUISITION_TRANSPORT_SUCCESSOR",
    "scientific_protocol_mutated": False,
    "predecessor_sha256": os.environ["ACQUISITION_PREDECESSOR_SHA256"],
    "patch_sha256": os.environ["ACQUISITION_PATCH_SHA256"],
    "successor_sha256": os.environ["ACQUISITION_SUCCESSOR_SHA256"],
    "route": "MENDELEY_PUBLIC_API_FILE_LIST_AND_PROVIDER_DOWNLOAD_URL",
    "authority_ceiling": "NONE",
    "promotion": "BLOCKED",
}
pathlib.Path(sys.argv[1]).write_text(json.dumps(body, sort_keys=True, indent=2) + "\n")
PY

overlay="$GITHUB_WORKSPACE/$SANDBOX_OVERLAY_PATH"
sandbox_target="$root/runtime/RUN_HARDENED_PICKLE_EXTRACTION_V0_9.sh"
test "$(sha256sum "$overlay" | awk '{print $1}')" = "$SANDBOX_OVERLAY_SHA256"
test "$(sha256sum "$sandbox_target" | awk '{print $1}')" = "$SANDBOX_PREDECESSOR_SHA256"
install -m 0755 "$overlay" "$sandbox_target"
test "$(sha256sum "$sandbox_target" | awk '{print $1}')" = "$SANDBOX_OVERLAY_SHA256"
bash -n "$sandbox_target"
python - "$receipts/SANDBOX_SUCCESSOR_RECEIPT.json" <<'PY'
import json, os, pathlib, sys
body = {
    "format": "KCH_HELICAL_V0_10_DOCKER_SANDBOX_SUCCESSOR",
    "scientific_protocol_mutated": False,
    "predecessor_sha256": os.environ["SANDBOX_PREDECESSOR_SHA256"],
    "successor_sha256": os.environ["SANDBOX_OVERLAY_SHA256"],
    "predecessor_failure": "UNPRIVILEGED_USER_NAMESPACE_MAPPING_BLOCKED_ON_GITHUB_RUNNER",
    "successor_boundary": "DOCKER_NETWORK_NONE_READ_ONLY_CAPABILITIES_ZERO_NONROOT",
    "authority_ceiling": "NONE",
    "promotion": "BLOCKED",
}
pathlib.Path(sys.argv[1]).write_text(json.dumps(body, sort_keys=True, indent=2) + "\n")
PY
