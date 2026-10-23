from pathlib import Path
import hashlib
import json
import subprocess

from huggingface_hub import hf_hub_download, snapshot_download

MODEL_REPO = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
DATASET_REPO = "allenai/ai2_arc"
DATASET_REVISION = "210d026faf9955653af8916fad021475a3f00453"
DATASET_FILE = "ARC-Challenge/validation-00000-of-00001.parquet"

snapshot_download(repo_id=MODEL_REPO, revision=MODEL_REVISION, local_dir="model_snapshot")
hf_hub_download(
    repo_id=DATASET_REPO,
    repo_type="dataset",
    revision=DATASET_REVISION,
    filename=DATASET_FILE,
    local_dir="dataset_snapshot",
)

def manifest(root: str):
    rows = []
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return rows

payload = {
    "model_repo": MODEL_REPO,
    "model_revision": MODEL_REVISION,
    "dataset_repo": DATASET_REPO,
    "dataset_revision": DATASET_REVISION,
    "dataset_file": DATASET_FILE,
    "model_files": manifest("model_snapshot"),
    "dataset_files": manifest("dataset_snapshot"),
}
Path("EXACT_ASSET_MANIFEST.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
subprocess.run(
    [
        "tar",
        "--sort=name",
        "--mtime=@0",
        "--owner=0",
        "--group=0",
        "--numeric-owner",
        "-cf",
        "exact_qwen_arc_assets.tar",
        "model_snapshot",
        "dataset_snapshot",
        "EXACT_ASSET_MANIFEST.json",
    ],
    check=True,
)
subprocess.run(["sha256sum", "exact_qwen_arc_assets.tar"], check=True, stdout=open("exact_qwen_arc_assets.tar.sha256", "w"))
subprocess.run(["split", "-b", "250M", "-d", "-a", "2", "exact_qwen_arc_assets.tar", "qwen_arc.part."], check=True)
with open("qwen_arc.parts.sha256", "w") as handle:
    subprocess.run(["sha256sum", *[str(p) for p in sorted(Path('.').glob('qwen_arc.part.*'))]], check=True, stdout=handle)
