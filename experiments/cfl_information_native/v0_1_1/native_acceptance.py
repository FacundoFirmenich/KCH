#!/usr/bin/env python3
"""Native-model CPU/BF16 acceptance for CFL-INFORMATION-CONTRACT-SHADOW-001.

Explicit execution-profile extension of the delivered 0.1.0 GPU/NF4 pilot.
Original TALM/TALON, projection, prompts, seeds and sampling are preserved.
This is engineering acceptance, not a GPU replication or semantic experiment.
No fixtures, synthetic logits, replacement models or sampling substitutions.
"""
from __future__ import annotations
import ast
import base64
import copy
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import platform
import random
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone

import numpy as np
import torch
import transformers
from huggingface_hub import HfApi
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
OUT = Path(os.environ.get('CFL_NATIVE_OUTPUT', 'native_results')).resolve()
MODEL_ID = 'Qwen/Qwen3.5-4B-Base'
SEED = 14
PROFILE = 'github_actions_cpu_bfloat16_unquantized'
UPSTREAM_HASHES = {
    'src/shadow_campaign.py': '711d509a1926fecb98a24bfdae97d1f4efbb3461188abf64647ebc79f8008c8e',
    'upstream/cfldr_plus_v0_4_repaired.py': 'ca295f590eb76fcde977c3983ff4ae81692079af31bdfbc4ce4301586e0ad71d',
    'upstream/canonical_talm_talon.py': '37170a0e1beb337e529681178b8f13800774fe6656c043c77727d018c665ef71',
}
ACTIONS = ('talon_mass_right', 'talon_mass_left', 'talm_mass_right_soft', 'baseline')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalize(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            raise ValueError('NaN in receipt')
        return {'extended_real': 'POSITIVE_INFINITY' if value > 0 else 'NEGATIVE_INFINITY'}
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [normalize(v) for v in value]
    return value


def canonical(value):
    return json.dumps(normalize(value), sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def array(t):
    t = t.detach().cpu()
    if t.dtype == torch.bfloat16:
        t = t.float()
    return t.numpy().copy()


def tensor_sha(x):
    x = np.asarray(x)
    return sha(canonical({'shape': list(x.shape), 'dtype': x.dtype.str}) + x.tobytes(order='C'))


def rng_state():
    return (random.getstate(), np.random.get_state(), torch.get_rng_state().clone())


def same_rng(a, b):
    return (a[0] == b[0] and a[1][0] == b[1][0]
            and np.array_equal(a[1][1], b[1][1]) and a[1][2:] == b[1][2:]
            and torch.equal(a[2], b[2]))


def restore_rng(state):
    random.setstate(state[0]); np.random.set_state(state[1]); torch.set_rng_state(state[2])


def comparison(a, b, temperature=1.0):
    """Float64 diagnostics; finite logits, not softmax underflow, define support."""
    if temperature <= 0 or not math.isfinite(temperature):
        raise ValueError('Invalid temperature')
    def dist(x):
        x = np.asarray(x, dtype=np.float64)
        if x.ndim != 1 or np.isnan(x).any() or np.isposinf(x).any():
            raise ValueError('Invalid logits')
        s = np.isfinite(x)
        if not s.any():
            raise ValueError('Empty support')
        z = (x[s] - np.max(x[s])) / temperature
        lp = np.full_like(x, -np.inf)
        lp[s] = z - np.log(np.exp(z).sum())
        return lp, np.exp(lp), s
    lp, p, sp = dist(a); lq, q, sq = dist(b)
    def kl(l1, p1, s1, l2, s2):
        if np.any(s1 & ~s2):
            return math.inf
        v = float(np.dot(p1[s1], l1[s1] - l2[s1]))
        if v < -1e-10 or not math.isfinite(v):
            raise ValueError('Invalid finite KL')
        return v
    lm = np.logaddexp(lp, lq) - math.log(2)
    ai, bi = int(np.argmax(a)), int(np.argmax(b))
    at, bt = int(np.sum(a == a[ai])), int(np.sum(b == b[bi]))
    return {
        'kl_forward': kl(lp, p, sp, lq, sq), 'kl_reverse': kl(lq, q, sq, lp, sp),
        'js_divergence': .5 * (kl(lp, p, sp, lm, sp | sq) + kl(lq, q, sq, lm, sp | sq)),
        'total_variation': float(np.abs(p - q).sum() / 2),
        'entropy_delta': float(-np.dot(q[sq], lq[sq]) + np.dot(p[sp], lp[sp])),
        'lost_support_count': int(np.sum(sp & ~sq)), 'gained_support_count': int(np.sum(sq & ~sp)),
        'base_support_size': int(sp.sum()), 'candidate_support_size': int(sq.sum()),
        'base_underflow_count': int(np.sum(sp & (p == 0))),
        'candidate_underflow_count': int(np.sum(sq & (q == 0))),
        'base_top1': ai, 'candidate_top1': bi,
        'unique_top1_preserved': bool(at == bt == 1 and ai == bi),
    }


def ray_metrics(z, u, temperature):
    s = np.isfinite(z)
    if not np.isfinite(u[s]).all():
        raise ValueError('Nonfinite direction')
    a = z[s].astype(np.float64) / temperature
    a -= a.max(); lp = a - np.log(np.exp(a).sum()); p = np.exp(lp)
    v = (u[s].astype(np.float64) - u[s][0]) / temperature
    w = lp + v; mx = w.max(); cumulant = float(mx + np.log(np.exp(w - mx).sum()))
    q = np.exp(w - cumulant); mean = float(np.dot(q, v))
    return {'scale': 1.0, 'fisher_directional': float(np.dot(q, (v - mean) ** 2)),
            'kl_cumulant_identity': cumulant - float(np.dot(p, v)),
            'hoeffding_upper_bound': float(np.ptp(v) ** 2 / 8)}


class Ledger:
    def __init__(self, contract):
        self.root = OUT / 'capture'; self.objects = self.root / 'objects'
        self.objects.mkdir(parents=True, exist_ok=True)
        self.contract = contract; self.head = sha(canonical(contract)); self.events = []
        write_json(self.root / 'contract.json', contract)
        self.db = sqlite3.connect(self.root / 'receipts.sqlite')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE receipts (seq INTEGER PRIMARY KEY,event_id TEXT UNIQUE,previous_sha TEXT,body TEXT,sha TEXT)')
        self.db.executescript("CREATE TRIGGER no_update BEFORE UPDATE ON receipts BEGIN SELECT RAISE(ABORT,'append only'); END; CREATE TRIGGER no_delete BEFORE DELETE ON receipts BEGIN SELECT RAISE(ABORT,'append only'); END;")
        self.db.commit()
    def append(self, event, tensors):
        import io
        for x in tensors.values():
            if x.size == 0 or np.isnan(x).any() or np.isposinf(x).any():
                raise ValueError('Invalid captured tensor')
        b = io.BytesIO(); np.savez_compressed(b, **tensors); blob = b.getvalue(); h = sha(blob)
        if sum(p.stat().st_size for p in self.objects.glob('*.npz')) + len(blob) > 512 * 1024**2:
            raise ValueError('Capture budget exceeded')
        (self.objects / (h + '.npz')).write_bytes(blob)
        body = {'metadata': event, 'object_sha256': h,
                'arrays': {k: {'shape': list(v.shape), 'dtype': v.dtype.str,
                               'tensor_sha256': tensor_sha(v)} for k, v in tensors.items()},
                'contract_sha256': sha(canonical(self.contract)),
                'captured_at_utc': datetime.now(timezone.utc).isoformat()}
        eid = f"{event['prompt_id']}:{SEED}:{event['step']}:{event['operator']}"
        body['event_id'] = eid; raw = canonical(body); newhead = sha(self.head.encode() + raw)
        with self.db:
            self.db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',
                            (len(self.events), eid, self.head, raw.decode(), newhead))
        self.head = newhead; self.events.append(body)
    def close(self):
        self.db.close()


def materialize_upstream():
    path = REPO / 'experiments/rdss_temporal_shadow/v0_1/RDSS_TEMPORAL_SHADOW_GATE_V0_1.ipynb'
    nb = json.loads(path.read_text())
    embedded = None
    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
        source = ''.join(cell['source'])
        if 'EMBEDDED' not in source:
            continue
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'EMBEDDED' for t in node.targets):
                embedded = json.loads(ast.literal_eval(node.value.args[0]))
    if embedded is None:
        raise ValueError('No original runtime found')
    target = OUT / 'upstream_exact'
    for name, encoded in embedded.items():
        dest = (target / name).resolve()
        if not dest.is_relative_to(target.resolve()):
            raise ValueError('Unsafe embedded path')
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(base64.b64decode(encoded))
    for name, expected in UPSTREAM_HASHES.items():
        if sha((target / name).read_bytes()) != expected:
            raise ValueError('Upstream source mismatch: ' + name)
    return target, sha(path.read_bytes())


def observer_class(baseclass, upstream, ledger, channel):
    class Observed(baseclass):
        _cfl_observer = True
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.suffix = None; self.pending = None; self.live = None; self.suffix_description = None
        def _capture(self, ids, scores):
            state = rng_state(); original_ids = ids.clone(); original_scores = scores.clone()
            try:
                super()._capture(ids, scores)
                if self.suffix is None:
                    raise ValueError('Actual native suffix was not bound')
                pending = []
                for action in ACTIONS:
                    raw, _ = upstream.apply_action_once(action, ids.clone(), scores.clone())
                    projected = scores.clone() if action == 'baseline' else upstream.project_top1(scores.clone(), raw.clone())
                    postbase = self.suffix(ids.clone(), scores.clone())
                    post = self.suffix(ids.clone(), projected.clone())
                    arrays = {'operator_input': array(scores), 'raw_candidate': array(raw),
                              'projected_candidate': array(projected), 'post_baseline_replay': array(postbase),
                              'post_candidate_replay': array(post), 'prefix_token_ids': array(ids)}
                    meta = {**channel, 'prompt_id': self.prompt_spec.id, 'step': int(self.step_index),
                            'operator': action, 'origin': 'native_capture',
                            'probe_state': 'fresh_counterfactual_not_live_processor',
                            'input_torch_dtype': str(scores.dtype), 'prefix_sha256': tensor_sha(arrays['prefix_token_ids']),
                            'raw_comparison': comparison(arrays['operator_input'][0], arrays['raw_candidate'][0], channel['temperature']),
                            'projected_comparison': comparison(arrays['operator_input'][0], arrays['projected_candidate'][0], channel['temperature']),
                            'post_comparison': comparison(arrays['post_baseline_replay'][0], arrays['post_candidate_replay'][0]),
                            'suffix_description': self.suffix_description}
                    a, b = arrays['operator_input'][0], arrays['raw_candidate'][0]
                    if np.array_equal(np.isfinite(a), np.isfinite(b)):
                        u = np.zeros_like(a, dtype=np.float64); mask = np.isfinite(a)
                        u[mask] = b[mask].astype(np.float64) - a[mask].astype(np.float64)
                        meta['raw_endpoint_ray'] = ray_metrics(a, u, channel['temperature'])
                        meta['raw_endpoint_ray']['interpretation'] = 'realized_endpoint_direction_not_derivative_of_stateful_operator'
                    pending.append((meta, arrays))
                if not torch.equal(ids, original_ids) or not torch.equal(scores, original_scores):
                    raise ValueError('Observer mutated input')
                if not same_rng(state, rng_state()):
                    raise ValueError('Observer consumed random state')
                self.pending = pending
            finally:
                restore_rng(state)
        def __call__(self, ids, scores):
            value = super().__call__(ids, scores)
            if self.pending is not None:
                self.live = value.detach().clone()
            return value
    return Observed


class SuffixContext:
    allowed = {'TemperatureLogitsWarper', 'TopPLogitsWarper', 'TopKLogitsWarper', 'MinPLogitsWarper', 'LogitNormalization'}
    def __init__(self, model, channel, ledger):
        self.model = model; self.channel = channel; self.ledger = ledger
    def __enter__(self):
        self.local = vars(self.model).get('_get_logits_processor')
        self.hadlocal = '_get_logits_processor' in vars(self.model)
        original = self.model._get_logits_processor
        def compose(*args, **kwargs):
            chain = original(*args, **kwargs)
            found = [(i, p) for i, p in enumerate(chain) if getattr(p, '_cfl_observer', False)]
            if len(found) != 1:
                raise ValueError('Expected one observer')
            index, obs = found[0]; suffix = list(chain[index+1:])
            descriptions = []
            for p in suffix:
                cls = type(p)
                if cls.__name__ not in self.allowed or not cls.__module__.startswith('transformers.generation.logits_process'):
                    raise ValueError('Unknown final processor: ' + cls.__name__)
                descriptions.append({'name': cls.__name__, 'state': vars(p), 'source_sha256': sha(inspect.getsource(cls).encode())})
            temperatures = [p for p in suffix if type(p).__name__ == 'TemperatureLogitsWarper']
            topp = [p for p in suffix if type(p).__name__ == 'TopPLogitsWarper']
            if self.channel['temperature'] != 1 and (len(temperatures) != 1 or temperatures[0].temperature != self.channel['temperature']):
                raise ValueError('Native temperature stage missing or changed')
            if self.channel['top_p'] < 1 and (len(topp) != 1 or topp[0].top_p != self.channel['top_p']):
                raise ValueError('Native top-p stage missing or changed')
            if 'logits_warper(' in inspect.getsource(self.model._sample):
                raise ValueError('Separate downstream warper not captured')
            replay = type(chain)(copy.deepcopy(suffix))
            obs.suffix = replay
            obs.suffix_description = {'processors': descriptions,
                'composition_source_sha256': sha(inspect.getsource(original).encode()),
                'sample_source_sha256': sha(inspect.getsource(self.model._sample).encode())}
            ledger = self.ledger
            class Tap:
                def __call__(self, ids, scores):
                    if obs.pending is not None:
                        state = rng_state()
                        try:
                            predicted = replay(ids.clone(), obs.live.clone())
                            if predicted.dtype != scores.dtype or not torch.equal(predicted, scores):
                                raise ValueError('Native final scores differ from exact replay')
                            if not same_rng(state, rng_state()):
                                raise ValueError('Suffix replay consumed RNG')
                            for meta, arrays in obs.pending:
                                arrays['actual_live_projected'] = array(obs.live)
                                arrays['actual_live_post'] = array(scores)
                                meta['native_suffix_verified'] = True
                                ledger.append(meta, arrays)
                            obs.pending = None
                        finally:
                            restore_rng(state)
                    return scores
            return type(chain)(list(chain) + [Tap()])
        self.model._get_logits_processor = compose
        return self
    def __exit__(self, *args):
        if self.hadlocal:
            self.model._get_logits_processor = self.local
        else:
            delattr(self.model, '_get_logits_processor')


def verify_native(ledger, rows, contract):
    grouped = {}
    for row in rows:
        if row['status'] != 'ok':
            raise ValueError('Generation failed')
        group = grouped.setdefault((row['prompt_id'], row['seed']), {})
        if row['method'] in group:
            raise ValueError('Duplicate generation')
        group[row['method']] = row
    if set(grouped) != {(p, SEED) for p in contract['prompt_ids']}:
        raise ValueError('Wrong cohort')
    for group in grouped.values():
        if set(group) != {'fixed_tmr', 'rdss_shadow_tmr'}:
            raise ValueError('Unpaired cohort')
        if group['fixed_tmr']['generated_token_ids_json'] != group['rdss_shadow_tmr']['generated_token_ids_json']:
            raise ValueError('Token noninterference failure')
    previous = sha(canonical(contract)); observed = {}
    with sqlite3.connect(f'file:{ledger.root / "receipts.sqlite"}?mode=ro', uri=True) as db:
        receipts = db.execute('SELECT seq,event_id,previous_sha,body,sha FROM receipts ORDER BY seq').fetchall()
    if not receipts:
        raise ValueError('No native captures')
    for n, (seq, eid, prev, raw, current) in enumerate(receipts):
        body = json.loads(raw)
        if n != seq or prev != previous or sha(prev.encode() + raw.encode()) != current or canonical(body) != raw.encode():
            raise ValueError('Broken hash chain')
        meta = body['metadata']; key = (meta['prompt_id'], SEED); row = grouped[key]['rdss_shadow_tmr']
        if not meta['native_suffix_verified']:
            raise ValueError('Unverified native suffix')
        path = ledger.objects / (body['object_sha256'] + '.npz')
        if sha(path.read_bytes()) != body['object_sha256']:
            raise ValueError('Tensor archive changed')
        with np.load(path, allow_pickle=False) as tensors:
            for name, identity in body['arrays'].items():
                if tensor_sha(tensors[name]) != identity['tensor_sha256']:
                    raise ValueError('Tensor identity changed')
            ids = json.loads(row['generated_token_ids_json']); plen = row['prompt_length']; step = meta['step']
            prefix = tensors['prefix_token_ids']
            if not (0 <= step < len(ids)) or list(prefix.shape) != [1, plen + step] or prefix[0, plen:].tolist() != ids[:step]:
                raise ValueError('Prefix/trajectory mismatch')
        observed.setdefault((key, step), set()).add(meta['operator']); previous = current
    for key, group in grouped.items():
        count = len(json.loads(group['rdss_shadow_tmr']['generated_token_ids_json']))
        for step in (0, 16, 32, 64):
            if step < count and observed.get((key, step)) != set(ACTIONS):
                raise ValueError('Incomplete planned checkpoint')
    return {'gate': 'CFL-INFORMATION-CONTRACT-SHADOW-001', 'native': 'PASS_SCOPED_ENGINEERING',
            'execution_profile': PROFILE, 'gpu_nf4_replication': False,
            'model_id': MODEL_ID, 'model_revision': contract['model_revision'],
            'paired_prompts': len(grouped), 'model_generations': len(rows),
            'sampled_token_count_including_both_arms': sum(r['new_token_count'] for r in rows),
            'native_events': len(receipts), 'all_planned_checkpoints_complete': True,
            'exact_token_identity': True, 'native_post_suffix_verified': True,
            'ledger_head': previous, 'authority': 'NONE',
            'semantic_improvement_claim': False, 'energy_measurement': None}


def main():
    started = time.time()
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError('Refusing to overwrite a run')
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4); torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    target, notebook_hash = materialize_upstream()
    spec = importlib.util.spec_from_file_location('native_existing_shadow', target / 'src/shadow_campaign.py')
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)
    v = m.v04
    if v.MODEL_ID != MODEL_ID:
        raise ValueError('Unexpected model')
    revision = HfApi().model_info(MODEL_ID).sha
    if len(revision) != 40:
        raise ValueError('Immutable model revision required')
    prompts = list(v.PROMPTS[:2])
    contract = {'gate': 'CFL-INFORMATION-CONTRACT-SHADOW-001', 'version': '0.1.1',
        'mode': 'SHADOW_ONLY', 'authority': 'NONE', 'data_split': 'development',
        'execution_profile': PROFILE, 'gpu_nf4_replication': False,
        'explicit_profile_change': 'CPU/BF16 unquantized instead of GPU/NF4; no cross-profile result equivalence assumed',
        'model_id': MODEL_ID, 'model_revision': revision, 'tokenizer_revision': revision,
        'seed': SEED, 'prompt_ids': [p.id for p in prompts],
        'prompt_suite_sha256': v.PROMPT_SUITE_HASH, 'method_config_sha256': v.METHOD_CONFIG_HASH,
        'temperature': v.BASE_TEMPERATURE, 'top_p': v.BASE_TOP_P,
        'upstream_hashes': UPSTREAM_HASHES, 'source_notebook_sha256': notebook_hash,
        'runner_source_sha256': sha(Path(__file__).read_bytes()),
        'git_commit': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
        'python': platform.python_version(), 'torch': torch.__version__,
        'transformers': transformers.__version__, 'quantization': 'none', 'dtype': 'bfloat16',
        'device': 'cpu', 'cpu_count': os.cpu_count(),
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'historical_data_can_promote': False, 'protected_reserve_touched': False}
    write_json(OUT / 'pilot_freeze.json', contract)
    print('FREEZE', json.dumps(contract), flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=revision, trust_remote_code=False, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=revision,
        trust_remote_code=False, torch_dtype=torch.bfloat16, device_map={'': 'cpu'},
        low_cpu_mem_usage=True, attn_implementation=v.ATTN_IMPLEMENTATION)
    model.eval()
    if any(p.is_meta or p.device.type != 'cpu' for p in model.parameters()):
        raise ValueError('Unexpected model placement')
    write_json(OUT / 'model_loaded.json', {'model_class': type(model).__name__,
        'parameter_count': sum(p.numel() for p in model.parameters()),
        'dtypes': sorted({str(p.dtype) for p in model.parameters()}),
        'generation_config': model.generation_config.to_dict(),
        'model_config': model.config.to_dict(), 'load_elapsed_seconds': time.time() - started})
    print('MODEL_LOADED', type(model).__name__, flush=True)
    channel = {'model_id': MODEL_ID, 'model_revision': revision, 'tokenizer_revision': revision,
               'seed': SEED, 'temperature': v.BASE_TEMPERATURE, 'top_p': v.BASE_TOP_P,
               'execution_profile': PROFILE}
    ledger = Ledger(contract); rows = []
    original = m.TMRCommonStateShadowProcessor
    m.TMRCommonStateShadowProcessor = observer_class(original, v, ledger, channel)
    try:
        for ps in prompts:
            print('GENERATING_FIXED', ps.id, flush=True)
            fixed = m.generate_fixed_one(tokenizer, model, torch.device('cpu'), ps, SEED)
            rows.append(fixed)
            (OUT / 'campaign_rows.jsonl').write_bytes(b''.join(canonical(r) + b'\n' for r in rows))
            print('GENERATING_SHADOW', ps.id, 'fixed_tokens', fixed['new_token_count'], flush=True)
            with SuffixContext(model, channel, ledger):
                shadow = m.generate_shadow_one(tokenizer, model, torch.device('cpu'), ps, SEED)
            rows.append(shadow)
            (OUT / 'campaign_rows.jsonl').write_bytes(b''.join(canonical(r) + b'\n' for r in rows))
            if fixed['generated_token_ids_json'] != shadow['generated_token_ids_json']:
                raise ValueError('SHADOW altered generated tokens')
            print('PAIR_MATCH', ps.id, shadow['new_token_count'], flush=True)
    finally:
        m.TMRCommonStateShadowProcessor = original; ledger.close()
    verdict = verify_native(ledger, rows, contract)
    verdict['wall_seconds'] = time.time() - started
    write_json(OUT / 'native_acceptance.json', verdict)
    print('NATIVE_VERDICT', json.dumps(verdict), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        write_json(OUT / 'failure.json', {'status': 'NATIVE_ACCEPTANCE_FAILED', 'error_type': type(exc).__name__,
            'error': str(exc), 'traceback': traceback.format_exc(), 'authority': 'NONE'})
        raise
    finally:
        if OUT.exists():
            hashes = {str(p.relative_to(OUT)): sha(p.read_bytes()) for p in sorted(OUT.rglob('*'))
                      if p.is_file() and p.name != 'SHA256SUMS.json' and '__pycache__' not in p.parts}
            write_json(OUT / 'SHA256SUMS.json', hashes)
