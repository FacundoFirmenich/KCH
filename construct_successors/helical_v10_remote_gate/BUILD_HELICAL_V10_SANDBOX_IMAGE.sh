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
mkdir -p "$receipts"
root="$RUNNER_TEMP/sandbox-image"
rm -rf "$root"
mkdir -p "$root/wheels"

docker pull --platform=linux/amd64 "$SANDBOX_BASE_REPO_DIGEST"
test "$(docker image inspect --format '{{.Id}}' "$SANDBOX_BASE_REPO_DIGEST")" = "$SANDBOX_BASE_IMAGE_ID"
python -m pip download \
  --disable-pip-version-check \
  --only-binary=:all: \
  --no-deps \
  --platform manylinux_2_17_x86_64 \
  --implementation cp \
  --python-version 311 \
  --abi cp311 \
  --dest "$root/wheels" \
  numpy==2.1.3
wheel="$root/wheels/$NUMPY_WHEEL_FILENAME"
test -f "$wheel"
test "$(sha256sum "$wheel" | awk '{print $1}')" = "$NUMPY_WHEEL_SHA256"
cat > "$root/Dockerfile" <<'DOCKERFILE'
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY wheels/ /wheels/
RUN python -m pip install --disable-pip-version-check --no-index --no-deps /wheels/*.whl \
    && python -m pip check \
    && python -c 'import numpy; assert numpy.__version__ == "2.1.3"' \
    && rm -rf /wheels /root/.cache
USER 65534:65534
WORKDIR /tmp
DOCKERFILE
dockerfile_sha="$(sha256sum "$root/Dockerfile" | awk '{print $1}')"
tag="kch-helical-v10-sandbox:${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
docker build \
  --pull=false \
  --no-cache \
  --network=none \
  --build-arg "BASE_IMAGE=$SANDBOX_BASE_REPO_DIGEST" \
  --tag "$tag" \
  "$root"
image_id="$(docker image inspect --format '{{.Id}}' "$tag")"
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]]

docker run --rm --platform linux/amd64 --network none --read-only \
  --cap-drop ALL --security-opt no-new-privileges:true --user 65534:65534 \
  --entrypoint /usr/bin/env "$image_id" -i PATH=/usr/local/bin:/usr/bin:/bin \
  /usr/local/bin/python -c 'import numpy; assert numpy.__version__ == "2.1.3"'
pip_freeze="$(docker run --rm --platform linux/amd64 --network none --read-only \
  --cap-drop ALL --security-opt no-new-privileges:true --user 65534:65534 \
  --entrypoint /usr/bin/env "$image_id" -i PATH=/usr/local/bin:/usr/bin:/bin \
  /usr/local/bin/python -m pip freeze --all | LC_ALL=C sort)"
printf '%s\n' "$pip_freeze" > "$receipts/SANDBOX_IMAGE_PIP_FREEZE.txt"
python - "$receipts/SANDBOX_IMAGE_BUILD_RECEIPT.json" "$image_id" "$dockerfile_sha" <<'PY'
import hashlib, json, os, pathlib, sys
path = pathlib.Path(sys.argv[1])
freeze = (path.parent / "SANDBOX_IMAGE_PIP_FREEZE.txt").read_bytes()
body = {
    "format": "KCH_HELICAL_V0_10_SANDBOX_IMAGE_BUILD",
    "platform": "linux/amd64",
    "base_repo_digest": os.environ["SANDBOX_BASE_REPO_DIGEST"],
    "base_image_id": os.environ["SANDBOX_BASE_IMAGE_ID"],
    "numpy_wheel_filename": os.environ["NUMPY_WHEEL_FILENAME"],
    "numpy_wheel_sha256": os.environ["NUMPY_WHEEL_SHA256"],
    "dockerfile_sha256": sys.argv[3],
    "built_image_id": sys.argv[2],
    "pip_freeze_sha256": hashlib.sha256(freeze).hexdigest(),
    "parent_environment_freeze_receipt_id": os.environ["SANDBOX_ENV_FREEZE_RECEIPT_ID"],
    "parent_environment_freeze_receipt_sha256": os.environ["SANDBOX_ENV_FREEZE_RECEIPT_SHA256"],
    "build_network_mode": "none",
    "execution_network_mode": "none",
    "authority_ceiling": "NONE",
    "promotion": "BLOCKED",
}
canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
body["receipt_id"] = "h10sandboximage:" + hashlib.sha256(canonical).hexdigest()
path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")
PY
receipt_sha="$(sha256sum "$receipts/SANDBOX_IMAGE_BUILD_RECEIPT.json" | awk '{print $1}')"
echo "image_id=$image_id" >> "$github_output"
echo "receipt_sha=$receipt_sha" >> "$github_output"
