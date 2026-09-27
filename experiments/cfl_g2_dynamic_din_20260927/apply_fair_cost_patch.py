#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply_fair_cost_patch.py RUNNER_PATH')
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
replacements = [
    (
'''    valid: bool
    lineage_hash: str


''',
'''    valid: bool
    lineage_hash: str
    seconds: float


'''
    ),
    (
'''    valid = all(r.valid for r in (x1r, x2r, h12r, h21r))
    return ClosureState(t, x1r.x, x2r.x, h12, h21, fused, reliability, hol, valid, lineage_hash(payload))
''',
'''    valid = all(r.valid for r in (x1r, x2r, h12r, h21r))
    closure_seconds = x1r.seconds + x2r.seconds + h12r.seconds + h21r.seconds
    return ClosureState(t, x1r.x, x2r.x, h12, h21, fused, reliability, hol, valid, lineage_hash(payload), closure_seconds)
'''
    ),
    (
'''    closures = [closure_for_frame(t, systems, alpha) for t in range(T)]
    if not all(c.valid for c in closures):
''',
'''    closures = [closure_for_frame(t, systems, alpha) for t in range(T)]
    closure_total_seconds = float(sum(c.seconds for c in closures))
    if not all(c.valid for c in closures):
'''
    ),
    (
'''        method_cost[method] = seconds
''',
'''        method_cost[method] = seconds + (closure_total_seconds if method.startswith("DIN_") else 0.0)
'''
    ),
    (
'''        "lineage_hash": c.lineage_hash,
    } for c in closures]
''',
'''        "lineage_hash": c.lineage_hash,
        "construction_seconds": c.seconds,
    } for c in closures]
'''
    ),
    (
'''        "false_closure_audit": false_closures,
        "adjudication": adjudication,
''',
'''        "false_closure_audit": false_closures,
        "closure_precomputation_seconds": closure_total_seconds,
        "adjudication": adjudication,
'''
    ),
]
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'patch contract failed: expected one occurrence, got {count}: {old[:80]!r}')
    text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
