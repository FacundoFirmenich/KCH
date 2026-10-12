#!/usr/bin/env python3
"""Successor harness for the v0.12 SHADOW external-conformance gate.

This file intentionally imports the previous attempt rather than deleting it. It
corrects only findings demonstrated by immutable predecessor artifacts:

* Cedar JSON schema selection and valid DENY exit semantics;
* privileged Bubblewrap namespace construction with a read-only host root;
* relative-path ORAS OCI layout operation;
* Cosign v3 signing config and explicit offline verification;
* release-asset hashes in the final evidence envelope.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
from typing import Any

import kwan_external_conformance as base


def policy_conformance(tmp: pathlib.Path, opa: str, cedar: str) -> dict[str, Any]:
    directory = tmp / "policy"
    directory.mkdir()
    (directory / "kch.rego").write_text(base.OPA_POLICY, encoding="utf-8")
    (directory / "policies.cedar").write_text(base.CEDAR_POLICIES, encoding="utf-8")
    (directory / "schema.json").write_text(
        json.dumps(base.CEDAR_SCHEMA, sort_keys=True), encoding="utf-8"
    )
    opa_check = base.run([opa, "check", "--strict", str(directory / "kch.rego")])
    cedar_validate = base.run(
        [
            cedar,
            "validate",
            "--policies",
            str(directory / "policies.cedar"),
            "--schema",
            str(directory / "schema.json"),
            "--schema-format",
            "json",
        ]
    )
    rows: list[dict[str, Any]] = []
    for vector in base.POLICY_VECTORS:
        opa_input = {
            "capability": {
                "implemented": vector["implemented"],
                "productive": vector["productive"],
            },
            "context": {
                "realm": vector["realm"],
                "realm_allowed": vector["realm_allowed"],
                "explicit_user_authority": vector["explicit"],
                "resource_bindings_complete": vector["bindings"],
            },
        }
        (directory / "input.json").write_text(json.dumps(opa_input), encoding="utf-8")
        opa_process = base.run(
            [
                opa,
                "eval",
                "--format=json",
                "--data",
                str(directory / "kch.rego"),
                "--input",
                str(directory / "input.json"),
                "data.kwan.kch.decision",
            ]
        )
        opa_document = json.loads(opa_process.stdout)
        opa_value = opa_document["result"][0]["expressions"][0]["value"]
        opa_outcome = "SUPPORT" if opa_value["support"] else "DENY"
        entities = [
            {
                "uid": {"type": "Kwan::Principal", "id": "user"},
                "attrs": {},
                "parents": [],
            },
            {
                "uid": {"type": "Kwan::Capability", "id": vector["id"]},
                "attrs": {
                    "implemented": vector["implemented"],
                    "productive": vector["productive"],
                },
                "parents": [],
            },
        ]
        request = {
            "principal": 'Kwan::Principal::"user"',
            "action": 'Kwan::Action::"considerLease"',
            "resource": f'Kwan::Capability::"{vector["id"]}"',
            "context": {
                "realm": vector["realm"],
                "realmAllowed": vector["realm_allowed"],
                "explicitUserAuthority": vector["explicit"],
                "resourceBindingsComplete": vector["bindings"],
            },
        }
        (directory / "entities.json").write_text(json.dumps(entities), encoding="utf-8")
        (directory / "request.json").write_text(json.dumps(request), encoding="utf-8")
        cedar_process = base.run(
            [
                cedar,
                "authorize",
                "--policies",
                str(directory / "policies.cedar"),
                "--entities",
                str(directory / "entities.json"),
                "--request-json",
                str(directory / "request.json"),
            ]
        )
        cedar_lines = [line.strip() for line in cedar_process.stdout.splitlines() if line.strip()]
        cedar_token = cedar_lines[-1] if cedar_lines else ""
        cedar_outcome = (
            "SUPPORT" if cedar_token == "ALLOW" else "DENY" if cedar_token == "DENY" else "ERROR"
        )
        reference = base.reference_outcome(vector)
        passed = (
            reference
            == vector["expected"]
            == opa_outcome
            == cedar_outcome
            and opa_process.returncode == 0
            and cedar_token in {"ALLOW", "DENY"}
        )
        rows.append(
            {
                "id": vector["id"],
                "expected": vector["expected"],
                "reference": reference,
                "opa": opa_outcome,
                "cedar": cedar_outcome,
                "opa_denials": opa_value["deny"],
                "cedar_exit_code": cedar_process.returncode,
                "cedar_output": cedar_process.stdout.strip(),
                "passed": passed,
            }
        )
    return {
        "passed": opa_check.returncode == 0
        and cedar_validate.returncode == 0
        and all(row["passed"] for row in rows),
        "opa_check": opa_check.returncode == 0,
        "cedar_validate": cedar_validate.returncode == 0,
        "cedar_validate_output": cedar_validate.stdout.strip(),
        "vectors": rows,
        "abstain_wrapper": {
            "case": "unknown capability outside external-engine schema",
            "outcome": "ABSTAIN",
            "external_engines_invoked": False,
            "authority_granted": False,
        },
    }


def sandbox_command(arguments: list[str]):
    return base.run(
        [
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
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--chdir",
            "/tmp",
            *arguments,
        ]
    )


def wasmtime_enforcement(tmp: pathlib.Path, wasmtime: str, _bwrap: str) -> dict[str, Any]:
    directory = tmp / "wasm"
    directory.mkdir()
    module = directory / "add.wat"
    module.write_text(
        '(module (func (export "add") (param i32 i32) (result i32) '
        "local.get 0 local.get 1 i32.add))\n",
        encoding="utf-8",
    )
    direct = base.run([wasmtime, "run", "--invoke", "add", str(module), "17", "25"])
    isolated = sandbox_command([wasmtime, "run", "--invoke", "add", str(module), "17", "25"])
    root_write = sandbox_command(["/bin/sh", "-c", "echo x > /kwan-enforcement-probe"])
    tmp_write = sandbox_command(
        ["/bin/sh", "-c", "echo x > /tmp/kwan-enforcement-probe && test -s /tmp/kwan-enforcement-probe"]
    )
    interfaces = sandbox_command(["/bin/sh", "-c", "ls -1 /sys/class/net 2>/dev/null || true"])
    network = sandbox_command(
        [
            sys.executable,
            "-c",
            "import socket; s=socket.socket(); s.settimeout(.5); s.connect(('1.1.1.1',53))",
        ]
    )
    capabilities = sandbox_command(
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
            "effective_capabilities_hex": cap_eff,
            "capabilities_dropped": cap_eff == "0000000000000000",
            "cgroup_v2_present": (cgroup / "cgroup.controllers").exists(),
            "cgroup_v2_writable": os.access(cgroup, os.W_OK),
            "seccomp_profile": "NOT_MATERIALISED_IN_THIS_GATE",
            "landlock_profile": "NOT_MATERIALISED_IN_THIS_GATE",
            "enclosure": "SUDO_BUBBLEWRAP_NAMESPACES_READ_ONLY_ROOT_TMPFS",
        },
    }


def truqueplace_conformance(tmp: pathlib.Path, oras: str, cosign: str) -> dict[str, Any]:
    directory = tmp / "truqueplace"
    directory.mkdir()
    pulled = directory / "pulled"
    pulled.mkdir()
    payload = directory / "operator.wasm"
    payload.write_bytes(b"KWAN-TRUQUEPLACE-EXTERNAL-CONFORMANCE\n")
    target = "kwan.external:v1"
    push = base.run(
        [
            oras,
            "push",
            target,
            f"{payload.name}:application/vnd.kwan.operator.v1",
            "--artifact-type",
            "application/vnd.kwan.operator.package.v1",
            "--oci-layout-path",
            "layout",
            "--export-manifest",
            "manifest.json",
        ],
        cwd=directory,
    )
    pull = base.run(
        [oras, "pull", target, "--oci-layout-path", "layout", "-o", pulled.name],
        cwd=directory,
    )
    restored = pulled / payload.name
    oras_ok = (
        push.returncode == 0
        and pull.returncode == 0
        and restored.is_file()
        and restored.read_bytes() == payload.read_bytes()
    )
    environment = dict(os.environ)
    environment["COSIGN_PASSWORD"] = "kwan-conformance-only"
    generate = base.run(
        [cosign, "generate-key-pair", "--output-key-prefix", "kwan"],
        cwd=directory,
        env=environment,
    )
    signing_config = base.run(
        [cosign, "signing-config", "create", "--out", "signing-config.json"],
        cwd=directory,
        env=environment,
    )
    sign = base.run(
        [
            cosign,
            "sign-blob",
            "--yes",
            "--key",
            "kwan.key",
            "--signing-config",
            "signing-config.json",
            "--bundle",
            "cosign.bundle.json",
            "manifest.json",
        ],
        cwd=directory,
        env=environment,
    )
    verify = base.run(
        [
            cosign,
            "verify-blob",
            "--key",
            "kwan.pub",
            "--bundle",
            "cosign.bundle.json",
            "--insecure-ignore-tlog=true",
            "manifest.json",
        ],
        cwd=directory,
        env=environment,
    )
    tuf = base.tuf_rollback_check()
    return {
        "passed": oras_ok
        and generate.returncode == 0
        and signing_config.returncode == 0
        and sign.returncode == 0
        and verify.returncode == 0
        and tuf["passed"],
        "oras": {
            "roundtrip_exact": oras_ok,
            "push_exit_code": push.returncode,
            "pull_exit_code": pull.returncode,
            "push_output": push.stdout.strip(),
            "pull_output": pull.stdout.strip(),
            "manifest_sha256": base.sha256((directory / "manifest.json").read_bytes())
            if (directory / "manifest.json").exists()
            else None,
        },
        "cosign": {
            "key_generation_exit_code": generate.returncode,
            "signing_config_exit_code": signing_config.returncode,
            "sign_exit_code": sign.returncode,
            "verify_exit_code": verify.returncode,
            "local_key_signature_verified": verify.returncode == 0,
            "sign_output": sign.stdout.strip(),
            "verify_output": verify.stdout.strip(),
            "rekor_transparency_used": False,
            "keyless_used": False,
        },
        "tuf": tuf,
    }


def main() -> int:
    base.policy_conformance = policy_conformance
    base.wasmtime_enforcement = wasmtime_enforcement
    base.truqueplace_conformance = truqueplace_conformance
    result = base.main()
    try:
        output_index = sys.argv.index("--output") + 1
        output = pathlib.Path(sys.argv[output_index])
    except (ValueError, IndexError):
        return 2
    document = json.loads(output.read_text(encoding="utf-8"))
    for name, variable in {
        "opa": "OPA_SHA256",
        "cedar": "CEDAR_SHA256",
        "wasmtime": "WASMTIME_SHA256",
        "oras": "ORAS_SHA256",
        "cosign": "COSIGN_SHA256",
    }.items():
        document["tools"][name]["asset_sha256"] = os.environ.get(variable)
    document.pop("report_sha256", None)
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    document["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"passed": document["passed"], "report_sha256": document["report_sha256"]},
            sort_keys=True,
        )
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
