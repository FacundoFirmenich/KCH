# Validación sustantiva — KCH AIO1

## Veredicto

`KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO1` queda en estado `CONSTRUCT_VALIDATED_NOT_PROMOTED`. Es un paquete portable, offline, transaccional y recuperable para Codex y Cline/VS Code; no es una instalación viva ni una promoción sobre R21/R33.

## Qué quedó demostrado

- Integridad exacta del payload, manifiesto y ZIP: PASS.
- Proyección Codex válida con un único ciclo R33 de seis eventos, 19 skills y cinco runtimes.
- Runtime aislado desde wheelhouse: diez módulos reales importados y tres comandos MCP ejecutables.
- Gate propio Studio/Super-MCP: `PASS_BOUNDED` 31/31, 294 herramientas combinadas, seis de bootstrap Codex y tres recursos MCP.
- Gobierno compilado: 23 nodos, siete agentes, 13 reglas y ocho artefactos verificados.
- Superficie estratégica: 41 clases, 285 métodos públicos, 238 expuestos como herramientas y 47 internos de composición; sin clasificaciones ni bindings faltantes en esa jurisdicción.
- MIS histórico: 480 registros y 60 ledgers, sin autoridad ejecutiva.
- Idempotencia: segunda instalación byte a byte idéntica, sin duplicar ni borrar `existing-plugin` o `ibp-priors`.
- Custodia: cuatro backups originales preservados; rollback de cuatro acciones validado en modo seco. El runtime nunca se borra automáticamente.
- PHL permanece autorizado pero sin entrenamiento, feedback real ni ejecución.

## Límites y evidencia adversa preservada

- No hubo activación en Codex ni Cline reales, promoción automática, micrófono, entrenamiento PHL ni efectos externos.
- El claim ceiling es `LOCAL_PORTABLE_INSTALLATION_STDIO_COMPOSITION_BOUNDED_MIS_REPLAY_AND_NATIVE_REFERENCE_DISCOVERY_WITHOUT_HOST_ACTIVATION`.
- La suite fuente de Studio tuvo intentos no terminales afectados por cwd, basetemp, dependencias ausentes y rutas Windows largas. No se reinterpretan como PASS; el gate de wheelhouse aislado es la evidencia final aplicable al paquete.
- Una creación de venv a más de 200 caracteres falló en `ensurepip`. Se añadió un preflight que rechaza rutas expandidas mayores de 180 caracteres antes de crear un runtime parcial.
- Cline sobre Windows recibe rules + Super-MCP. Sus hooks no se activan porque el host oficial aún no ofrece esa paridad; no se simula soporte inexistente.
- El validador oficial de plugins Codex exige ruta extendida en este árbol largo; la proyección pasó al usar `\\?\`.
- No se inspeccionó, importó ni modificó ninguna rama R34.

## Consecuencia

AIO1 ya puede pasar a una autorización separada de instalación onboarding en hosts frescos. Esa fase deberá observar activación nativa real, receipts de hooks, disponibilidad callable y convivencia con los plugins R21/R33; un PASS portable no equivale a esa activación.