"""Run the supported pinned DSH SDK launcher with KCH, without a model turn.

Requires pnpm, installed upstream dependencies, host artifacts, and the upstream
native flock addon. Output is retained in a new evidence directory. This test
creates its own KCH state and never changes the owner's active native state.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

PIN = '5badb15009ae1756c3afe0ae0cef1faafc290ccc'
PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parents[3]
NATIVE = REPO / 'construct_successors/KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2/vendor/kch-native-r33-0.11.33'


def launch(upstream: Path, evidence: Path, label: str, timeout: float) -> dict:
    # No provider key, user .env, telemetry setting, model request, or assistant
    # replay enters this child. An explicit DSH home scopes all runtime state.
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'USER', 'LANG') if key in os.environ}
    env.update(DSH_HOME=str(evidence / 'home'), DSH_TELEMETRY_MODE='DISABLED', DSH_TELEMETRY_DISABLED='1')
    cmd = ['pnpm', '--silent', 'dsh', '--profile', 'sdk', '--patch', str(evidence / 'kch-sdk.patch.json'),
           '--patch', str(evidence / 'probe.patch.json')]
    process = subprocess.Popen(cmd, cwd=upstream, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'cwd': str(evidence / 'workspace'), 'provider': 'deepseek-official', 'model': 'deepseek-flash'}}
    process.stdin.write((json.dumps(request) + '\n').encode()); process.stdin.flush()
    captured = {process.stdout: bytearray(), process.stderr: bytearray()}
    streams = list(captured)
    deadline = time.monotonic() + timeout
    shutdown_sent = False
    timed_out = False
    try:
        while process.poll() is None:
            if time.monotonic() >= deadline:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                break
            for stream in select.select(streams, [], [], .25)[0]:
                data = os.read(stream.fileno(), 65536)
                if not data:
                    streams.remove(stream)
                    continue
                captured[stream].extend(data)
                if len(captured[stream]) > 8 * 1024 * 1024:
                    raise RuntimeError('Launcher diagnostics exceeded 8 MiB')
                if stream is process.stdout and not shutdown_sent:
                    for line in captured[stream].splitlines():
                        try:
                            frame = json.loads(line)
                        except json.JSONDecodeError:
                            continue  # The next read may complete this line.
                        if frame.get('id') == 1:
                            process.stdin.write(b'{"jsonrpc":"2.0","id":2,"method":"shutdown"}\n')
                            process.stdin.flush()
                            shutdown_sent = True
                            break
        try:
            out, err = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            out, err = process.communicate()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
    captured[process.stdout].extend(out); captured[process.stderr].extend(err)
    stdout = bytes(captured[process.stdout]); stderr = bytes(captured[process.stderr])
    (evidence / f'{label}.stdout.jsonl').write_bytes(stdout)
    (evidence / f'{label}.stderr.log').write_bytes(stderr)
    frames = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    return {'exit_code': process.returncode, 'timed_out': timed_out, 'frames': frames,
            'stderr': stderr.decode('utf-8', errors='replace'), 'command': cmd}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsh-source', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=90)
    args = parser.parse_args()
    upstream = args.dsh_source.resolve(strict=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=upstream, text=True).strip()
    if head != PIN:
        parser.error(f'Expected upstream {PIN}; got {head}')
    if args.timeout <= 0:
        parser.error('timeout must be positive')
    evidence = args.evidence_dir.resolve(); evidence.mkdir(parents=True, exist_ok=False)
    workspace = evidence / 'workspace'; workspace.mkdir()
    native_data = evidence / 'native'; native_data.mkdir()
    source = REPO / 'integrations/kch-composed-runtime/README.md'
    protected = workspace / 'source-readme.md'; protected.write_bytes(source.read_bytes())
    os.environ['KCH_NATIVE_DATA'] = str(native_data)
    sys.path.insert(0, str(NATIVE / 'scripts'))
    import kch_native_state as state
    db = state.connect()
    state.set_setting(db, 'locks_enabled', 'true')
    db.execute('INSERT INTO locks(id,kind,pattern,created_at) VALUES(?,?,?,?)',
               ('launcher-protected', 'EXACT', state.normalize_file(str(protected), str(workspace)), state.utc_now()))
    db.commit(); db.close()
    subprocess.run([sys.executable, str(PLUGIN / 'prepare_patch.py'), '--native-root', str(NATIVE),
                    '--data-dir', str(native_data), '--workspace-root', str(workspace), '--namespace',
                    'launcher-proof', '--profile', 'sdk', '--output', str(evidence / 'kch-sdk.patch.json')], check=True)
    # The test observer calls real native tools on a real idle agent; it is not a
    # model adapter and cannot supply a model answer. The SDK remains the endpoint.
    patch = [{'id': 'session-log-deepseek', 'disabled': True}, {'insert': [{
        'id': 'kch-launcher-probe', 'name': str(PLUGIN / 'tests/launcher_probe.mjs'),
        'config': {'workspace': str(workspace), 'protectedPath': str(protected),
                   'output': str(evidence / 'probe-result.json')},
    }]}]
    (evidence / 'probe.patch.json').write_text(json.dumps(patch, indent=2) + '\n')
    positive = launch(upstream, evidence, 'enabled', args.timeout)
    assert not positive['timed_out'] and positive['exit_code'] == 0, positive
    assert not positive['stderr'].strip(), positive['stderr']
    handshake = next(frame for frame in positive['frames'] if frame.get('id') == 1)
    assert handshake['result']['serverInfo']['name'] == 'deepseek-harness-sdk-runtime', handshake
    assert any(frame.get('id') == 2 and frame.get('result') == {} for frame in positive['frames'])
    probe = json.loads((evidence / 'probe-result.json').read_text())
    assert probe['sourceUnchanged'] and probe['receipts'] == 2 and probe['failure'] is None, probe
    db = state.connect()
    valid, count = state.verify_chain(db)
    receipts = [dict(row) for row in db.execute("SELECT * FROM events WHERE event_name='DSHToolResult' ORDER BY id")]
    assert valid and len(receipts) == 2
    (evidence / 'native-receipts.json').write_text(json.dumps(receipts, indent=2) + '\n')
    state.set_setting(db, 'locks_enabled', 'false'); db.close()
    negative = launch(upstream, evidence, 'disabled', args.timeout)
    assert not negative['timed_out'] and negative['exit_code'] != 0, negative
    assert 'KCH_LOCKS_OR_LEDGER_NOT_READY' in negative['stderr'], negative
    assert not any(frame.get('id') == 1 and 'result' in frame for frame in negative['frames']), negative
    db = state.connect()
    assert state.setting(db, 'locks_enabled') == 'false'
    final_valid, final_count = state.verify_chain(db); db.close()
    assert final_valid and final_count == count
    result = {
        'gate': 'PASS', 'upstream_commit': PIN, 'profile': 'sdk', 'launcher': 'pnpm --silent dsh',
        'upstream_package_version': json.loads((upstream / 'package.json').read_text())['version'],
        'sdk_handshake': handshake['result'], 'positive_exit': positive['exit_code'],
        'disabled_locks_exit': negative['exit_code'], 'native_ledger_valid': final_valid,
        'native_events': final_count, 'native_tool_receipts': len(receipts),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'assertions': ['SDK initialization and clean shutdown', 'KCH plugin active', 'real protected-file read',
                       'real overwrite denied', 'original file unchanged', 'native receipts and hash chain',
                       'same generated patch fails startup after locks disabled', 'no policy self-enablement'],
        'inference': {'session_prompts_sent': 0, 'model_adapter_substituted': False,
                      'paid_model_calls_performed': False, 'model_quality_measured': False},
        'limits': ['No model turn', 'Source launcher, not published npm/wheel artifact',
                   'sdk profile only; headless dependency emitted but not boot-tested',
                   'Tool boundary does not confine trusted same-process plugins'],
    }
    (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
