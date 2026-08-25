# Cierre sustantivo - KCH AIO1 0.11.33 / Studio 0.3.16

Fecha: 2026-08-25

## Resultado real

KCH AIO1 ya existe como paquete conjunto y recuperable para las dos primeras superficies objetivo: Codex y Cline en VS Code. Re£ne las proyecciones R21/R33, Studio, Super MCP, skills, hooks, gobierno, runtimes, custodia y rollback dentro de una £nica distribuci¢n versionada. La rama R34 qued¢ expresamente fuera de esta construcci¢n.

El ZIP final contiene 461 archivos, pas¢ verificaci¢n CRC y tiene SHA-256:

`2c2c40a231800da82b43304804bb759c41b82dff7818ab15326454904edbb34d`

La validaci¢n estructural y funcional cerr¢ 1.418/1.418 controles. Esto demuestra consistencia interna, empaquetado reproducible y contratos ejecutables; no demuestra por s¡ solo que todo host externo haya recargado la versi¢n.

## Cline / VS Code

La aceptaci¢n end-to-end de Cline es PASS. Se probaron instalaci¢n limpia, reinstalaci¢n idempotente, configuraci¢n MCP, hooks en modo real de stdin, proyecci¢n MIS, custodia, dry-run de rollback y rollback efectivo. El rollback retir¢ £nicamente los 31 blancos materiales creados por AIO1 y preserv¢ preexistencias id‚nticas.

La frontera pendiente es operacional y pertenece al usuario: instalar el ZIP final en su instancia real de VS Code/Cline. El paquete est  preparado y probado en host-mode, pero esa instalaci¢n personal todav¡a no fue observada.

## Codex

El despliegue material est  presente en la fuente de plugin y en `D:\CodexRuntimes\kch-aio1`. El preflight corregido ejecutado exclusivamente con Luna y razonamiento xhigh termin¢ PASS con una £nica llamada y salida terminal limpia.

La activaci¢n nativa del host Codex abierto todav¡a no puede promoverse a PASS. Los procesos persistentes observados segu¡an usando el runtime anterior de AppData, la cach‚ era anterior a la correcci¢n MIS y no apareci¢ un recibo literal de `SessionStart` o `UserPromptSubmit`. El veredicto correcto es:

`PASS corrected preflight / FAIL current host onboarding`

La acci¢n cr¡tica es reiniciar o recargar Codex y abrir una tarea fresca. Esa tarea debe observar el hook literal y ejecutar el preflight sin inyecci¢n manual de variables.

## MIS y custodia

El transporte m¡nimo de MIS conserva 16 archivos y 1.931.633 bytes de evidencia/resultados necesarios, sin duplicar el  rbol fuente completo. El runtime de estado MIS queda confinado bajo el runtime AIO1 para impedir derrames en workspaces arbitrarios.

Los fallos previos se conservaron: el FAIL inicial de Cline, el fallo de ruta de validaci¢n y la primera aceptaci¢n Luna. No fueron reescritos ni maquillados.

## Drive y almacenamiento

El ZIP final y los recibos de validaci¢n, Cline, instalaci¢n Codex y Luna xhigh fueron subidos a la carpeta Drive AIO1. El conector confirm¢ aceptaci¢n y coincidencia exacta de tama¤os; no expuso un hash remoto, por lo que el SHA-256 registrado sigue siendo el calculado localmente antes de borrar el ZIP local.

La limpieza cloud-first retir¢ 636.435.505 bytes y 14.040 archivos regenerables: laboratorios temporales Luna/pytest, build, ZIP local ya respaldado, runtimes de validaci¢n, junctions y logs vac¡os. La fuente y evidencia local del sucesor quedaron reducidas a 9.912.605 bytes, adem s del runtime vivo. Se conservaron los recibos, `test_work` y las dos fuentes posibles del plugin porque una ruta relativa aparece en el marketplace.

## L¡mites constitucionales

- R21 y R33 fueron preservados.
- R34 no fue accedida ni modificada.
- PHL no fue entrenado ni ejecutado.
- No se activ¢ micr¢fono.
- Ninguna instalaci¢n fue presentada como autoridad o entrenamiento.
- Ning£n FAIL fue convertido en PASS por interpretaci¢n.

## Pr¢xima acci¢n decisiva

1. Recargar o reiniciar Codex.
2. Abrir una tarea fresca.
3. Verificar recibo literal de hook y preflight AIO1 sin env manual.
4. Si pasa, promover la activaci¢n Codex a PASS nativo.
5. Instalar el ZIP de Drive en VS Code/Cline y obtener el primer recibo del host personal.
