#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ALLOWED_STATES = {
    "POINT_IDENTIFIED",
    "PARTIALLY_IDENTIFIED",
    "NOT_IDENTIFIED",
    "ILL_TYPED",
    "INVALID_CONSTRUCT",
    "OPEN_WORLD_UNCERTIFIED",
}
ALLOWED_CONSTRUCT = {"VALID", "FAILED", "UNRESOLVED", "FAILED_OR_UNRESOLVED"}

SYSTEM = """You are one of two independent blinded scientific adjudicators. You receive no gold label, no other-pass output, and no system output. Evaluate only the supplied source snapshot. Do not infer beyond the source. A source paper reporting a claim is not itself a scientific certificate. Expert-review criticism is evidence within review scope, not universal ground truth. Choose the strongest state actually supported and preserve uncertainty. Return exactly one JSON object with keys state, construct_validity, certificate_status, claim_ceiling, reasoning. state must be one of POINT_IDENTIFIED, PARTIALLY_IDENTIFIED, NOT_IDENTIFIED, ILL_TYPED, INVALID_CONSTRUCT, OPEN_WORLD_UNCERTIFIED. construct_validity must be one of VALID, FAILED, UNRESOLVED, FAILED_OR_UNRESOLVED. certificate_status must be a nonempty array of short strings. Do not add markdown or prose outside the JSON."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def post_json(url: str, payload: dict, attempts: int = 60) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    last = None
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ConnectionError) as exc:
            last = exc
            time.sleep(2)
    raise RuntimeError(f"server not available: {last}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--card", required=True)
    p.add_argument("--pass-id", required=True, choices=["PASS_A", "PASS_B"])
    p.add_argument("--model-id", required=True)
    p.add_argument("--model-file", required=True)
    p.add_argument("--url", default="http://127.0.0.1:8080/v1/chat/completions")
    p.add_argument("--output", required=True)
    p.add_argument("--raw-output", required=True)
    args = p.parse_args()

    card_path = Path(args.card)
    model_path = Path(args.model_file)
    card = json.loads(card_path.read_text(encoding="utf-8"))
    prompt = (
        f"PASS ID: {args.pass_id}\n"
        "ADJUDICATE THIS SOURCE-GROUNDED CARD:\n"
        + json.dumps(card, ensure_ascii=False, sort_keys=True)
    )
    payload = {
        "model": args.model_id,
        "temperature": 0,
        "seed": 20261024 if args.pass_id == "PASS_A" else 20261025,
        "max_tokens": 450,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    envelope = post_json(args.url, payload)
    content = envelope["choices"][0]["message"]["content"]
    Path(args.raw_output).write_text(content + "\n", encoding="utf-8")
    parsed = parse_json_object(content)

    required = {"state", "construct_validity", "certificate_status", "claim_ceiling", "reasoning"}
    missing = required - set(parsed)
    if missing:
        raise ValueError(f"missing keys: {sorted(missing)}")
    if parsed["state"] not in ALLOWED_STATES:
        raise ValueError(f"invalid state: {parsed['state']}")
    if parsed["construct_validity"] not in ALLOWED_CONSTRUCT:
        raise ValueError(f"invalid construct_validity: {parsed['construct_validity']}")
    if not isinstance(parsed["certificate_status"], list) or not parsed["certificate_status"]:
        raise ValueError("certificate_status must be a nonempty array")
    if len(str(parsed["reasoning"])) < 20:
        raise ValueError("reasoning is too short")

    output = {
        "claim_id": card["claim_id"],
        "pass_id": args.pass_id,
        "source_snapshot_sha256": card["source_snapshot_sha256"],
        "state": parsed["state"],
        "construct_validity": parsed["construct_validity"],
        "certificate_status": [str(x) for x in parsed["certificate_status"]],
        "claim_ceiling": str(parsed["claim_ceiling"]),
        "reasoning": str(parsed["reasoning"]),
        "adjudicator_receipt": {
            "model_id": args.model_id,
            "model_artifact_sha256": sha256_bytes(model_path.read_bytes()),
            "prompt_sha256": sha256_bytes((SYSTEM + "\n" + prompt).encode("utf-8")),
            "output_sha256": sha256_bytes(content.encode("utf-8")),
            "labels_seen": False,
            "other_pass_seen": False,
            "temperature": 0,
            "seed": payload["seed"],
            "llama_server_response_id": envelope.get("id"),
        },
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
