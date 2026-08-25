+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-CONSTITUTIONAL-LOCK-KEYS"
kind = "RULE"
version = "0.1.0"
title = "Exact constitutional lock keys"
parent = "KCH-RULES"
children = []
routines = ["MATCH_LOCK", "BLOCK_BEFORE_EFFECT", "EXPLAIN_CHANGE", "AUTHORIZE_ONCE", "VERIFY_DRIFT"]
subroutines = ["BIND_RESOURCE", "BIND_OPERATION", "BIND_PREIMAGE", "BIND_RESULT", "BIND_FULL_ARGUMENTS", "REJECT_MODEL_AUTHORITY", "REJECT_SESSION_WIDE_UNLOCK", "CONSUME_BEFORE_ATTEMPT", "PRESERVE_HASH_CHAIN"]
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND"]
native_exec_rules = []
supersedes = []
+++

# Llaves constitucionales exactas

1. El modo es opcional y viene apagado. Solo el usuario puede activarlo, crear llaves o desactivarlas.
2. Una coincidencia activa bloquea la mutacion antes de cualquier efecto, incluso si existe permiso, consentimiento general, automatizacion, RUN o CONSTRUCT.
3. La propuesta debe explicar razon, impacto, dependencias y recuperacion, y vincular de forma exacta recurso, operacion, preimagen, argumentos completos y resultado pretendido.
4. El modelo y los canales no confiables no pueden autorizar. La autorizacion requiere un gesto local confiable del usuario.
5. La autorizacion es de un unico uso. Se consume antes del intento para impedir carreras y reejecuciones. No existen desbloqueos implicitos, generales ni por toda la sesion.
6. Cambiar un byte, argumento, recurso, operacion, linea base o llave invalida la autorizacion. Un intento alterado no consume una autorizacion exacta aun valida.
7. Todo bloqueo, propuesta, autorizacion, consumo, rechazo y deriva se conserva en un registro encadenado verificable.
8. La prevencion solo se afirma para superficies mediadas por KCH. La mutacion externa no mediada se detecta como deriva cuando exista una linea base verificable.
