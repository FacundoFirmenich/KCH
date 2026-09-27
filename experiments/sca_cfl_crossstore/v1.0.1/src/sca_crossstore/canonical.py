from __future__ import annotations
import hashlib,json

def canonical(x)->bytes:
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def digest(x)->str:
    return hashlib.sha256(canonical(x)).hexdigest()

def file_sha256(path)->str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()
