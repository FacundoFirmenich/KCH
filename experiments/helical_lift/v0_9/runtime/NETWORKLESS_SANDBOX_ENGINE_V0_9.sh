#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: NETWORKLESS_SANDBOX_ENGINE_V0_9.sh \
  --input FILE --program PYTHON_FILE --support-dir DIR --output-dir EMPTY_DIR \
  [--timeout-seconds N] [--memory-mib N] [--output-limit-mib N] -- [PROGRAM_ARGS...]
EOF
  exit 64
}

input=""; program=""; support_dir=""; output_dir=""
timeout_seconds=2700; memory_mib=8192; output_limit_mib=4096
while (($#)); do
  case "$1" in
    --input) input=${2-}; shift 2 ;;
    --program) program=${2-}; shift 2 ;;
    --support-dir) support_dir=${2-}; shift 2 ;;
    --output-dir) output_dir=${2-}; shift 2 ;;
    --timeout-seconds) timeout_seconds=${2-}; shift 2 ;;
    --memory-mib) memory_mib=${2-}; shift 2 ;;
    --output-limit-mib) output_limit_mib=${2-}; shift 2 ;;
    --) shift; break ;;
    *) usage ;;
  esac
done
program_args=("$@")
[[ -n "$input" && -n "$program" && -n "$support_dir" && -n "$output_dir" ]] || usage
for value in "$timeout_seconds" "$memory_mib" "$output_limit_mib"; do
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || { echo "invalid numeric limit" >&2; exit 64; }
done
(( memory_mib >= 1024 && memory_mib <= 32768 )) || { echo "memory limit outside 1024..32768 MiB" >&2; exit 64; }
(( output_limit_mib >= 64 && output_limit_mib <= 16384 )) || { echo "output limit outside 64..16384 MiB" >&2; exit 64; }
for tool in unshare mount chroot setpriv timeout sha256sum readlink find python; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool" >&2; exit 69; }
done
[[ -f "$input" && ! -L "$input" ]] || { echo "input must be a regular non-symlink file" >&2; exit 66; }
[[ -f "$program" && ! -L "$program" ]] || { echo "program must be a regular non-symlink file" >&2; exit 66; }
[[ -d "$support_dir" && ! -L "$support_dir" ]] || { echo "support-dir must be a non-symlink directory" >&2; exit 66; }
mkdir -p "$output_dir"
input=$(readlink -f "$input")
program=$(readlink -f "$program")
support_dir=$(readlink -f "$support_dir")
output_dir=$(readlink -f "$output_dir")
[[ "$input" != "$output_dir"/* && "$program" != "$output_dir"/* && "$support_dir" != "$output_dir"/* ]] || {
  echo "output may not contain input/program/support" >&2; exit 65;
}
if find "$output_dir" -mindepth 1 -print -quit | grep -q .; then
  echo "output directory must be empty" >&2
  exit 73
fi

input_sha=$(sha256sum "$input" | awk '{print $1}')
program_sha=$(sha256sum "$program" | awk '{print $1}')
python_bin=$(readlink -f "$(command -v python)")
python_prefix=""
case "$python_bin" in
  /usr/*) python_inside="$python_bin" ;;
  /opt/*)
    python_prefix=$(awk -F/ '{print "/"$2"/"$3}' <<<"$python_bin")
    python_inside="$python_bin"
    ;;
  *) echo "unsupported Python location: $python_bin" >&2; exit 69 ;;
esac

scratch=$(mktemp -d "${TMPDIR:-/tmp}/kch-helical-v09-sandbox.XXXXXXXX")
root="$scratch/root"
mkdir -p "$root"
cleanup() { rm -rf "$scratch"; }
trap cleanup EXIT INT TERM

set +e
unshare --user --map-root-user --mount --net --pid --fork bash -s -- \
  "$root" "$input" "$program" "$support_dir" "$output_dir" "$timeout_seconds" "$memory_mib" "$output_limit_mib" "$python_inside" "$python_prefix" "${program_args[@]}" <<'INNER'
set -euxo pipefail
root=$1; host_input=$2; host_program=$3; host_support=$4; host_output=$5
timeout_seconds=$6; memory_mib=$7; output_limit_mib=$8; python_inside=$9; python_prefix=${10}
shift 10
program_args=("$@")
mount --make-rprivate /
mount -t tmpfs -o size=256m,nosuid,nodev,noexec tmpfs "$root"
mkdir -p "$root/usr" "$root/in" "$root/out" "$root/app" "$root/app/support" "$root/tmp" "$root/opt"

mount --rbind /usr "$root/usr"
mount -o remount,ro,bind "$root/usr"
if [[ -n "$python_prefix" && "$python_prefix" != "/usr" ]]; then
  mkdir -p "$root$python_prefix"
  mount --rbind "$python_prefix" "$root$python_prefix"
  mount -o remount,ro,bind "$root$python_prefix"
fi
if [[ -d /opt/python-hooks ]]; then
  mkdir -p "$root/opt/python-hooks"
  mount --rbind /opt/python-hooks "$root/opt/python-hooks"
  mount -o remount,ro,bind "$root/opt/python-hooks"
fi
ln -s usr/bin "$root/bin"
ln -s usr/lib "$root/lib"
ln -s usr/lib64 "$root/lib64"

touch "$root/in/source" "$root/app/program.py"
mount --bind "$host_input" "$root/in/source"
mount -o remount,ro,bind "$root/in/source"
mount --bind "$host_program" "$root/app/program.py"
mount -o remount,ro,bind "$root/app/program.py"
mount --rbind "$host_support" "$root/app/support"
mount -o remount,ro,bind "$root/app/support"
mount --bind "$host_output" "$root/out"
mount -o remount,rw,bind,nosuid,nodev "$root/out"
chmod 0555 "$root" "$root/in" "$root/app" "$root/tmp"
mount -o remount,ro,nosuid,nodev,noexec tmpfs "$root"

ulimit -t "$timeout_seconds"
ulimit -n 96
ulimit -u 64
ulimit -v "$((memory_mib * 1024))"
ulimit -f "$((output_limit_mib * 1024))"

chroot "$root" /usr/bin/env -i \
  PATH=/opt/pyvenv/bin:/usr/bin:/bin \
  PYTHONPATH=/app/support \
  HOME=/nonexistent \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /usr/bin/timeout --signal=KILL "${timeout_seconds}s" \
  /usr/bin/setpriv --no-new-privs --bounding-set=-all --inh-caps=-all --ambient-caps=-all \
  "$python_inside" /app/program.py "${program_args[@]}"
INNER
rc=$?
set -e

violation=""
if find "$output_dir" -mindepth 1 ! -type f -print -quit | grep -q .; then
  violation="NON_REGULAR_OUTPUT_OBJECT"
fi
file_count=$(find "$output_dir" -mindepth 1 -maxdepth 1 -type f | wc -l | tr -d ' ')
total_bytes=$(find "$output_dir" -mindepth 1 -maxdepth 1 -type f -printf '%s\n' | awk '{s+=$1} END{print s+0}')
if (( file_count > 100 )); then violation="OUTPUT_FILE_COUNT_LIMIT_EXCEEDED"; fi
if (( total_bytes > output_limit_mib * 1024 * 1024 )); then violation="OUTPUT_BYTE_LIMIT_EXCEEDED"; fi
reserved="$output_dir/SANDBOX_EXECUTION_RECEIPT_V0_9.json"
if [[ -e "$reserved" ]]; then violation="RESERVED_RECEIPT_COLLISION"; fi

python - "$reserved" "$input_sha" "$program_sha" "$rc" "$timeout_seconds" "$memory_mib" "$output_limit_mib" "$file_count" "$total_bytes" "$violation" "$output_dir" <<'PY'
import hashlib, json, pathlib, sys
receipt_path = pathlib.Path(sys.argv[1])
out_dir = pathlib.Path(sys.argv[11])
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
    "format": "KCH_HELICAL_V0_9_NETWORKLESS_SANDBOX_EXECUTION_RECEIPT",
    "input_sha256": sys.argv[2],
    "program_sha256": sys.argv[3],
    "program_exit_code": int(sys.argv[4]),
    "timeout_seconds": int(sys.argv[5]),
    "memory_limit_mib": int(sys.argv[6]),
    "output_limit_mib": int(sys.argv[7]),
    "output_file_count_before_receipt": int(sys.argv[8]),
    "output_bytes_before_receipt": int(sys.argv[9]),
    "violation": sys.argv[10] or None,
    "outputs": files,
    "controls": {
        "new_user_namespace": True,
        "new_mount_namespace": True,
        "new_network_namespace_loopback_down": True,
        "new_pid_namespace": True,
        "tmpfs_root_read_only_before_exec": True,
        "input_bind_read_only": True,
        "program_bind_read_only": True,
        "support_bind_read_only": True,
        "output_only_writable_bind": True,
        "proc_not_mounted": True,
        "dev_not_mounted": True,
        "environment_reset": True,
        "known_secret_names_removed_with_environment_reset": True,
        "no_new_privileges": True,
        "capability_bounding_set_dropped": True,
        "resource_limits": True,
    },
    "authority_ceiling": "NONE",
}
body["status"] = "PASS" if body["program_exit_code"] == 0 and body["violation"] is None else "FAIL_CLOSED"
canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
body["receipt_id"] = "h9sandbox:" + hashlib.sha256(canonical).hexdigest()
receipt_path.write_text(json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
PY

if [[ -n "$violation" || $rc -ne 0 ]]; then
  exit 74
fi
