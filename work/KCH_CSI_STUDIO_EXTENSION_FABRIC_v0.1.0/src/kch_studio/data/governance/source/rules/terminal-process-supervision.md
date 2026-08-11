+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-TERMINAL-PROCESS-SUPERVISION"
kind = "RULE"
version = "0.2.0"
title = "Durable supervision to exact terminal evidence"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "BUILD_STAGED", "VALIDATE"]
routines = ["register_before_promising", "launch_shell_free_when_owned", "preserve_process_identity", "wait_without_relaunch", "adjudicate_terminal_receipt"]
subroutines = ["seal_request", "bind_signed_effective_worker_pid", "hash_stdout_stderr", "record_exit_code", "distinguish_wait_timeout", "reject_artifact_only_success", "emit_terminal_alert_once", "isolate_reconciliation_errors", "recover_after_restart"]
native_exec_rules = []
supersedes = []
+++

# Supervisión durable hasta evidencia terminal exacta

Cuando una respuesta promete seguir una ejecución, el compromiso de monitoreo debe quedar registrado antes de liberar esa promesa. La existencia de la herramienta no concede permiso para ejecutar: la misión, la matriz de permisos y la autoridad del usuario siguen siendo requisitos independientes.

Cuando KCH sea quien lance una ejecución autorizada, utilizará argumentos estructurados sin `shell`, un directorio de trabajo explícito y un supervisor que persista fuera del ciclo conversacional inmediato. El supervisor debe conservar identidad de proceso, solicitud autosellada, `stdout`, `stderr`, artefactos esperados y recibo terminal autosellado. Variables de entorno con apariencia de secreto no se transportan por esta vía: corresponden al broker de cuentas y permisos finitos.

Un `PID` que desaparece, un artefacto presente, una línea de log o un timeout del envoltorio no equivalen a éxito. El estado terminal fuerte exige un recibo canónico válido y el código de salida del proceso objetivo. La presencia de artefactos sin código de salida queda como evidencia terminal incompleta; una salida no cero se conserva como resultado adverso, nunca se reetiqueta como éxito.

Un timeout de espera sólo termina esa espera: mantiene activo el mismo compromiso y no autoriza matar, relanzar, duplicar ni sustituir la ejecución. Todo retry necesita adjudicación explícita y debe preservar la cronología del primer intento. La reutilización de PID debe detectarse mediante identidad de creación del proceso cuando el sistema operativo la exponga.

El bucle en segundo plano aislará los fallos de reconciliación por compromiso, los registrará y continuará vigilando los demás. Las alertas terminales son exactamente una vez por compromiso, mientras la evidencia puede volver a verificarse tras reiniciar KCH. Ningún resultado local de este monitor demuestra eficacia general, producción ni validación industrial.
