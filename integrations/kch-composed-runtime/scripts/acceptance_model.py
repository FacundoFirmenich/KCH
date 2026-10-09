#!/usr/bin/env python3
"""Run the KCH cycle against an explicitly configured real loopback model server.

No model is downloaded, started, selected or emulated here. No tool call is
manufactured. Model messages are passed from ChatCompletionsClient to Runtime.
The bounded task uses existing repository bytes and records every attempt.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from kch_composed.model import ChatCompletionsClient
from kch_composed.runtime import Runtime


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class RecordingClient(ChatCompletionsClient):
    """Record genuine provider envelopes without modifying their assistant data."""
    def __init__(self, *args, output, **kwargs):
        super().__init__(*args, **kwargs)
        self.output, self.count = output, 0

    def complete(self, messages, tools):
        self.count += 1
        prefix = self.output / f"request-{self.count:02d}"
        dump(prefix.with_suffix('.json'), {"messages": messages, "tools": tools,
             "options": self.request_options})
        start = time.monotonic()
        try:
            message = super().complete(messages, tools)
        except Exception as exc:
            if self.last_response is not None:
                dump(self.output / f"response-{self.count:02d}.json", self.last_response)
            dump(self.output / f"error-{self.count:02d}.json", {
                "type": type(exc).__name__, "message": str(exc),
                "elapsed_seconds": time.monotonic() - start})
            raise
        dump(self.output / f"response-{self.count:02d}.json", self.last_response)
        return message


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True, help='Explicit loopback Chat Completions endpoint')
    parser.add_argument('--model', required=True)
    parser.add_argument('--weights', type=Path, required=True, help='Real local model weights; hash is recorded')
    parser.add_argument('--output', type=Path, required=True, help='New evidence directory; must not exist')
    parser.add_argument('--source', default='integrations/kch-composed-runtime/pyproject.toml')
    parser.add_argument('--max-steps', type=int, default=8)
    parser.add_argument('--max-tokens', type=int, default=768)
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args(argv)
    host = urlsplit(args.endpoint).hostname
    try:
        loopback = host == 'localhost' or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        parser.error('This cost-free gate only accepts an explicitly supplied loopback endpoint')
    source = (ROOT / args.source).resolve(strict=True)
    if not source.is_relative_to(ROOT) or not source.is_file():
        parser.error('Source must be an existing repository file')
    original = source.read_bytes()
    if len(original) > 4096:
        parser.error('Acceptance source must fit within the preregistered 4096-byte bound')
    weights = args.weights.resolve(strict=True)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'source-snapshot.bin').write_bytes(original)
    task = (f"Execute this task using the tools. First read_file the existing file {args.source!r} "
            "with max_bytes 4096. Then memory_ingest that same file with source_id 'acceptance-source'. "
            "Then memory_recall source_id 'acceptance-source'. Wait for tool results. "
            "After these three operations have succeeded, report briefly what you did and the "
            "source SHA-256 shown by the tools. Do not invent tool results. /no_think")
    configuration = {'schema': 'kch.live-model-acceptance.v1',
        'registered_at': datetime.now(timezone.utc).isoformat(),
        'working_tree_changes_present': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'endpoint': args.endpoint, 'model': args.model,
        'weights': {'name': weights.name, 'bytes': weights.stat().st_size, 'sha256': sha_file(weights)},
        'source': {'path': args.source, 'bytes': len(original), 'sha256': hashlib.sha256(original).hexdigest()},
        'prompt': task, 'max_steps': args.max_steps, 'max_tokens': args.max_tokens,
        'acceptance': ['real provider response received', 'model requested read_file, memory_ingest and memory_recall',
                       'read and recall bytes equal existing source', 'ingest SHA-256 equals existing source',
                       'runtime completed', 'journal verifies'],
        'claim_ceiling': 'One bounded real local inference/tool/memory integration case; no benchmark or model quality claim'}
    dump(out / 'preregistration.json', configuration)
    runtime = Runtime(repository=ROOT, workspace=ROOT, state=out / 'state',
                      principal='local-acceptance', session='live-read-memory',
                      enabled={'read_file', 'memory_ingest', 'memory_recall'})
    client = RecordingClient(args.endpoint, args.model, timeout=args.timeout, output=out,
                            request_options={'max_tokens': args.max_tokens, 'temperature': 0.1, 'seed': 42})
    start = time.monotonic()
    error = None
    result = None
    try:
        result = runtime.run(client, task, max_steps=args.max_steps,
                             binding={'endpoint': client.endpoint, 'model': args.model,
                                      'weights_sha256': configuration['weights']['sha256']})
    except Exception as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
    calls = runtime.journal.calls()
    events = runtime.journal.events()
    successful = [c for c in calls if c['status'] == 'DONE' and c['result'].get('ok')]
    checks = {'provider_responses': sum(e['kind'] == 'model.received' for e in events) > 0,
              'runtime_completed': bool(result and result.get('status') == 'COMPLETED'),
              'journal_verifies': runtime.journal.verify() is True}
    for tool in ('read_file', 'memory_ingest', 'memory_recall'):
        selected = [c for c in successful if c['name'] == tool]
        checks['model_' + tool] = bool(selected)
        matching = False
        for call in selected:
            value = call['result']['value']
            try:
                if tool == 'memory_ingest':
                    matching |= value['sha256'] == configuration['source']['sha256']
                else:
                    content = value['content']
                    matching |= content['encoding'] == 'base64' and base64.b64decode(content['data'], validate=True) == original
            except (KeyError, ValueError, TypeError):
                pass
        checks[tool + '_exact_source'] = matching
    status = 'PASS_BOUNDED_LOCAL_CASE' if all(checks.values()) else 'FAIL_BOUNDED_LOCAL_CASE'
    receipt = {'status': status, 'checks': checks, 'runtime_result': result,
               'error': error, 'elapsed_seconds': time.monotonic() - start,
               'http_request_attempts': client.count,
               'usage': [e['payload'].get('usage') for e in events if e['kind'] == 'model.received'],
               'claim_ceiling': configuration['claim_ceiling']}
    dump(out / 'receipt.json', receipt)
    dump(out / 'journal-events.json', events)
    dump(out / 'tool-receipts.json', calls)
    runtime.close()
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if status.startswith('PASS') else 1

if __name__ == '__main__':
    raise SystemExit(main())
