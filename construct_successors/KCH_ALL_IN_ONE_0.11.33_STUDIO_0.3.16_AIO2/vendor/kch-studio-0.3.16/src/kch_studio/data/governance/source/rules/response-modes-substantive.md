+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-RESPONSE-MODES-SUBSTANTIVE"
kind = "RULE"
version = "0.1.0"
title = "Substantive authored-chat response modes"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "DESIGN", "RECOMMEND"]
routines = ["resolve_response_profile", "compose_substantive_answer", "separate_outputs", "persist_execution_register", "emit_register_path_line"]
subroutines = ["apply_scope_precedence", "measure_host_viewport", "compress_repetition_not_substance", "preserve_claim_boundaries", "write_markdown_register"]
native_exec_rules = []
supersedes = []
+++

# Modos sustantivos de contestación

KCH ofrece tres perfiles canónicos para la contestación redactada del chat: **Conciso**, **Explicativo** y **Extenso**. El usuario puede crear perfiles custom y vincularlos por mensaje, sesión, tarea, SCO, workspace o globalmente.

El perfil Conciso apunta a una pantalla y no debe exceder dos pantallas o un scroll. El perfil Explicativo ocupa aproximadamente entre dos y cinco scrolls. El perfil Extenso utiliza todo el espacio necesario. La métrica es el viewport renderizado del usuario: los outputs, el código, los archivos, los resultados y demás artefactos quedan fuera del cómputo y nunca se recortan por este mecanismo.

Todo perfil conserva una respuesta informativa, explicativa y de conjunto. La síntesis debe explicar qué cambió, qué significa, qué posición real tiene el proyecto, qué no está demostrado y qué decisión sigue; no puede sustituirse por un inventario de acciones, estados, hashes o rutas.

La cronología técnica de ejecución se persiste automáticamente como ficha Markdown separada. No se ofrece al usuario ni se pregunta si la desea. La contestación termina únicamente con una línea que informa la ruta de la ficha guardada.
