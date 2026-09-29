#!/usr/bin/env python3
"""Reviewed wrapper reconciliation with Python-version-independent source hashes.
The five exercised definitions are textually identical across the delivered and
GitHub notebook wrappers. AST serialization differs between Python 3.11/3.13;
we hash their exact extracted source text, not interpreter-specific AST dumps.
No operator, prompt, projection or generation body is changed.
"""
import ast
from pathlib import Path
import traceback
import native_acceptance as m

REVIEWED = '66b4c1f717ee2e2759baa05c06a50b1ecb95e098d67351d0acb394962fe4f67b'
DEFINITION_HASHES = {
 'raw_state_features':'e61b3fdd07e40dbff694a9e6110ab2384c28893808d8c0c92a2b6c63f847e91c',
 'TMRCommonStateShadowProcessor':'02386d6a8f1990127bb86c10ea2fdcf229b47bf6884d860b90e406ca05b5a768',
 'generation_kwargs':'235be53f84fe9164e09a5cab6f61f3d27baa8d56cb59d2901b435f6ece119b9d',
 'generate_shadow_one':'49b5fea603cdc8cfd24a2bcd42a6fca18115b1972bd475778f5597e7f63fc1d6',
 'generate_fixed_one':'5d87e0e4ddf76bfba2107b73958e546996de61e53584876b46a5beb43f9e40d2',
}
m.UPSTREAM_HASHES['src/shadow_campaign.py'] = REVIEWED
original_materialize = m.materialize_upstream

def checked_materialize():
    target, digest = original_materialize()
    source=(target/'src/shadow_campaign.py').read_text()
    tree=ast.parse(source)
    observed={n.name:m.sha(ast.get_source_segment(source,n).encode()) for n in tree.body
              if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in DEFINITION_HASHES}
    if observed != DEFINITION_HASHES:
        raise ValueError('Previously reviewed executable source definitions changed')
    m.write_json(m.OUT/'source_reconciliation.json',{
        'prior_delivery_sha256':'711d509a1926fecb98a24bfdae97d1f4efbb3461188abf64647ebc79f8008c8e',
        'reviewed_notebook_wrapper_sha256':REVIEWED,'executed_definitions_textually_identical':True,
        'executed_definition_sha256':DEFINITION_HASHES,
        'prior_failed_runs':[36581643705,36582390150],
        'reviewed_runner_sha256':m.sha(Path(__file__).read_bytes()),
        'protected_reserve_touched':False,'authority':'NONE'})
    return target,digest

m.materialize_upstream=checked_materialize
if __name__ == '__main__':
    try:
        m.main()
    except BaseException as exc:
        m.OUT.mkdir(parents=True,exist_ok=True)
        m.write_json(m.OUT/'failure.json',{'status':'NATIVE_ACCEPTANCE_FAILED',
            'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),
            'authority':'NONE'})
        raise
    finally:
        if m.OUT.exists():
            hashes={str(p.relative_to(m.OUT)):m.sha(p.read_bytes()) for p in sorted(m.OUT.rglob('*'))
                    if p.is_file() and p.name!='SHA256SUMS.json' and '__pycache__' not in p.parts}
            m.write_json(m.OUT/'SHA256SUMS.json',hashes)
