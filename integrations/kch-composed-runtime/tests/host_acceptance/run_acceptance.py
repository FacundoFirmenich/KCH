"""Reproduce pinned original-host client acceptance in a dedicated work directory.

Downloads public upstream code and locked dependencies; runs no model or user
host. Existing upstream checkouts must match the recorded pin and be unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


PINS = {
    "qwenpaw": ("https://github.com/agentscope-ai/QwenPaw.git", "7147731d582fdd106af6ca7e3a3a5dc650183755"),
    "openclaw": ("https://github.com/openclaw/openclaw.git", "c9a0c00b8691bda5bd7a38ee494b5edd8ecb9254"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--host", choices=("both", "qwenpaw", "openclaw"), default="both")
    args = parser.parse_args()
    root, repository = args.work.resolve(), args.repository.resolve(strict=True)
    scripts = Path(__file__).resolve().parent
    if root == repository or root.is_relative_to(repository):
        parser.error("Use a dedicated work directory outside the source repository")
    root.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    commands = []

    def run(label, argv, *, cwd=root, env=None, timeout=600):
        commands.append({"label": label, "argv": [str(x) for x in argv], "cwd": str(cwd)})
        with (root / "logs" / (label + ".log")).open("w") as stream:
            completed = subprocess.run([str(x) for x in argv], cwd=cwd, env=env,
                                       stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        (root / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if completed.returncode:
            raise RuntimeError(f"{label} failed; inspect {root / 'logs' / (label + '.log')}")

    hosts = tuple(PINS) if args.host == "both" else (args.host,)
    for host in hosts:
        url, pin = PINS[host]
        checkout = root / "upstream" / host
        if not checkout.exists():
            checkout.mkdir(parents=True)
            run(host + "-init", ["git", "init", checkout])
            run(host + "-remote", ["git", "remote", "add", "origin", url], cwd=checkout)
            run(host + "-fetch", ["git", "fetch", "--depth=1", "origin", pin], cwd=checkout)
            run(host + "-checkout", ["git", "checkout", "--detach", "FETCH_HEAD"], cwd=checkout)
        observed = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
        if observed != pin:
            raise RuntimeError(f"{host} checkout differs from pinned source; choose a fresh work directory")
        if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=checkout):
            raise RuntimeError(f"{host} tracked source has changes; acceptance requires unchanged source")
    venv = root / "venv"
    if not venv.exists():
        run("venv", [sys.executable, "-m", "venv", venv])
    python = venv / "bin/python"
    run("python-dependencies", [python, "-m", "pip", "install", "-r", scripts / "requirements-qwenpaw.txt"])
    if "qwenpaw" in hosts:
        run("qwenpaw-acceptance", [python, scripts / "qwenpaw_acceptance.py",
            "--repository", repository, "--upstream", root / "upstream/qwenpaw",
            "--output", root / "qwenpaw-acceptance.json"])
    if "openclaw" in hosts:
        checkout, js = root / "upstream/openclaw", root / "js"
        js.mkdir(exist_ok=True)
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(scripts / "node" / name, js / name)
        run("node-dependencies", ["npm", "ci", "--ignore-scripts"], cwd=js)
        modules = checkout / "node_modules"
        if not modules.exists():
            modules.symlink_to(js / "node_modules", target_is_directory=True)
        if modules.resolve() != (js / "node_modules").resolve():
            raise RuntimeError("OpenClaw has unrelated dependencies; use a dedicated checkout")
        run("openclaw-process-owner-build", [js / "node_modules/.bin/esbuild",
            "src/process/supervisor/service-child-group-anchor.ts", "--bundle", "--platform=node",
            "--format=esm", "--packages=external", "--outdir=acceptance-build",
            "--metafile=acceptance-build/meta.json"], cwd=checkout)
        env = {**os.environ, "TSX_TSCONFIG_PATH": str(checkout / "tsconfig.json")}
        run("openclaw-acceptance", ["node", "--import", js / "node_modules/tsx/dist/loader.mjs",
            scripts / "openclaw_acceptance.mjs", "--repository", repository,
            "--upstream", checkout, "--python", python,
            "--owner", checkout / "acceptance-build/service-child-group-anchor.js",
            "--output", root / "openclaw-acceptance.json"], env=env)
    reports = {host: json.loads((root / (host + "-acceptance.json")).read_text()) for host in hosts}
    summary = {"status": "PASS", "hosts": reports,
               "dependency_locks": {name: hashlib.sha256((scripts / name).read_bytes()).hexdigest()
                                    for name in ("requirements-qwenpaw.txt", "node/package-lock.json")},
               "boundary": "ORIGINAL_CLIENT_COMPONENTS_NOT_COMPLETE_HOST_APPLICATIONS"}
    (root / "acceptance.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
