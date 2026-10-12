#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent

POLICY_VECTORS = [
    {"id":"support_shadow_nonproductive","implemented":True,"productive":False,"realm":"SHADOW","realm_allowed":True,"explicit":False,"bindings":True,"expected":"SUPPORT"},
    {"id":"deny_shadow_productive","implemented":True,"productive":True,"realm":"SHADOW","realm_allowed":True,"explicit":True,"bindings":True,"expected":"DENY"},
    {"id":"deny_active_without_explicit","implemented":True,"productive":True,"realm":"ACTIVE","realm_allowed":True,"explicit":False,"bindings":True,"expected":"DENY"},
    {"id":"support_active_with_explicit","implemented":True,"productive":True,"realm":"ACTIVE","realm_allowed":True,"explicit":True,"bindings":True,"expected":"SUPPORT"},
    {"id":"deny_unimplemented","implemented":False,"productive":False,"realm":"SHADOW","realm_allowed":True,"explicit":False,"bindings":True,"expected":"DENY"},
    {"id":"deny_realm_not_allowed","implemented":True,"productive":False,"realm":"QUARANTINE","realm_allowed":False,"explicit":False,"bindings":True,"expected":"DENY"},
    {"id":"deny_underbound_resource","implemented":True,"productive":False,"realm":"SHADOW","realm_allowed":True,"explicit":False,"bindings":False,"expected":"DENY"},
    {"id":"deny_multiple_reasons","implemented":False,"productive":True,"realm":"SHADOW","realm_allowed":False,"explicit":False,"bindings":False,"expected":"DENY"},
]

CEDAR_POLICIES = r'''// Kwan KCH policy support only. No authority is granted here.
forbid (principal, action == Kwan::Action::"considerLease", resource) when { !resource.implemented };
forbid (principal, action == Kwan::Action::"considerLease", resource) when { !context.realmAllowed };
forbid (principal, action == Kwan::Action::"considerLease", resource) when { resource.productive && context.realm == "SHADOW" };
forbid (principal, action == Kwan::Action::"considerLease", resource) when { resource.productive && context.realm == "ACTIVE" && !context.explicitUserAuthority };
forbid (principal, action == Kwan::Action::"considerLease", resource) when { !context.resourceBindingsComplete };
permit (principal, action == Kwan::Action::"considerLease", resource) when {
  resource.implemented && context.realmAllowed && context.resourceBindingsComplete &&
  !(resource.productive && context.realm == "SHADOW") &&
  (!resource.productive || context.explicitUserAuthority)
};
'''

CEDAR_SCHEMA = {
    "Kwan": {
        "entityTypes": {
            "Principal": {"memberOfTypes": []},
            "Capability": {"memberOfTypes": [], "shape": {"type":"Record", "attributes": {
                "implemented":{"type":"Boolean","required":True},
                "productive":{"type":"Boolean","required":True}
            }}}
        },
        "actions": {"considerLease": {"appliesTo": {
            "principalTypes":["Principal"], "resourceTypes":["Capability"],
            "context":{"type":"Record","attributes":{
                "realm":{"type":"String","required":True},
                "realmAllowed":{"type":"Boolean","required":True},
                "explicitUserAuthority":{"type":"Boolean","required":True},
                "resourceBindingsComplete":{"type":"Boolean","required":True}
            }}
        }}}
    }
}

OPA_POLICY = r'''package kwan.kch
import rego.v1
default support := false
deny contains "CAPABILITY_UNIMPLEMENTED" if { not input.capability.implemented }
deny contains "REALM_NOT_ALLOWED" if { not input.context.realm_allowed }
deny contains "PRODUCTIVE_SHADOW_FORBIDDEN" if { input.capability.productive; input.context.realm == "SHADOW" }
deny contains "EXPLICIT_USER_AUTHORITY_REQUIRED" if { input.capability.productive; input.context.realm == "ACTIVE"; not input.context.explicit_user_authority }
deny contains "RESOURCE_BINDING_INCOMPLETE" if { not input.context.resource_bindings_complete }
support if { count(deny) == 0 }
decision := {"support":support,"deny":sort([x | x := deny[_]]),"authority_granted":false,"execution_granted":false}
'''

IPLD_VALID = [
    {"id":"empty_map","value":{}},
    {"id":"key_order","value":{"aa":1,"b":2,"a":3}},
    {"id":"nested","value":{"z":[1,-1,True,False,None],"u":"KWAN-λ"}},
    {"id":"large_ints","value":{"p":4294967296,"n":-4294967297}},
    {"id":"array","value":[{"k":"v"},0,23,24,255,256,65535,65536]},
]
IPLD_MALFORMED = [
    {"id":"truncated_map","hex":"a1"},
    {"id":"indefinite_map","hex":"bf616101ff"},
    {"id":"non_text_key","hex":"a10101"},
    {"id":"unsupported_tag","hex":"c101"},
]

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def run(args: list[str], *, cwd: pathlib.Path | None = None, env: dict[str,str] | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(args, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if check and process.returncode:
        raise RuntimeError(f"command failed ({process.returncode}): {' '.join(args)}\n{process.stdout}")
    return process

def tool_version(path: str, args: list[str] | None = None) -> str:
    process = run([path] + (args or ["--version"]), check=True)
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    return lines[0] if lines else "UNKNOWN"

def reference_outcome(vector: dict[str,Any]) -> str:
    deny = (
        not vector["implemented"] or not vector["realm_allowed"] or not vector["bindings"] or
        (vector["productive"] and vector["realm"] == "SHADOW") or
        (vector["productive"] and vector["realm"] == "ACTIVE" and not vector["explicit"])
    )
    return "DENY" if deny else "SUPPORT"

def policy_conformance(tmp: pathlib.Path, opa: str, cedar: str) -> dict[str,Any]:
    directory = tmp / "policy"
    directory.mkdir()
    (directory/"kch.rego").write_text(OPA_POLICY, encoding="utf-8")
    (directory/"policies.cedar").write_text(CEDAR_POLICIES, encoding="utf-8")
    (directory/"schema.json").write_text(json.dumps(CEDAR_SCHEMA, sort_keys=True), encoding="utf-8")
    opa_check = run([opa,"check","--strict",str(directory/"kch.rego")])
    cedar_validate = run([cedar,"validate","--policies",str(directory/"policies.cedar"),"--schema",str(directory/"schema.json")])
    rows=[]
    for vector in POLICY_VECTORS:
        opa_input={"capability":{"implemented":vector["implemented"],"productive":vector["productive"]},"context":{
            "realm":vector["realm"],"realm_allowed":vector["realm_allowed"],"explicit_user_authority":vector["explicit"],"resource_bindings_complete":vector["bindings"]}}
        (directory/"input.json").write_text(json.dumps(opa_input),encoding="utf-8")
        opa_process = run([opa,"eval","--format=json","--data",str(directory/"kch.rego"),"--input",str(directory/"input.json"),"data.kwan.kch.decision"])
        opa_document=json.loads(opa_process.stdout)
        opa_value=opa_document["result"][0]["expressions"][0]["value"]
        opa_outcome="SUPPORT" if opa_value["support"] else "DENY"
        entities=[
            {"uid":{"type":"Kwan::Principal","id":"user"},"attrs":{},"parents":[]},
            {"uid":{"type":"Kwan::Capability","id":vector["id"]},"attrs":{"implemented":vector["implemented"],"productive":vector["productive"]},"parents":[]},
        ]
        request={"principal":"Kwan::Principal::\"user\"","action":"Kwan::Action::\"considerLease\"","resource":f"Kwan::Capability::\"{vector['id']}\"","context":{
            "realm":vector["realm"],"realmAllowed":vector["realm_allowed"],"explicitUserAuthority":vector["explicit"],"resourceBindingsComplete":vector["bindings"]}}
        (directory/"entities.json").write_text(json.dumps(entities),encoding="utf-8")
        (directory/"request.json").write_text(json.dumps(request),encoding="utf-8")
        cedar_process=run([cedar,"authorize","--policies",str(directory/"policies.cedar"),"--entities",str(directory/"entities.json"),"--request-json",str(directory/"request.json")])
        cedar_lines=[line.strip() for line in cedar_process.stdout.splitlines() if line.strip()]
        cedar_outcome="SUPPORT" if cedar_lines and cedar_lines[-1]=="ALLOW" else "DENY"
        reference=reference_outcome(vector)
        passed=(reference==vector["expected"]==opa_outcome==cedar_outcome and opa_process.returncode==0 and cedar_process.returncode==0)
        rows.append({"id":vector["id"],"expected":vector["expected"],"reference":reference,"opa":opa_outcome,"cedar":cedar_outcome,"opa_denials":opa_value["deny"],"passed":passed,"cedar_output":cedar_process.stdout.strip()})
    passed=(opa_check.returncode==0 and cedar_validate.returncode==0 and all(row["passed"] for row in rows))
    return {"passed":passed,"opa_check":opa_check.returncode==0,"cedar_validate":cedar_validate.returncode==0,"cedar_validate_output":cedar_validate.stdout.strip(),"vectors":rows,
            "abstain_wrapper":{"case":"unknown capability outside external-engine schema","outcome":"ABSTAIN","external_engines_invoked":False,"authority_granted":False}}

def cbor_head(major:int,value:int)->bytes:
    if value<24:return bytes([(major<<5)|value])
    if value<256:return bytes([(major<<5)|24,value])
    if value<65536:return bytes([(major<<5)|25])+value.to_bytes(2,"big")
    if value<2**32:return bytes([(major<<5)|26])+value.to_bytes(4,"big")
    if value<2**64:return bytes([(major<<5)|27])+value.to_bytes(8,"big")
    raise ValueError("integer too large")

def encode_cbor(value:Any)->bytes:
    if value is None:return b"\xf6"
    if value is False:return b"\xf4"
    if value is True:return b"\xf5"
    if isinstance(value,int):return cbor_head(0,value) if value>=0 else cbor_head(1,-1-value)
    if isinstance(value,str):
        encoded=value.encode("utf-8")
        return cbor_head(3,len(encoded))+encoded
    if isinstance(value,list):return cbor_head(4,len(value))+b"".join(encode_cbor(item) for item in value)
    if isinstance(value,dict):
        items=[]
        for key,item in value.items():
            if not isinstance(key,str):raise ValueError("DAG-CBOR map keys must be strings")
            encoded_key=encode_cbor(key)
            items.append((encoded_key,encode_cbor(item)))
        items.sort(key=lambda pair:(len(pair[0]),pair[0]))
        return cbor_head(5,len(items))+b"".join(key+item for key,item in items)
    raise ValueError(f"unsupported type {type(value)!r}")

def varint(value:int)->bytes:
    output=bytearray()
    while True:
        byte=value&0x7f
        value>>=7
        output.append(byte|(0x80 if value else 0))
        if not value:return bytes(output)

def cid_for(data:bytes)->str:
    raw=varint(1)+varint(0x71)+varint(0x12)+varint(32)+hashlib.sha256(data).digest()
    return "b"+base64.b32encode(raw).decode().lower().rstrip("=")

def ipld_conformance(tmp:pathlib.Path,node:str)->dict[str,Any]:
    directory=tmp/"ipld"
    directory.mkdir()
    request={"valid":IPLD_VALID,"malformed":IPLD_MALFORMED}
    (directory/"vectors.json").write_text(json.dumps(request,ensure_ascii=False),encoding="utf-8")
    process=run([node,str(ROOT/"ipld_external.mjs"),str(directory/"vectors.json")],cwd=ROOT)
    if process.returncode:raise RuntimeError(process.stdout)
    external=json.loads(process.stdout)
    external_valid={item["id"]:item for item in external["valid"]}
    rows=[]
    for vector in IPLD_VALID:
        encoded=encode_cbor(vector["value"])
        external_item=external_valid[vector["id"]]
        rows.append({"id":vector["id"],"python_hex":encoded.hex(),"external_hex":external_item["hex"],"python_cid":cid_for(encoded),"external_cid":external_item["cid"],"passed":encoded.hex()==external_item["hex"] and cid_for(encoded)==external_item["cid"]})
    external_bad={item["id"]:item for item in external["malformed"]}
    malformed=[{"id":vector["id"],"external_rejected":external_bad[vector["id"]]["rejected"],"error":external_bad[vector["id"]]["error"]} for vector in IPLD_MALFORMED]
    return {"passed":all(item["passed"] for item in rows) and all(item["external_rejected"] for item in malformed),"valid":rows,"malformed":malformed}

def sandbox_command(bwrap:str,args:list[str])->subprocess.CompletedProcess[str]:
    prefix=[bwrap,"--unshare-all","--die-with-parent","--new-session","--cap-drop","ALL","--ro-bind","/","/","--tmpfs","/tmp","--proc","/proc","--dev","/dev","--chdir","/tmp"]
    return run(prefix+args)

def wasmtime_enforcement(tmp:pathlib.Path,wasmtime:str,bwrap:str)->dict[str,Any]:
    directory=tmp/"wasm"
    directory.mkdir()
    module=directory/"add.wat"
    module.write_text('(module (func (export "add") (param i32 i32) (result i32) local.get 0 local.get 1 i32.add))\n',encoding="utf-8")
    direct=run([wasmtime,"run","--invoke","add",str(module),"17","25"])
    isolated=sandbox_command(bwrap,[wasmtime,"run","--invoke","add",str(module),"17","25"])
    root_write=sandbox_command(bwrap,["/bin/sh","-c","echo x > /kwan-enforcement-probe"])
    tmp_write=sandbox_command(bwrap,["/bin/sh","-c","echo x > /tmp/kwan-enforcement-probe && test -s /tmp/kwan-enforcement-probe"])
    interfaces=sandbox_command(bwrap,["/bin/sh","-c","ls -1 /sys/class/net 2>/dev/null || true"])
    network=sandbox_command(bwrap,[sys.executable,"-c","import socket; s=socket.socket(); s.settimeout(.5); s.connect(('1.1.1.1',53))"])
    cgroup=pathlib.Path('/sys/fs/cgroup')
    interface_list=interfaces.stdout.strip().splitlines()
    passed=(direct.returncode==0 and direct.stdout.strip().splitlines()[-1]=="42" and isolated.returncode==0 and isolated.stdout.strip().splitlines()[-1]=="42" and root_write.returncode!=0 and tmp_write.returncode==0 and network.returncode!=0 and all(item in {"lo",""} for item in interface_list))
    return {"passed":passed,"wasmtime_result":direct.stdout.strip(),"isolated_result":isolated.stdout.strip(),"namespace_enforcement":{"root_write_denied":root_write.returncode!=0,"tmp_write_allowed":tmp_write.returncode==0,"network_connect_denied":network.returncode!=0,"interfaces":interface_list,"cgroup_v2_present":(cgroup/'cgroup.controllers').exists(),"cgroup_v2_writable":os.access(cgroup,os.W_OK),"seccomp_profile":"NOT_MATERIALISED_IN_THIS_GATE","landlock_profile":"NOT_MATERIALISED_IN_THIS_GATE"}}

def tuf_rollback_check()->dict[str,Any]:
    try:
        from securesystemslib.signer import CryptoSigner
        from tuf.api.metadata import Metadata, Root, Timestamp, MetaFile
        from tuf.ngclient._internal.trusted_metadata_set import TrustedMetadataSet
        from tuf.api.exceptions import BadVersionNumberError
    except Exception as exc:
        return {"passed":False,"error":f"import failed: {exc}"}
    now=dt.datetime.now(dt.timezone.utc)
    signer=CryptoSigner.generate_ed25519()
    root=Metadata(Root(expires=now+dt.timedelta(days=30),version=1))
    for role in ("root","timestamp","snapshot","targets"):
        root.signed.add_key(signer.public_key,role)
    root.sign(signer)
    def timestamp(version:int)->bytes:
        metadata=Metadata(Timestamp(expires=now+dt.timedelta(days=7),version=version,snapshot_meta=MetaFile(version=1)))
        metadata.sign(signer)
        return metadata.to_bytes()
    trusted=TrustedMetadataSet(root.to_bytes())
    trusted.update_timestamp(timestamp(2))
    rejected=False
    error_type=None
    try:
        trusted.update_timestamp(timestamp(1))
    except BadVersionNumberError as exc:
        rejected=True
        error_type=type(exc).__name__
    return {"passed":rejected,"trusted_timestamp_version":2,"rollback_candidate_version":1,"rollback_rejected":rejected,"error_type":error_type}

def truqueplace_conformance(tmp:pathlib.Path,oras:str,cosign:str)->dict[str,Any]:
    directory=tmp/"truqueplace"
    directory.mkdir()
    layout=directory/"layout"
    pulled=directory/"pulled"
    pulled.mkdir()
    payload=directory/"operator.wasm"
    payload.write_bytes(b"KWAN-TRUQUEPLACE-EXTERNAL-CONFORMANCE\n")
    target="kwan.external:v1"
    push=run([oras,"push",target,f"{payload}:application/vnd.kwan.operator.v1","--artifact-type","application/vnd.kwan.operator.package.v1","--oci-layout-path",str(layout),"--export-manifest",str(directory/"manifest.json")])
    pull=run([oras,"pull",target,"--oci-layout-path",str(layout),"-o",str(pulled)])
    restored=pulled/payload.name
    oras_ok=push.returncode==0 and pull.returncode==0 and restored.is_file() and restored.read_bytes()==payload.read_bytes()
    environment=dict(os.environ)
    environment["COSIGN_PASSWORD"]="kwan-conformance-only"
    generate=run([cosign,"generate-key-pair","--output-key-prefix",str(directory/"kwan")],env=environment)
    bundle=directory/"cosign.bundle.json"
    sign=run([cosign,"sign-blob","--yes","--tlog-upload=false","--key",str(directory/"kwan.key"),"--bundle",str(bundle),str(directory/"manifest.json")],env=environment)
    verify=run([cosign,"verify-blob","--key",str(directory/"kwan.pub"),"--bundle",str(bundle),str(directory/"manifest.json")],env=environment)
    tuf=tuf_rollback_check()
    return {"passed":oras_ok and generate.returncode==0 and sign.returncode==0 and verify.returncode==0 and tuf["passed"],"oras":{"roundtrip_exact":oras_ok,"push_output":push.stdout.strip(),"pull_output":pull.stdout.strip(),"manifest_sha256":sha256((directory/"manifest.json").read_bytes()) if (directory/"manifest.json").exists() else None},"cosign":{"local_key_signature_verified":verify.returncode==0,"sign_output":sign.stdout.strip(),"verify_output":verify.stdout.strip(),"rekor_transparency_used":False,"keyless_used":False},"tuf":tuf}

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    arguments=parser.parse_args()
    tools={key:os.environ.get(key) for key in ["OPA_BIN","CEDAR_BIN","WASMTIME_BIN","ORAS_BIN","COSIGN_BIN","BWRAP_BIN","NODE_BIN"]}
    if not all(tools.values()):raise SystemExit(f"missing tool env: {tools}")
    with tempfile.TemporaryDirectory(prefix="kwan-ext-") as temporary:
        tmp=pathlib.Path(temporary)
        report={"format":"KWAN_EXTERNAL_CONFORMANCE_REPORT_V1","gate":"v0.12.0-alpha.1","generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"authority_granted":False,"promotion_performed":False,"tools":{
            "opa":{"version":tool_version(tools['OPA_BIN'],['version']),"sha256":sha256(pathlib.Path(tools['OPA_BIN']).read_bytes())},
            "cedar":{"version":tool_version(tools['CEDAR_BIN']),"sha256":sha256(pathlib.Path(tools['CEDAR_BIN']).read_bytes())},
            "wasmtime":{"version":tool_version(tools['WASMTIME_BIN']),"sha256":sha256(pathlib.Path(tools['WASMTIME_BIN']).read_bytes())},
            "oras":{"version":tool_version(tools['ORAS_BIN'],['version']),"sha256":sha256(pathlib.Path(tools['ORAS_BIN']).read_bytes())},
            "cosign":{"version":tool_version(tools['COSIGN_BIN'],['version']),"sha256":sha256(pathlib.Path(tools['COSIGN_BIN']).read_bytes())},
        }}
        report["policy"]=policy_conformance(tmp,tools["OPA_BIN"],tools["CEDAR_BIN"])
        report["ipld"]=ipld_conformance(tmp,tools["NODE_BIN"])
        report["sweetbox"]=wasmtime_enforcement(tmp,tools["WASMTIME_BIN"],tools["BWRAP_BIN"])
        report["truqueplace"]=truqueplace_conformance(tmp,tools["ORAS_BIN"],tools["COSIGN_BIN"])
        report["passed"]=all(report[name]["passed"] for name in ["policy","ipld","sweetbox","truqueplace"])
        canonical=json.dumps(report,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        report["report_sha256"]=sha256(canonical)
        output=pathlib.Path(arguments.output)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        print(json.dumps({"passed":report["passed"],"report_sha256":report["report_sha256"]},sort_keys=True))
        return 0 if report["passed"] else 1

if __name__=="__main__":
    raise SystemExit(main())
