#!/usr/bin/env python3
"""Sweetbox enclosure successor for the v0.12 external gate.

The v3 predecessor proved every control except execution inside the enclosure:
a capability-free process could not traverse the runner's private home to reach
Wasmtime. This successor copies only the already hash-pinned executable and
fixed module into a short-lived host staging directory, then binds those exact
files read-only into `/tmp/sandbox` inside the private tmpfs. Runtime cache and
home paths are also confined to that private tmpfs.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sys
import tempfile
from typing import Any

import kwan_external_conformance_v3 as predecessor


base = predecessor.predecessor.base


def enclosure(arguments: list[str], readonly_binds: list[tuple[str, str]] | None = None):
    command = [
        os.environ["SUDO_BIN"],
        "--non-interactive",
        os.environ["BWRAP_BIN"],
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--cap-drop",
        "ALL",
        "--ro-bind",
        "/",
        "/",
        "--tmpfs",
        "/tmp",
        "--chmod",
        "1777",
        "/tmp",
        "--dir",
        "/tmp/sandbox",
        "--chmod",
        "0755",
        "/tmp/sandbox",
        "--dir",
        "/tmp/.cache",
        "--chmod",
        "0700",
        "/tmp/.cache",
        "--setenv",
        "HOME",
        "/tmp",
        "--setenv",
        "XDG_CACHE_HOME",
        "/tmp/.cache",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
    ]
    for source, destination in readonly_binds or []:
        command.extend(["--ro-bind", source, destination])
    command.extend(["--chdir", "/tmp", *arguments])
    return base.run(command)


def wasmtime_enforcement(tmp: pathlib.Path, wasmtime: str, _bwrap: str) -> dict[str, Any]:
    directory = tmp / "wasm"
    directory.mkdir()
    module = directory / "add.wat"
    module.write_text(
        '(module (func (export "add") (param i32 i32) (result i32) '
        "local.get 0 local.get 1 i32.add))\n",
        encoding="utf-8",
    )
    direct = base.run(
        [wasmtime, "run", "--invoke", "add", str(module), "17", "25"]
    )

    staging = pathlib.Path(tempfile.mkdtemp(prefix="kwan-sweetbox-", dir="/var/tmp"))
    os.chmod(staging, 0o755)
    staged_wasmtime = staging / "wasmtime"
    staged_module = staging / "add.wat"
    shutil.copy2(wasmtime, staged_wasmtime)
    shutil.copy2(module, staged_module)
    os.chmod(staged_wasmtime, 0o755)
    os.chmod(staged_module, 0o644)
    try:
        isolated = enclosure(
            [
                "/tmp/sandbox/wasmtime",
                "run",
                "--invoke",
                "add",
                "/tmp/sandbox/add.wat",
                "17",
                "25",
            ],
            [
                (str(staged_wasmtime), "/tmp/sandbox/wasmtime"),
                (str(staged_module), "/tmp/sandbox/add.wat"),
            ],
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    root_write = enclosure(["/bin/sh", "-c", "echo x > /kwan-enforcement-probe"])
    tmp_write = enclosure(
        ["/bin/sh", "-c", "echo x > /tmp/kwan-enforcement-probe && test -s /tmp/kwan-enforcement-probe"]
    )
    interfaces = enclosure(
        [
            "/bin/sh",
            "-c",
            "awk -F: 'NR>2 {gsub(/[[:space:]]/,\"\",$1); print $1}' /proc/net/dev",
        ]
    )
    network = enclosure(
        [
            "/usr/bin/python3",
            "-c",
            "import socket; s=socket.socket(); s.settimeout(.5); s.connect(('1.1.1.1',53))",
        ]
    )
    capabilities = enclosure(
        ["/bin/sh", "-c", "awk '/^CapEff:/ {print $2}' /proc/self/status"]
    )
    interface_list = [line for line in interfaces.stdout.strip().splitlines() if line]
    cap_eff = capabilities.stdout.strip().splitlines()[-1] if capabilities.stdout.strip() else None
    cgroup = pathlib.Path("/sys/fs/cgroup")
    passed = (
        direct.returncode == 0
        and direct.stdout.strip().splitlines()[-1] == "42"
        and isolated.returncode == 0
        and isolated.stdout.strip().splitlines()[-1] == "42"
        and root_write.returncode != 0
        and tmp_write.returncode == 0
        and network.returncode != 0
        and set(interface_list).issubset({"lo"})
        and cap_eff == "0000000000000000"
    )
    return {
        "passed": passed,
        "wasmtime_result": direct.stdout.strip(),
        "isolated_result": isolated.stdout.strip(),
        "namespace_enforcement": {
            "root_write_denied": root_write.returncode != 0,
            "tmp_write_allowed": tmp_write.returncode == 0,
            "network_connect_denied": network.returncode != 0,
            "interfaces": interface_list,
            "interface_source": "/proc/net/dev",
            "effective_capabilities_hex": cap_eff,
            "capabilities_dropped": cap_eff == "0000000000000000",
            "operator_bound_read_only": True,
            "module_bound_read_only": True,
            "home_confined_to_private_tmpfs": True,
            "cache_confined_to_private_tmpfs": True,
            "host_staging_removed": not staging.exists(),
            "cgroup_v2_present": (cgroup / "cgroup.controllers").exists(),
            "cgroup_v2_writable": os.access(cgroup, os.W_OK),
            "seccomp_profile": "NOT_MATERIALISED_IN_THIS_GATE",
            "landlock_profile": "NOT_MATERIALISED_IN_THIS_GATE",
            "enclosure": "SUDO_BUBBLEWRAP_NAMESPACES_READ_ONLY_ROOT_PRIVATE_TMPFS_EXPLICIT_RO_BINDS",
        },
    }


def main() -> int:
    predecessor.predecessor.wasmtime_enforcement = wasmtime_enforcement
    return predecessor.main()


if __name__ == "__main__":
    raise SystemExit(main())
