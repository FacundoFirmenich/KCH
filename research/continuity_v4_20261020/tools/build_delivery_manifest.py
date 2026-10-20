#!/usr/bin/env python3
"""Inventory delivered bytes after editing; never rewrites historical evidence."""
import argparse, hashlib, json
from pathlib import Path

ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);a=ap.parse_args()
repo=a.repo.resolve();root=repo/'research/continuity_v4_20261020'
excluded={root/'DELIVERY_MANIFEST.json',root/'CORPUS_VERIFICATION.json'}
files=sorted(p for p in root.rglob('*') if p.is_file() and p not in excluded and '__pycache__' not in p.parts)
files.append(repo/'.github/workflows/research-review-implementation.yml')
manifest=dict(schema='KCH_V4_DELIVERY_MANIFEST',date='2026-10-20',parent_commit='3d50f0ae68affbc747d73eb855863ead02d02782',
  branch='continuity/review-implementation-20261020',draft_pr='https://github.com/FacundoFirmenich/KCH/pull/37',
  exclusions=['Self digest is external in the Git tree.','CORPUS_VERIFICATION.json is a generated receipt; CI generates a fresh copy outside corpus.','Python bytecode caches are not delivered.'],
  files=[dict(path=str(p.relative_to(repo)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in files])
(root/'DELIVERY_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(files=len(files),bytes=sum(f['bytes']for f in manifest['files']))))
