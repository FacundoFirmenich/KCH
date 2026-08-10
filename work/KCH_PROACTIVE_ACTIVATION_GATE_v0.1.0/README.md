# KCH Proactive Activation Gate v0.1.0

Overlay experimental y reversible sobre los bytes congelados de KCH 0.11. Añade activación proactiva consultiva a herramientas KCH de inspección *read-only*; no modifica KCH 0.11, no habilita mutaciones y no ejecuta PHL real.

## Contrato de consentimiento

Ante una regla acotada que considera indicada una herramienta, el adaptador pregunta exactamente:

- **Sí**: ejecuta sólo la propuesta pendiente actual.
- **No**: declina sólo la propuesta pendiente actual.
- **Nunca en esta sesión**: suprime futuras coincidencias de la misma regla/herramienta durante la sesión de host actual.
- **Siempre en esta sesión**: ejecuta la propuesta actual y autoejecuta futuras coincidencias de la misma regla/herramienta durante la sesión de host actual.

Nunca y Siempre no son preferencias globales ni sobreviven a `SessionEnd`. No existe `AUTO_ALL`. Una respuesta no reconocida no se interpreta como consentimiento.

## Arquitectura efectiva

1. `UserPromptSubmit` entrega el prompt al adaptador nativo de Codex.
2. Un catálogo versionado de reglas deterministas propone como máximo una herramienta *read-only* por evento.
3. Sin política de sesión, el hook bloquea el prompt y muestra las cuatro opciones.
4. La respuesta consume atómicamente la propuesta. Si autoriza, el runtime invoca directamente el handler sellado de KCH 0.11 y reinyecta tanto la petición original como el resultado observado.
5. SQLite conserva propuestas, políticas, ejecuciones y una cadena de eventos enlazada por SHA-256. El texto del prompt se borra al resolver, expirar, ignorar o cerrar la propuesta; el evento conserva sólo su hash.
6. `SessionEnd` elimina políticas y cierra propuestas pendientes sin borrar el historial de auditoría.

El catálogo inicial usa coincidencias léxicas explícitas, prioridades, exclusiones, *cooldown*, TTL y presupuesto de consultas. Esto es un detector determinista audit-able; **no demuestra comprensión semántica general ni selección óptima de herramientas**.

## Superficie MCP experimental

El launcher expone las 49 herramientas de KCH 0.11 más:

- `kch.activation.scan`
- `kch.activation.respond`
- `kch.activation.status`
- `kch.activation.session.close`

El `initialize` MCP anuncia `CONSULT_FIRST` y las cuatro respuestas. La versión informativa es `0.11.0+activation.gate.1`; no constituye una nueva macrorelease canónica.

## Despliegue Codex

El proyecto contiene:

- `.codex/config.toml`: apunta al overlay MCP.
- `.codex/hooks.json`: conecta `UserPromptSubmit` y `SessionEnd`.

Codex exige revisar y confiar en el hash exacto de hooks locales. En una nueva tarea o después de recargar el proyecto, abra `/hooks`, inspeccione ambos comandos y confíe en ellos. Hasta realizar ese paso, Codex omite los hooks aunque el MCP pueda arrancar.

Prueba manual no-PHL recomendada:

1. Escribir `Comprueba el estado del runtime KCH`.
2. Verificar que aparecen las cuatro opciones.
3. Elegir una opción.
4. Para `Siempre en esta sesión`, repetir una petición de estado y comprobar la autoejecución.
5. Cerrar la sesión y verificar que la política no se transporta a otra.

## Ejecución directa y tests

```powershell
C:\Python314\python.exe -X utf8 -u work\KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0\launcher\run_kch_activation.py
C:\Python314\python.exe -X utf8 -m unittest discover -s work\KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0\tests -v
```

## Techo de evidencia

Demostrado por gates locales: las cuatro semánticas, consumo único, políticas confinadas a sesión, limpieza al cierre, detección de manipulación del ledger, falsa autorización impedida en fallos, transporte hook bloqueo-respuesta-reinyección, 53 herramientas MCP y cero ejecución PHL en la campaña de validación.

No demostrado: fiabilidad longitudinal en uso humano, calidad de activación en lenguaje abierto, cobertura Cline/Cowork/OpenCode, beneficio causal, seguridad para autoejecución mutante, superioridad respecto de otros sistemas o PHL real. Los bytes canónicos KCH 0.11 y el estado histórico PHL permanecen fuera del overlay.
