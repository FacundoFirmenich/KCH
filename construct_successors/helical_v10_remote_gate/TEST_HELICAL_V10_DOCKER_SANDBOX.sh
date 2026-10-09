#!/usr/bin/env bash
set -euo pipefail
usage(){ echo "Usage: $0 --capsule-root DIR --image-id SHA256 --image-receipt-sha SHA256 --receipts DIR" >&2; exit 64; }
capsule_root=""; image_id=""; image_receipt_sha=""; receipts=""
while (($#)); do
  case "$1" in
    --capsule-root) capsule_root=${2-}; shift 2;;
    --image-id) image_id=${2-}; shift 2;;
    --image-receipt-sha) image_receipt_sha=${2-}; shift 2;;
    --receipts) receipts=${2-}; shift 2;;
    *) usage;;
  esac
done
[[ -n "$capsule_root" && -n "$image_id" && -n "$image_receipt_sha" && -n "$receipts" ]] || usage
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ && "$image_receipt_sha" =~ ^[0-9a-f]{64}$ ]] || usage
mkdir -p "$receipts"

input="$capsule_root/source_lock/HELICAL_DYNAMIC_MARKED_POINT_PROCESS_GATE_V0_8_LOCKED.json"
out="$RUNNER_TEMP/hostile-sandbox"
rm -rf "$out"
mkdir -p "$out"
expected="$(sha256sum "$input" | awk '{print $1}')"
set +e
KCH_DOCKER_SANDBOX_IMAGE="$image_id" \
KCH_DOCKER_SANDBOX_IMAGE_REPO_DIGEST="$SANDBOX_BASE_REPO_DIGEST" \
KCH_DOCKER_SANDBOX_ENV_RECEIPT_SHA256="$image_receipt_sha" \
  bash "$capsule_root/runtime/RUN_HARDENED_PICKLE_EXTRACTION_V0_9.sh" \
    --input "$input" --expected-sha256 "$expected" --output-dir "$out" \
    --memory-mib 2048 --timeout-seconds 300
rc=$?
set -e
test "$rc" -eq 74
test ! -e "$out/blind_columns.npz"
python - "$out/SANDBOX_EXECUTION_RECEIPT_V0_9.json" "$receipts/HOSTILE_SANDBOX_RECEIPT.json" <<'PY'
import json, pathlib, shutil, sys
source = pathlib.Path(sys.argv[1])
body = json.loads(source.read_text())
assert body["status"] == "FAIL_CLOSED"
assert body["program_exit_code"] != 0
assert body["controls"]["network_mode_none"] is True
assert body["controls"]["capabilities_dropped_all"] is True
shutil.copy2(source, sys.argv[2])
PY
rm -rf "$out"

selftest="$RUNNER_TEMP/docker-selftest"
rm -rf "$selftest"
mkdir -p "$selftest"
chmod 0777 "$selftest"
docker run --rm -i --platform linux/amd64 \
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --pids-limit 32 --memory 512m --memory-swap 512m --cpus 1.0 \
  --ipc none --pid private --cgroupns private --shm-size 8m \
  --user 65534:65534 --workdir /tmp \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=33554432,mode=1777 \
  --mount "type=bind,src=$input,dst=/in/source,readonly" \
  --mount "type=bind,src=$selftest,dst=/out" \
  --entrypoint /usr/bin/env "$image_id" \
  -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/nonexistent \
  /usr/local/bin/python - <<'PY'
import json, os, pathlib, socket
result = {
    "uid": os.getuid(),
    "gid": os.getgid(),
    "network_connect_denied": False,
    "root_write_denied": False,
    "input_write_denied": False,
    "effective_capabilities_zero": False,
    "host_environment_absent": "GITHUB_TOKEN" not in os.environ and "ACTIONS_ID_TOKEN_REQUEST_TOKEN" not in os.environ,
}
try:
    socket.create_connection(("1.1.1.1", 53), timeout=1)
except OSError:
    result["network_connect_denied"] = True
try:
    pathlib.Path("/forbidden").write_text("x")
except OSError:
    result["root_write_denied"] = True
try:
    pathlib.Path("/in/source").write_text("x")
except OSError:
    result["input_write_denied"] = True
status = pathlib.Path("/proc/self/status").read_text()
cap_eff = next(line.split()[1] for line in status.splitlines() if line.startswith("CapEff:"))
result["effective_capabilities_zero"] = int(cap_eff, 16) == 0
result["pass"] = all([
    result["uid"] == 65534,
    result["gid"] == 65534,
    result["network_connect_denied"],
    result["root_write_denied"],
    result["input_write_denied"],
    result["effective_capabilities_zero"],
    result["host_environment_absent"],
])
pathlib.Path("/out/CONTROL_SELFTEST.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
raise SystemExit(0 if result["pass"] else 1)
PY
chmod 0755 "$selftest"
python - "$selftest/CONTROL_SELFTEST.json" "$receipts/DOCKER_CONFINEMENT_SELFTEST.json" <<'PY'
import json, pathlib, shutil, sys
source = pathlib.Path(sys.argv[1])
body = json.loads(source.read_text())
assert body["pass"] is True
shutil.copy2(source, sys.argv[2])
PY
rm -rf "$selftest"
