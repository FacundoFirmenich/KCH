#!/usr/bin/env bash
set -euo pipefail

usage(){
  echo "Usage: $0 --input FILE --expected-sha256 HEX --output-dir EMPTY_DIR [--memory-mib N] [--timeout-seconds N]" >&2
  exit 64
}

input=""; expected=""; output=""; memory_mib=8192; timeout_seconds=2700; output_limit_mib=4096
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
for value in "$memory_mib" "$timeout_seconds" "$output_limit_mib"; do
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || { echo "invalid numeric limit" >&2; exit 64; }
done
(( memory_mib >= 1024 && memory_mib <= 32768 )) || { echo "memory limit outside 1024..32768 MiB" >&2; exit 64; }

for tool in docker timeout sha256sum readlink find stat chmod python; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool" >&2; exit 69; }
done
[[ -f "$input" && ! -L "$input" ]] || { echo "input must be a regular non-symlink file" >&2; exit 66; }
mkdir -p "$output"
[[ -d "$output" && ! -L "$output" ]] || { echo "output must be a non-symlink directory" >&2; exit 66; }
if find "$output" -mindepth 1 -print -quit | grep -q .; then
  echo "output directory must be empty" >&2
  exit 73
fi

image=${KCH_DOCKER_SANDBOX_IMAGE:-}
image_repo_digest=${KCH_DOCKER_SANDBOX_IMAGE_REPO_DIGEST:-}
environment_receipt_sha256=${KCH_DOCKER_SANDBOX_ENV_RECEIPT_SHA256:-}
[[ -n "$image" && "$image" =~ ^sha256:[0-9a-f]{64}$ ]] || {
  echo "KCH_DOCKER_SANDBOX_IMAGE must be an immutable sha256 image ID" >&2
  exit 69
}
[[ -n "$image_repo_digest" && "$image_repo_digest" == *@sha256:* ]] || {
  echo "KCH_DOCKER_SANDBOX_IMAGE_REPO_DIGEST must be an immutable repo digest" >&2
  exit 69
}
[[ "$environment_receipt_sha256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "KCH_DOCKER_SANDBOX_ENV_RECEIPT_SHA256 must be a SHA-256" >&2
  exit 69
}
observed_image_id=$(docker image inspect --format '{{.Id}}' "$image")
[[ "$observed_image_id" == "$image" ]] || { echo "sandbox image ID mismatch" >&2; exit 69; }

base=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
input=$(readlink -f "$input")
output=$(readlink -f "$output")
base=$(readlink -f "$base")
[[ "$input" != "$output"/* && "$base" != "$output"/* ]] || {
  echo "output may not contain input or support" >&2; exit 65;
}
input_sha=$(sha256sum "$input" | awk '{print $1}')
[[ "$input_sha" == "$expected" ]] || { echo "input SHA-256 mismatch before sandbox" >&2; exit 65; }
program="$base/HARDENED_PICKLE_EXTRACTION_V0_9.py"
verifier="$base/VERIFY_SAFE_NPZ_V0_9.py"
[[ -f "$program" && -f "$verifier" ]] || { echo "sandbox program/verifier missing" >&2; exit 69; }
program_sha=$(sha256sum "$program" | awk '{print $1}')
verifier_sha=$(sha256sum "$verifier" | awk '{print $1}')

scratch=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/kch-helical-v10-docker.XXXXXXXX")
cidfile="$scratch/container.cid"
original_mode=$(stat -c '%a' "$output")
container_name="kch-helical-v10-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-0}-$$"
cleanup(){
  if [[ -s "$cidfile" ]]; then
    docker rm -f "$(cat "$cidfile")" >/dev/null 2>&1 || true
  else
    docker rm -f "$container_name" >/dev/null 2>&1 || true
  fi
  chmod "$original_mode" "$output" >/dev/null 2>&1 || true
  rm -rf "$scratch"
}
trap cleanup EXIT INT TERM
chmod 0777 "$output"

set +e
timeout --signal=TERM --kill-after=15s "${timeout_seconds}s" \
  docker run \
    --name "$container_name" \
    --cidfile "$cidfile" \
    --rm \
    --platform linux/amd64 \
    --network none \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --pids-limit 64 \
    --memory "${memory_mib}m" \
    --memory-swap "${memory_mib}m" \
    --cpus 2.0 \
    --ulimit nofile=96:96 \
    --ulimit nproc=64:64 \
    --ulimit fsize="$((output_limit_mib * 1024 * 1024)):$((output_limit_mib * 1024 * 1024))" \
    --ipc none \
    --pid private \
    --cgroupns private \
    --shm-size 16m \
    --user 65534:65534 \
    --hostname kch-helical-sandbox \
    --workdir /tmp \
    --tmpfs /tmp:rw,noexec,nosuid,nodev,size=268435456,mode=1777 \
    --mount "type=bind,src=$input,dst=/in/source,readonly" \
    --mount "type=bind,src=$base,dst=/app/support,readonly" \
    --mount "type=bind,src=$output,dst=/out" \
    --entrypoint /usr/bin/env \
    "$image" \
    -i \
    PATH=/usr/local/bin:/usr/bin:/bin \
    PYTHONPATH=/app/support \
    HOME=/nonexistent \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONNOUSERSITE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    /usr/local/bin/python \
    /app/support/HARDENED_PICKLE_EXTRACTION_V0_9.py \
    --input /in/source \
    --expected-sha256 "$expected" \
    --output-dir /out
rc=$?
set -e
chmod "$original_mode" "$output"

violation=""
if find "$output" -mindepth 1 ! -type f -print -quit | grep -q .; then
  violation="NON_REGULAR_OUTPUT_OBJECT"
fi
file_count=$(find "$output" -mindepth 1 -maxdepth 1 -type f | wc -l | tr -d ' ')
total_bytes=$(find "$output" -mindepth 1 -maxdepth 1 -type f -printf '%s\n' | awk '{s+=$1} END{print s+0}')
if (( file_count > 100 )); then violation="OUTPUT_FILE_COUNT_LIMIT_EXCEEDED"; fi
if (( total_bytes > output_limit_mib * 1024 * 1024 )); then violation="OUTPUT_BYTE_LIMIT_EXCEEDED"; fi
reserved="$output/SANDBOX_EXECUTION_RECEIPT_V0_9.json"
if [[ -e "$reserved" ]]; then violation="RESERVED_RECEIPT_COLLISION"; fi

python - "$reserved" "$input_sha" "$program_sha" "$verifier_sha" "$rc" "$timeout_seconds" "$memory_mib" "$output_limit_mib" "$file_count" "$total_bytes" "$violation" "$output" "$image" "$image_repo_digest" "$environment_receipt_sha256" <<'PY'
import hashlib, json, pathlib, sys
receipt_path = pathlib.Path(sys.argv[1])
out_dir = pathlib.Path(sys.argv[12])
files = []
for path in sorted(out_dir.iterdir(), key=lambda p: p.name):
    if path.name == receipt_path.name or not path.is_file() or path.is_symlink():
        continue
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    files.append({"name": path.name, "bytes": path.stat().st_size, "sha256": h.hexdigest()})
body = {
    "format": "KCH_HELICAL_V0_10_DOCKER_NETWORKLESS_SANDBOX_EXECUTION_RECEIPT",
    "input_sha256": sys.argv[2],
    "program_sha256": sys.argv[3],
    "host_verifier_sha256": sys.argv[4],
    "program_exit_code": int(sys.argv[5]),
    "timeout_seconds": int(sys.argv[6]),
    "memory_limit_mib": int(sys.argv[7]),
    "output_limit_mib": int(sys.argv[8]),
    "output_file_count_before_receipt": int(sys.argv[9]),
    "output_bytes_before_receipt": int(sys.argv[10]),
    "violation": sys.argv[11] or None,
    "outputs": files,
    "container_image_id": sys.argv[13],
    "container_base_repo_digest": sys.argv[14],
    "sandbox_environment_receipt_sha256": sys.argv[15],
    "controls": {
        "container_runtime": "docker",
        "linux_platform": "amd64",
        "network_mode_none": True,
        "read_only_root_filesystem": True,
        "input_bind_read_only": True,
        "support_bind_read_only": True,
        "output_only_persistent_writable_bind": True,
        "tmp_ephemeral_tmpfs_noexec_nosuid_nodev": True,
        "private_pid_namespace": True,
        "proc_visible_only_inside_private_pid_namespace": True,
        "ipc_none": True,
        "host_docker_socket_not_mounted": True,
        "host_devices_not_mounted": True,
        "minimal_container_devices_only": True,
        "environment_allowlist_only": True,
        "host_environment_not_forwarded": True,
        "known_secret_names_not_forwarded": True,
        "no_new_privileges": True,
        "capabilities_dropped_all": True,
        "non_root_uid_gid": "65534:65534",
        "default_docker_seccomp_profile": True,
        "resource_limits": True,
    },
    "authority_ceiling": "NONE",
    "promotion": "BLOCKED",
}
body["status"] = "PASS" if body["program_exit_code"] == 0 and body["violation"] is None else "FAIL_CLOSED"
canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
body["receipt_id"] = "h10sandbox:" + hashlib.sha256(canonical).hexdigest()
receipt_path.write_text(json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
PY

if [[ -n "$violation" || $rc -ne 0 ]]; then
  exit 74
fi

"$(command -v python)" "$verifier" \
  --npz "$output/blind_columns.npz" \
  --extraction-receipt "$output/EXTRACTION_RECEIPT_V0_9.json" \
  --output "$output/SAFE_NPZ_VERIFICATION_RECEIPT_V0_9.json"
