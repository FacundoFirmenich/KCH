"""DT14: source-, scope- and time-bound admission of model advice.

This checker verifies structure/provenance constraints, not semantic truth.
Free commentary is never rendered as an instrument-verified fact. No host action.
The module is standard-library only and is shared byte-for-byte with the remote
experiment, rather than emulating a model or supplying a canned model answer.
"""
from __future__ import annotations
import copy
import hashlib
import json
from typing import Any

KINDS = frozenset({'OBSERVED_ARTIFACT', 'DOCUMENT_REPORT', 'MODEL_TEXT', 'NOT_VERIFIED'})
FIELDS = {'observed_ids': 'OBSERVED_ARTIFACT', 'document_ids': 'DOCUMENT_REPORT',
          'model_text_ids': 'MODEL_TEXT', 'boundary_ids': 'NOT_VERIFIED'}
VERDICTS = frozenset({'WITHHOLD_WHOLE_ASSESSMENT', 'LOCAL_COMMENT_ONLY', 'ASSESS_COMPLETE_TEXT'})

class EvidenceError(ValueError):
    pass

def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def _text(x: Any, name: str, maximum: int = 20000) -> str:
    if not isinstance(x, str) or not x.strip() or len(x) > maximum:
        raise EvidenceError('INVALID_' + name)
    return x

def _sha(x: Any) -> str:
    if not isinstance(x, str) or len(x) != 64 or any(c not in '0123456789abcdef' for c in x):
        raise EvidenceError('INVALID_SHA256')
    return x

def prepare(*, session: str, turn: str, goal_version: int, work_text: str,
            work_complete: bool, catalog: dict, question: str) -> dict:
    """Freeze the instrument-supplied catalog and explicit source cut.

    Catalog kind assignments are supplied by the operator/instrument. The
    checker never infers their correctness merely from a matching digest.
    """
    _text(session, 'SESSION', 200); _text(turn, 'TURN', 200); _text(question, 'QUESTION')
    if type(goal_version) is not int or goal_version < 1 or type(work_complete) is not bool:
        raise EvidenceError('INVALID_TARGET')
    if not isinstance(work_text, str) or len(work_text.encode()) > 250000:
        raise EvidenceError('INVALID_WORK_TEXT')
    if not isinstance(catalog, dict) or not 1 <= len(catalog) <= 128:
        raise EvidenceError('INVALID_CATALOG')
    for key, item in catalog.items():
        _text(key, 'EVIDENCE_ID', 80)
        if not isinstance(item, dict) or set(item) != {'kind', 'statement', 'source_sha256', 'scope'}:
            raise EvidenceError('INVALID_CATALOG_FIELDS')
        if item['kind'] not in KINDS: raise EvidenceError('UNKNOWN_EVIDENCE_KIND')
        _text(item['statement'], 'STATEMENT'); _sha(item['source_sha256']); _text(item['scope'], 'SCOPE', 500)
    if not any(x['kind'] == 'NOT_VERIFIED' for x in catalog.values()):
        raise EvidenceError('EXPLICIT_BOUNDARY_REQUIRED')
    payload = {'schema':'kch.dt14.evidence-packet/1', 'session':session, 'turn':turn,
               'goal_version':goal_version, 'work_text':work_text,
               'work_text_sha256':text_hash(work_text), 'work_complete':work_complete,
               'catalog':copy.deepcopy(catalog), 'question':question,
               'authority':'NONE', 'catalog_truth_independently_verified':False}
    return {'payload':payload, 'sha256':digest(payload)}

def verify_packet(packet: dict) -> dict:
    if not isinstance(packet, dict) or set(packet) != {'payload', 'sha256'}:
        raise EvidenceError('INVALID_PACKET')
    p = packet['payload']
    if not isinstance(p, dict) or digest(p) != packet['sha256']:
        raise EvidenceError('PACKET_HASH_MISMATCH')
    keys = {'schema','session','turn','goal_version','work_text','work_text_sha256',
            'work_complete','catalog','question','authority','catalog_truth_independently_verified'}
    if set(p) != keys or p['schema'] != 'kch.dt14.evidence-packet/1':
        raise EvidenceError('PACKET_SCHEMA_MISMATCH')
    rebuilt = prepare(session=p['session'], turn=p['turn'], goal_version=p['goal_version'],
                      work_text=p['work_text'], work_complete=p['work_complete'],
                      catalog=p['catalog'], question=p['question'])
    if rebuilt != packet: raise EvidenceError('PACKET_NOT_CANONICAL')
    return p

def parse_advice(text: str) -> dict:
    """Accept one JSON object or one complete JSON fence; never salvage substrings."""
    _text(text, 'ADVICE', 100000)
    stripped = text.strip()
    if stripped.startswith('```json\n') and stripped.endswith('\n```'):
        stripped = stripped[8:-4]
    elif stripped.startswith('```\n') and stripped.endswith('\n```'):
        stripped = stripped[4:-4]
    def pairs(entries):
        obj = {}
        for key, value in entries:
            if key in obj: raise EvidenceError('DUPLICATE_JSON_KEY')
            obj[key] = value
        return obj
    try: obj = json.loads(stripped, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(EvidenceError('NONFINITE_JSON')))
    except json.JSONDecodeError as exc: raise EvidenceError('INVALID_ADVICE_JSON') from exc
    if not isinstance(obj, dict): raise EvidenceError('ADVICE_NOT_OBJECT')
    return obj

def admit(packet: dict, advice: dict, *, current_session: str, current_turn: str,
          current_goal_version: int) -> dict:
    """Admit canonical facts and quarantine free text. This never dispatches WORK.

    Later WORK deltas do not invalidate a statement about a known prefix; the
    receipt remains about that frozen prefix. Turn and goal changes do invalidate
    its use as a current intervention and require a new packet.
    """
    p = verify_packet(packet)
    if (p['session'], p['turn'], p['goal_version']) != (current_session, current_turn, current_goal_version):
        raise EvidenceError('STALE_OR_WRONG_TARGET')
    required = set(FIELDS) | {'work_assessment', 'current_deployment_verified', 'commentary', 'proposed_next_step'}
    if not isinstance(advice, dict) or set(advice) != required:
        raise EvidenceError('ADVICE_SCHEMA_MISMATCH')
    if advice['work_assessment'] not in VERDICTS:
        raise EvidenceError('INVALID_WORK_ASSESSMENT')
    if advice['work_assessment'] == 'ASSESS_COMPLETE_TEXT' and not p['work_complete']:
        raise EvidenceError('PARTIAL_IS_NOT_WHOLE')
    if advice['current_deployment_verified'] is not False:
        raise EvidenceError('NO_CURRENT_DEPLOYMENT_WITNESS')
    for field in ('commentary', 'proposed_next_step'):
        _text(advice[field], field.upper(), 10000)
    expanded = {}
    used = set()
    for field, kind in FIELDS.items():
        ids = advice[field]
        if not isinstance(ids, list) or len(ids) > len(p['catalog']):
            raise EvidenceError('INVALID_ID_LIST')
        expanded[field] = []
        for key in ids:
            if not isinstance(key, str) or key not in p['catalog']:
                raise EvidenceError('UNKNOWN_EVIDENCE_ID')
            if key in used: raise EvidenceError('DUPLICATE_EVIDENCE_ID')
            used.add(key)
            if p['catalog'][key]['kind'] != kind:
                raise EvidenceError('EVIDENCE_TYPE_PROMOTION')
            expanded[field].append({'id':key, **p['catalog'][key]})
    if not advice['boundary_ids']:
        raise EvidenceError('BOUNDARY_OMITTED')
    return {'schema':'kch.dt14.admission/1', 'packet_sha256':packet['sha256'],
            'advice_sha256':digest(advice), 'target':{'session':p['session'],'turn':p['turn'],'goal_version':p['goal_version']},
            'status':'SCOPED_FACTS_ADMITTED_NOT_SEMANTICALLY_CERTIFIED',
            'facts':expanded, 'work_assessment':advice['work_assessment'],
            'work_cut':{'text_sha256':p['work_text_sha256'],'complete':p['work_complete']},
            'unverified_model_commentary':advice['commentary'],
            'unapproved_proposed_next_step':advice['proposed_next_step'],
            'requires_explicit_relay':True, 'automatic_dispatch':False,
            'current_deployment_verified':False, 'authority':'NONE'}

def render(receipt: dict, *, include_unverified: bool = False) -> str:
    """Facts are expanded from catalog entries. Unverified text is opt-in labelled."""
    if receipt.get('schema') != 'kch.dt14.admission/1': raise EvidenceError('INVALID_RECEIPT')
    headings = {'observed_ids':'Observaciones de artefactos en su ámbito',
                'document_ids':'Afirmaciones documentales, no reejecuciones',
                'model_text_ids':'Texto emitido por modelos, no evidencia independiente',
                'boundary_ids':'Límites de verificación'}
    lines = []
    for field, heading in headings.items():
        lines.append(heading + ':')
        for item in receipt['facts'][field]:
            lines.append(f"[{item['id']}] {item['statement']} (ámbito: {item['scope']})")
    lines.append('Autoridad: NONE. Ningún comando ha sido ejecutado por esta admisión.')
    if include_unverified:
        lines += ['INTERPRETACIÓN NO ADJUDICADA DEL MODELO:',receipt['unverified_model_commentary'],
                  'PROPUESTA NO AUTORIZADA:',receipt['unapproved_proposed_next_step']]
    return '\n'.join(lines)
