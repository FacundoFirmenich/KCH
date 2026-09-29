#!/usr/bin/env python3
"""Reviewed wrapper-source reconciliation after remote attempt 36581643705.
The five exercised functions/classes have identical ASTs in the delivered and
GitHub notebook versions. Only the unexecuted campaign CLI/reserve handling
changed. Neither operator, prompt, projection nor generation function changes.
"""
import ast
import json
from pathlib import Path
import traceback
import native_acceptance as m

REVIEWED = '66b4c1f717ee2e2759baa05c06a50b1ecb95e098d67351d0acb394962fe4f67b'
AST_HASHES = {
 'raw_state_features':'f8f30a02c187f42dc9ddf86ef16793c7c50413796c8feaffadded03c9996f8b5',
 'TMRCommonStateShadowProcessor':'f365ca3cefe9d3dbfc58ef1e1e94f6921e0b3f80f7fef67939a1182452fda295',
 'generation_kwargs':'dc1d3ea451c712291cad4142a624b4a3bfc99386a53ef0bf3e2bc366a04db319',
 'generate_shadow_one':'0138fb03a7fb6e47bbbe7c27b51e0aac9b0497368102f69af387e7da3f65e287',
 'generate_fixed_one':'1f8571c0db4d006d87618f1a97bdc2d33bc52ca9bbcafdcbb76ec0415fd8edab',
}
m.UPSTREAM_HASHES['src/shadow_campaign.py'] = REVIEWED
original_materialize = m.materialize_upstream

def checked_materialize():
    target, digest = original_materialize()
    tree = ast.parse((target/'src/shadow_campaign.py').read_text())
    observed = {n.name:m.sha(ast.dump(n,include_attributes=False).encode()) for n in tree.body
                if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in AST_HASHES}
    if observed != AST_HASHES:
        raise ValueError('Previously reviewed executable functions changed')
    m.write_json(m.OUT/'source_reconciliation.json',{
        'prior_delivery_sha256':'711d509a1926fecb98a24bfdae97d1f4efbb3461188abf64647ebc79f8008c8e',
        'reviewed_notebook_wrapper_sha256':REVIEWED,'executed_ast_identical':True,
        'executed_ast_sha256':AST_HASHES,'prior_failed_run':36581643705,
        'reviewed_runner_sha256':m.sha(Path(__file__).read_bytes()),
        'protected_reserve_touched':False,'authority':'NONE'})
    return target,digest

m.materialize_upstream = checked_materialize
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
