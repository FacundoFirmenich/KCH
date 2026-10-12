from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--protocol',required=True,type=Path); p.add_argument('--delivery-manifest',required=True,type=Path); p.add_argument('--output',required=True,type=Path); a=p.parse_args()
    raw=a.protocol.read_bytes(); obj=json.loads(raw)
    stripped=dict(obj); pid=stripped.pop('protocol_id'); declared=stripped.pop('protocol_sha256'); calculated=hashlib.sha256(canonical(stripped)).hexdigest()
    manifest=json.loads(a.delivery_manifest.read_text())
    checks={
      'protocol_id_content_address': pid == 'h8p:'+calculated,
      'declared_protocol_hash': declared == calculated,
      'locked_before_angle_access': obj.get('status') == 'LOCKED_BEFORE_REAL_MECHANISM_ANGLE_ACCESS',
      'angle_firewall': obj.get('blind_eligibility',{}).get('angle_fields_sealed_until_selection_receipt') is True,
      'authority_none': obj.get('authority_ceiling') == 'NONE',
      'promotion_blocked': obj.get('promotion') == 'BLOCKED',
      'scientific_execution_not_performed': obj.get('scientific_execution_performed') is False,
      'delivery_protocol_match': manifest.get('protocol_id') == pid,
      'delivery_outcome_preacquisition': manifest.get('outcome') == 'LOCKED_AWAITING_BLIND_ELIGIBILITY_AND_EXACT_BYTE_ACQUISITION',
    }
    body={'format':'KCH_HELICAL_V0_8_PROTOCOL_LOCK_AUDIT','checks':checks,'status':'PASS' if all(checks.values()) else 'FAIL','protocol_id':pid,'protocol_content_sha256':calculated,'protocol_file_sha256':hashlib.sha256(raw).hexdigest(),'delivery_manifest_sha256':hashlib.sha256(a.delivery_manifest.read_bytes()).hexdigest(),'authority_ceiling':'NONE'}
    body['receipt_id']='h8lockaudit:'+hashlib.sha256(canonical(body)).hexdigest(); a.output.write_text(json.dumps(body,indent=2,sort_keys=True)+'\n'); print(json.dumps(body,indent=2,sort_keys=True)); return 0 if body['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
