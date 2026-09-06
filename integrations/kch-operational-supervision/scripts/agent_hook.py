"""Event-driven native Codex observer. Never starts a model or polls the host."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from kch_ops.agents import AgentObservatory, ALLOWED_MODELS


def handle(payload):
    event=payload.get('hook_event_name')
    name=str(payload.get('tool_name',''))
    tool_input=payload.get('tool_input',{})
    if event=='PreToolUse' and name.endswith('spawn_agent'):
        error=None
        if not isinstance(tool_input,dict) or tool_input.get('model') not in ALLOWED_MODELS:
            error='KCH: agentes auxiliares requieren modelo explícito gpt-5.6-luna o gpt-5.6-terra.'
        elif tool_input.get('fork_turns','all')=='all':
            error='KCH: usá fork_turns none o un número; all hereda el modelo y no admite este override.'
        if error:
            return {'hookSpecificOutput':{'hookEventName':event,'permissionDecision':'deny','permissionDecisionReason':error}}
    if event=='PostToolUse' and name.endswith('list_agents'):
        response=payload.get('tool_response')
        if isinstance(response,str):
            try: response=json.loads(response)
            except ValueError: response=None
        if not isinstance(response,dict) or not isinstance(response.get('agents'),list):
            return {'hookSpecificOutput':{'hookEventName':event,'additionalContext':'KCH observatorio: formato nativo no admitido; no se inventa un censo de agentes.'}}
        normalized=[]
        for agent in response['agents']:
            identity=agent.get('agent_name') or agent.get('agent_id')
            status=agent.get('agent_status') or agent.get('status')
            if not identity or not status:
                raise ValueError('NATIVE_AGENT_ID_OR_STATUS_MISSING')
            normalized.append({'agent_id':identity,'status':status,'is_governor':identity=='/root',
                               **({'model':agent['model']} if agent.get('model') else {})})
        session=payload.get('session_id')
        cwd=payload.get('cwd')
        call_id=payload.get('tool_use_id') or payload.get('tool_call_id')
        if not session or not cwd or not call_id:
            return {'hookSpecificOutput':{'hookEventName':event,'additionalContext':'KCH observatorio: falta vinculación nativa sesión/directorio/call-id; captura pendiente.'}}
        db=Path(cwd)/'.kch/operational-supervision/agents.sqlite3'
        observer=AgentObservatory(db)
        event_id=f'{session}:{call_id}'
        prior=next((e for e in observer.events() if e['event_id']==event_id),None)
        receipt={'event_id':event_id,'source_ref':f'codex://threads/{session}#tool={call_id}',
                 'host':'CODEX','scope':session,'observed_at':prior['payload']['observed_at'] if prior else datetime.now(timezone.utc).isoformat(),
                 'agents':normalized,'native_response_sha256':hashlib.sha256(json.dumps(response,sort_keys=True).encode()).hexdigest()}
        observer.observe(receipt)
        alerts=[alert for row in observer.status()['agents'] for alert in row['alerts']]
        if alerts:
            return {'hookSpecificOutput':{'hookEventName':event,'additionalContext':'KCH observatorio: '+', '.join(sorted(set(alerts)))}}
    if event=='UserPromptSubmit' and any(word in str(payload.get('prompt','')).lower() for word in ('vps','agentes','subagente','prerregistr')):
        return {'hookSpecificOutput':{'hookEventName':event,'additionalContext':
            'KCH supervisión: herramientas locales en '+str(ROOT/'scripts/kch_ops.py')+
            '; VPS requiere perfil SSH exacto; agentes usa recibos nativos y prerregistro Construct dual. Sin llamadas a modelos propias.'}}
    return {}


if __name__=='__main__':
    try:
        print(json.dumps(handle(json.load(sys.stdin)),ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'systemMessage':'KCH observatorio: captura fallida, '+type(error).__name__+'; no se declara cobertura completa.'}))
        raise SystemExit(1)
