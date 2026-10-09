#!/usr/bin/env bash
set -euo pipefail
base=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work=${1:-"$base/work"}
rm -rf "$work"
mkdir -p "$work/acquisition" "$work/extraction" "$work/final" "$work/runtime"

write_blocked_final() {
  local outcome=$1
  local stage=$2
  local rc=$3
  local pickle_destroyed=${4:-false}
  python - "$work" "$outcome" "$stage" "$rc" "$pickle_destroyed" <<'PY'
import hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1]); outcome=sys.argv[2]; stage=sys.argv[3]; rc=int(sys.argv[4]); destroyed=sys.argv[5].lower()=="true"
body={
  "format":"KCH_HELICAL_V0_9_REMOTE_FINAL_GATE",
  "outcome":outcome,
  "blocked_stage":stage,
  "stage_exit_code":rc,
  "extraction_performed":stage not in {"HOST_PREPARATION","EXACT_BYTE_ACQUISITION","CONTAINER_BUILD"},
  "blind_eligibility_performed":False,
  "source_pickle_destroyed_after_boundary":destroyed,
  "scientific_model_fitting_performed":False,
  "physical_helicity_evaluated":False,
  "promotion":"BLOCKED",
  "canonicalization":"BLOCKED",
  "authority_ceiling":"NONE",
}
body["receipt_id"]="h9final:"+hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
(root/"final"/"FINAL_GATE_V0_9.json").write_text(json.dumps(body,indent=2,sort_keys=True,allow_nan=False)+"\n")
PY
}

set +e
python -m pip install --disable-pip-version-check -r "$base/requirements-host.txt" > "$work/runtime/pip-install.txt" 2>&1
host_rc=$?
set -e
if [[ $host_rc -ne 0 ]]; then
  write_blocked_final "BLOCKED_HOST_PREPARATION" "HOST_PREPARATION" "$host_rc" false
  exit 0
fi
python -m pip freeze --all | LC_ALL=C sort > "$work/runtime/pip-freeze.txt"
python --version > "$work/runtime/python-version.txt" 2>&1
docker version > "$work/runtime/docker-version.txt" 2>&1 || true

set +e
python "$base/acquire_public_exact.py" --output-dir "$work/acquisition" > "$work/runtime/acquisition.stdout.json" 2> "$work/runtime/acquisition.stderr.txt"
acq_rc=$?
set -e
if [[ $acq_rc -ne 0 ]]; then
  write_blocked_final "BLOCKED_EXACT_BYTE_ACQUISITION" "EXACT_BYTE_ACQUISITION" "$acq_rc" false
  exit 0
fi

mechanism="$work/acquisition/data/focmec_ca_final.pickle"
fault="$work/acquisition/data/gem_active_faults_harmonized.geojson"
acq_receipt="$work/acquisition/receipts/ACQUISITION_RECEIPT_V0_9.json"
mechanism_sha=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["mechanism_receipt"]["sha256"])' "$acq_receipt")

image="kch-helical-extractor:v0.9-${GITHUB_SHA:-local}"
set +e
docker build --pull --no-cache -f "$base/Dockerfile.extract" -t "$image" "$base" > "$work/runtime/docker-build.txt" 2>&1
build_rc=$?
set -e
if [[ $build_rc -ne 0 ]]; then
  rm -f "$mechanism"
  write_blocked_final "BLOCKED_PICKLE_SANDBOX_BUILD" "CONTAINER_BUILD" "$build_rc" true
  exit 0
fi
docker image inspect "$image" > "$work/runtime/docker-image-inspect.json"
chmod 0777 "$work/extraction"
set +e
docker run --rm \
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --pids-limit 64 --memory 6g --cpus 2 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=256m \
  -v "$mechanism:/in/source:ro" \
  -v "$work/extraction:/out:rw" \
  "$image" --input /in/source --expected-sha256 "$mechanism_sha" --output-dir /out \
  > "$work/runtime/extraction.stdout.json" 2> "$work/runtime/extraction.stderr.txt"
ext_rc=$?
set -e
rm -f "$mechanism"
if [[ $ext_rc -ne 0 ]]; then
  write_blocked_final "BLOCKED_PICKLE_SANDBOX" "PICKLE_EXTRACTION" "$ext_rc" true
  exit 0
fi

set +e
python "$base/eligibility.py" \
  --protocol "$base/HELICAL_DYNAMIC_MARKED_POINT_PROCESS_GATE_V0_8_LOCKED.json" \
  --safe-npz "$work/extraction/blind_columns.npz" \
  --extraction-receipt "$work/extraction/EXTRACTION_RECEIPT_V0_9.json" \
  --acquisition-receipt "$acq_receipt" \
  --fault-geojson "$fault" \
  --output "$work/final/BLIND_ELIGIBILITY_RESULT_V0_9.json" \
  > "$work/runtime/eligibility.stdout.json" 2> "$work/runtime/eligibility.stderr.txt"
elig_rc=$?
set -e
if [[ $elig_rc -ne 0 ]]; then
  write_blocked_final "BLOCKED_BLIND_ELIGIBILITY_RUNTIME" "BLIND_ELIGIBILITY" "$elig_rc" true
  exit 0
fi

python - "$work" <<'PY'
import hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1])
elig=json.loads((root/"final"/"BLIND_ELIGIBILITY_RESULT_V0_9.json").read_text())
body={
  "format":"KCH_HELICAL_V0_9_REMOTE_FINAL_GATE",
  "outcome":elig["outcome"],
  "eligibility_result_id":elig["eligibility_result_id"],
  "directional_unsealing_authorized":elig["directional_unsealing_authorized"],
  "scientific_model_fitting_performed":False,
  "physical_helicity_evaluated":False,
  "source_pickle_destroyed_after_boundary":True,
  "promotion":"BLOCKED","canonicalization":"BLOCKED","authority_ceiling":"NONE",
}
body["receipt_id"]="h9final:"+hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
(root/"final"/"FINAL_GATE_V0_9.json").write_text(json.dumps(body,indent=2,sort_keys=True,allow_nan=False)+"\n")
PY
