"""Explicit connection between SCO orders and KCH's own model execution cycle."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

from .runtime import Runtime


def make_model_handler(*, repository, state, workspace, principal, client_factory,
                       model_binding, enabled_tools, native_data=None, sensors=None,
                       max_steps=16):
    """Return a trusted SCO handler, with no inference until dispatch invokes it.

    The host supplies the client factory, selected tools and identity. Every order
    must explicitly grant MODEL_INFERENCE and tool:<name> for every exposed tool.
    Neither an order's prose nor a sensor signal can select a different backend.
    End-to-end model execution requires an explicitly configured real endpoint.
    """
    enabled = frozenset(enabled_tools)
    required = {"MODEL_INFERENCE"} | {"tool:" + name for name in enabled}
    state = Path(state).resolve()

    def handle(envelope):
        order = envelope["work_order"]
        grants = set(order["authority_granted"])
        if not required.issubset(grants):
            return {"outcome": "BLOCKED", "limitations": ["Order lacks explicit inference/tool capabilities"],
                    "authority_exercised": []}
        identity = json.dumps([order["sco_id"], order["target_node_id"], order["order_id"]],
                              ensure_ascii=False, separators=(",", ":"))
        session = "sco:" + hashlib.sha256(identity.encode()).hexdigest()
        runtime = Runtime(repository=Path(repository), state=state, workspace=Path(workspace),
                          principal=principal, session=session, enabled=enabled,
                          native_data=native_data, sensors=sensors)
        # Locators remain data references. No implicit full-context/native-memory copy.
        prompt = json.dumps({"objective": order["objective"], "input_refs": order["input_refs"],
                             "disclosed_fragments": order["disclosed_fragments"],
                             "required_outputs": order["required_outputs"],
                             "termination": order["termination"],
                             "claim_ceiling": order["claim_ceiling"]}, ensure_ascii=False)
        try:
            result = runtime.run(client_factory(), prompt, max_steps=max_steps, binding=model_binding)
            calls = runtime.journal.calls()
        finally:
            runtime.close()
        report_dir = state / "order-results"
        report_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = report_dir / (session.split(":", 1)[1] + ".json")
        data = json.dumps({"order_id": order["order_id"], "result": result,
                           "native_session_id": runtime.tools.native_session_id},
                          ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
        with target.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(report_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        used = {"MODEL_INFERENCE"} | {"tool:" + c["name"] for c in calls
                                     if c["status"] == "DONE"}
        return {"outcome": "SUCCEEDED" if result["status"] == "COMPLETED" else "BLOCKED",
                "output_refs": [target.as_uri()],
                "evidence_ids": ["sha256:" + hashlib.sha256(data).hexdigest()],
                "claims": ["Model cycle returned " + result["status"]],
                "limitations": ["Completion does not adjudicate scientific correctness or semantic output requirements"],
                "authority_exercised": sorted(used)}
    return handle
