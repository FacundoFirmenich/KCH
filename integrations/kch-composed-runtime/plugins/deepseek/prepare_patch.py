"""Write an exact DSH overlay for an already configured KCH native state."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--native-root', required=True, type=Path)
p.add_argument('--data-dir', required=True, type=Path)
p.add_argument('--workspace-root', required=True, type=Path)
p.add_argument('--namespace', required=True)
p.add_argument('--profile', choices=('sdk', 'headless'), default='sdk',
               help='Application endpoint which must wait for KCH (default: sdk)')
p.add_argument('--output', required=True, type=Path)
args = p.parse_args()
config = {name: str(value.resolve(strict=True)) for name, value in {
    'nativeRoot': args.native_root, 'dataDir': args.data_dir,
    'workspaceRoot': args.workspace_root,
}.items()}
config['namespace'] = args.namespace
config['python'] = sys.executable
directory = Path(__file__).resolve().parent
probe = subprocess.run([sys.executable, str(directory / 'native_bridge.py')],
                       input=json.dumps({**config, 'action': 'probe'}),
                       text=True, capture_output=True, check=True)
state = json.loads(probe.stdout)
if not state['locksEnabled'] or not state['chainValid']:
    p.error('KCH state must already have enabled locks and a valid ledger; no settings were changed')
# DSH treats a failed external plugin as optional. Binding its service into
# required startup entries makes KCH failure stop the selected application.
# The pinned base agent-loop has no entry-level injection to preserve; the
# application endpoint dependencies below reproduce its shipped patch exactly.
endpoint = ({'id': 'sdk-jsonrpc-server', 'inject': ['sdkAppStartup', 'loader', 'kchDeepSeek']}
            if args.profile == 'sdk' else
            {'id': 'headless-runner', 'inject': ['headlessStartup', 'kchDeepSeek']})
patch = [
    {'insert': [{'id': 'kch-deepseek-native', 'name': str(directory / 'index.mjs'), 'config': config}]},
    {'id': 'agent-loop', 'inject': ['kchDeepSeek']},
    endpoint,
]
# JSON is a YAML subset accepted by the DSH ordered patch loader.
with args.output.open('x', encoding='utf-8') as output:
    json.dump(patch, output, ensure_ascii=False, indent=2)
    output.write('\n')
print(str(args.output.resolve()))
