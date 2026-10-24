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
ALLOWED_CEILINGS = {
    "POINT_IDENTIFIED",
    "PARTIALLY_IDENTIFIED",
    "NOT_IDENTIFIED",
    "INVALID_CONSTRUCT",
    "OPEN_WORLD_UNCERTIFIED",
}

SYSTEM = """You are one of two independent blinded scientific adjudicators. You receive no gold label, no other-pass output, and no system output. Evaluate only the supplied source snapshot. Do not infer beyond the source. A source paper reporting a claim is not itself a scientific certificate. Expert-review criticism is evidence within review scope, not universal ground truth. Choose the strongest state actually supported and preserve uncertainty. Every required JSON field must be present. Return exactly one JSON object and no markdown."""

JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "state",
        "construct_validity",
        "certificate_status",
        "claim_ceiling",
        "reasoning",
    ],
    "properties": {
        "state": {"type": "string", "enum": sorted(ALLOWED_STATES)},
        "construct_validity": {"type": "string", "enum": sorted(ALLOWED_CONSTRUCT)},
        "certificate_status": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {"type": "string", "minLength": 3, "maxLength": 120},
        },
        "claim_ceiling": {"type": "string", "enum": sorted(ALLOWED_CEILINGS)},
        "reasoning": {"type": "string", "minLength": 40, "maxLength": 2000},
    },
}


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


def validate(parsed: dict) -> None:
    required = {"state", "construct_validity", "certificate_status", "claim_ceiling", "reasoning"}
    missing = required - set(parsed)
    if missing:
        raise ValueError(f"missing keys: {sorted(missing)}")
    extra = set(parsed) - required
    if extra:
        raise ValueError(f"unexpected keys: {sorted(extra)}")
    if parsed["state"] not in ALLOWED_STATES:
        raise ValueError(f"invalid state: {parsed['state']}")
    if parsed["construct_validity"] not in ALLOWED_CONSTRUCT:
        raise ValueError(f"invalid construct_validity: {parsed['construct_validity']}")
    if parsed["claim_ceiling"] not in ALLOWED_CEILINGS:
        raise ValueError(f"invalid claim_ceiling: {parsed['claim_ceiling']}")
    if not isinstance(parsed["certificate_status"], list) or not parsed["certificate_status"]:
        raise ValueError("certificate_status must be a nonempty array")
    if not all(isinstance(x, str) and 3 <= len(x) <= 120 for x in parsed["certificate_status"]):
        raise ValueError("certificate_status contains an invalid item")
    if not isinstance(parsed["reasoning"], str) or len(parsed["reasoning"].strip()) < 40:
        raise ValueError("reasoning is too short")


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
    p.add_argument("--max-corrective-attempts", type=int, default=3)
    args = p.parse_args()

    card_path = Path(args.card)
    model_path = Path(args.model_file)
    card = json.loads(card_path.read_text(encoding="utf-8"))
    base_prompt = (
        f"PASS ID: {args.pass_id}\n"
        "ADJUDICATE THIS SOURCE-GROUNDED CARD. "
        "Return all five required fields: state, construct_validity, certificate_status, claim_ceiling, reasoning.\n"
        + json.dumps(card, ensure_ascii=False, sort_keys=True)
    )

    attempt_receipts = []
    final_envelope = None
    final_content = None
    final_parsed = None
    previous_error = None

    for attempt in range(1, args.max_corrective_attempts + 1):
        corrective = ""
        if previous_error:
            corrective = (
                "\nCORRECTIVE REQUIREMENT: the previous response failed validation: "
                + previous_error
                + ". Produce a complete object satisfying the schema; do not omit reasoning."
            )
        prompt = base_prompt + corrective
        payload = {
            "model": args.model_id,
            "temperature": 0,
            "seed": (20261024 if args.pass_id == "PASS_A" else 20261025) + attempt - 1,
            "max_tokens": 700,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "schema": JSON_SCHEMA,
            },
        }
        envelope = post_json(args.url, payload)
        content = envelope["choices"][0]["message"]["content"]
        attempt_path = Path(f"{args.raw_output}.attempt{attempt}.txt")
        attempt_path.write_text(content + "\n", encoding="utf-8")
        receipt = {
            "attempt": attempt,
            "seed": payload["seed"],
            "prompt_sha256": sha256_bytes((SYSTEM + "\n" + prompt).encode("utf-8")),
            "raw_output_sha256": sha256_bytes(content.encode("utf-8")),
            "server_response_id": envelope.get("id"),
        }
        try:
            parsed = parse_json_object(content)
            validate(parsed)
        except Exception as exc:
            previous_error = f"{type(exc).__name__}: {exc}"
            receipt["validation"] = "FAIL"
            receipt["validation_error"] = previous_error
            attempt_receipts.append(receipt)
            continue
        receipt["validation"] = "PASS"
        attempt_receipts.append(receipt)
        final_envelope = envelope
        final_content = content
        final_parsed = parsed
        break

    if final_parsed is None or final_content is None or final_envelope is None:
        Path(f"{args.raw_output}.attempts.json").write_text(
            json.dumps(attempt_receipts, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise RuntimeError(f"all adjudication attempts failed validation: {previous_error}")

    Path(args.raw_output).write_text(final_content + "\n", encoding="utf-8")
    Path(f"{args.raw_output}.attempts.json").write_text(
        json.dumps(attempt_receipts, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    output = {
        "claim_id": card["claim_id"],
        "pass_id": args.pass_id,
        "source_snapshot_sha256": card["source_snapshot_sha256"],
        "state": final_parsed["state"],
        "construct_validity": final_parsed["construct_validity"],
        "certificate_status": [str(x) for x in final_parsed["certificate_status"]],
        "claim_ceiling": str(final_parsed["claim_ceiling"]),
        "reasoning": str(final_parsed["reasoning"]),
        "adjudicator_receipt": {
            "model_id": args.model_id,
            "model_artifact_sha256": sha256_bytes(model_path.read_bytes()),
            "system_prompt_sha256": sha256_bytes(SYSTEM.encode("utf-8")),
            "schema_sha256": sha256_bytes(json.dumps(JSON_SCHEMA, sort_keys=True).encode("utf-8")),
            "output_sha256": sha256_bytes(final_content.encode("utf-8")),
            "labels_seen": False,
            "other_pass_seen": False,
            "temperature": 0,
            "successful_attempt": len(attempt_receipts),
            "attempts": attempt_receipts,
            "llama_server_response_id": final_envelope.get("id"),
        },
    }
    Path(args.output).write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
