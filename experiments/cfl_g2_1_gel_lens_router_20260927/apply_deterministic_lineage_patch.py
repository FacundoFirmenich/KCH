#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply_deterministic_lineage_patch.py RUNNER_PATH')
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
old = '''    if variant == "DIN_LINEAGE_SHUFFLED":\n        seed = int(hashlib.sha256(f"{t}:{lineage}".encode()).hexdigest()[:8], 16)\n        perm = np.random.default_rng(seed).permutation(len(angles))\n'''
new = '''    if variant == "DIN_LINEAGE_SHUFFLED":\n        seed_payload = canonical_json({\n            "program": PROGRAM_ID,\n            "variant": variant,\n            "t": int(t),\n            "source_t": int(source_t),\n            "config": asdict(cfg),\n            "n_angles": int(len(angles)),\n        })\n        seed = int(hashlib.sha256(seed_payload.encode()).hexdigest()[:8], 16)\n        perm = np.random.default_rng(seed).permutation(len(angles))\n'''
count = text.count(old)
if count != 1:
    raise SystemExit(f'patch contract failed: expected 1 occurrence, found {count}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
