from __future__ import annotations
import argparse, hashlib, json, pathlib, shutil, zipfile
from typing import Any
CHUNK=8*1024*1024

def sha(path:pathlib.Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(CHUNK),b''): h.update(b)
    return h.hexdigest()

def canonical(v:Any)->bytes:
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--work',type=pathlib.Path,required=True); p.add_argument('--source',type=pathlib.Path,required=True); p.add_argument('--out',type=pathlib.Path,required=True); a=p.parse_args()
    stage=a.out/'KCH_KWANBLOCKS_HELICAL_LIFT_V0_9_EXACT_BYTE_BLIND_ELIGIBILITY_SUCCESSOR_2026-10-09'
    if stage.exists(): shutil.rmtree(stage)
    stage.mkdir(parents=True)
    # Copy only governed outputs. Never package the code-capable source pickle or quarantine bodies.
    for rel in ['acquisition/receipts','extraction','final','runtime']:
        src=a.work/rel
        if src.exists(): shutil.copytree(src,stage/rel)
    fault=a.work/'acquisition/data/gem_active_faults_harmonized.geojson'
    if fault.exists():
        (stage/'acquisition/data').mkdir(parents=True,exist_ok=True); shutil.copy2(fault,stage/'acquisition/data'/fault.name)
    shutil.copytree(a.source,stage/'operator')
    forbidden=list(stage.rglob('*.pickle'))+list(stage.rglob('*.partial'))
    if forbidden: raise SystemExit(f'forbidden source bodies in release: {forbidden}')
    files=[]
    for path in sorted(p for p in stage.rglob('*') if p.is_file()):
        files.append({'path':path.relative_to(stage).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
    manifest={'format':'KCH_HELICAL_V0_9_RELEASE_MANIFEST','files':files,'file_count':len(files),'total_bytes':sum(x['bytes'] for x in files),'source_pickle_packaged':False,'promotion':'BLOCKED','authority_ceiling':'NONE'}
    manifest['manifest_id']='h9manifest:'+hashlib.sha256(canonical(manifest)).hexdigest()
    (stage/'MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    tree_lines=[f"{x['sha256']}  {x['path']}" for x in files]+[f"{sha(stage/'MANIFEST.json')}  MANIFEST.json"]
    (stage/'SHA256SUMS.txt').write_text('\n'.join(tree_lines)+'\n')
    tree=hashlib.sha256(('\n'.join(tree_lines)+'\n').encode()).hexdigest(); (stage/'TREE_SHA256.txt').write_text(tree+'\n')
    archive=a.out/(stage.name+'.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(p for p in stage.rglob('*') if p.is_file()): z.write(path,path.relative_to(a.out).as_posix())
    (archive.with_suffix('.zip.sha256')).write_text(f"{sha(archive)}  {archive.name}\n")
    print(json.dumps({'archive':str(archive),'archive_sha256':sha(archive),'tree_sha256':tree,'manifest_id':manifest['manifest_id']},indent=2,sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
