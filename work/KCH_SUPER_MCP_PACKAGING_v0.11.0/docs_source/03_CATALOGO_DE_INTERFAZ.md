# Catálogo de interfaz MCP

## Operaciones estables de orquestación

| Herramienta | Función | Frontera crítica |
|---|---|---|
| `kch.super.status` | Estado del runtime, perfil, ledger, componentes y claims | Inspección |
| `kch.super.registry` | Registro federado canónico | No fusiona autoridad |
| `kch.super.session.open` | Abre sesión y emite capacidades ligadas al objetivo | Capacidad de un solo uso y TTL |
| `kch.super.evidence.admit` | Admite evidencia tipada | Exige SHA-256, rol, procedencia y jurisdicción |
| `kch.super.context.compile` | Evalúa un subconjunto explícito de controles | No crea autoridad |
| `kch.super.action.propose` | Registra propuesta | Propuesta no equivale a autorización |
| `kch.super.action.authorize` | Autoriza propuestas read-only completas | Mutación no disponible |
| `kch.super.action.execute` | Ejecuta ruta federada autorizada | Sólo `READ_ONLY` |
| `kch.super.precommit.verify` | Verifica objetivo, evidencia, artefacto y observador | Precommit shadow, no commit mutante |
| `kch.super.rollback` | Registra compensación inmutable | No reescribe historia ni archivos |
| `kch.super.outcome.register` | Registra resultado, incluido adverso | Conserva evidencia histórica |
| `kch.super.audit.export` | Exporta cadena append-only y hash | Auditoría local |

`kch.super.controls` es una operación de inspección y por ello no se cuenta entre las 12 anteriores.

## Nueve operaciones de inspección federada

| Herramienta | Resultado |
|---|---|
| `kch.super.controls` | Catálogo exacto R01–R28 y su techo de evidencia |
| `kch.super.registry.evidence.audit` | Recalcula hashes de las evidencias portables del registro |
| `kch.component.status` | Disponibilidad de los siete paquetes soberanos |
| `kch.phl.projection` | Proyección PHL verificada y de solo lectura |
| `kch.sco.projection` | Proyección SCO conservando soberanía contextual |
| `kch.mis.certificate.verify` | Verificación del certificado histórico MIS 0.3.1 |
| `kch.kwanprompts.probe` | Disponibilidad del paquete KwanPrompts |
| `kch.rgg.probe` | Disponibilidad del Rigor Gradient Governor |
| `kch.obl_phl.probe` | Disponibilidad del paquete OBL/PHL |

## Veintiocho herramientas de control

Cada control se publica individualmente como `kch.control.R01` … `kch.control.R28`. Devuelve un recibo firmado por contenido, pero nunca concede autoridad.

| ID | Control |
|---|---|
| R01 | Bloqueo del objetivo gobernante |
| R02 | Firewall entre proyectos |
| R03 | Compilador de autorización |
| R04 | KCH aplicado al propio agente y observador externo |
| R05 | Recibo previo de coste y alcance |
| R06 | Presupuesto de tokens y fan-out |
| R07 | Probe barato obligatorio |
| R08 | Parada por irrelevancia |
| R09 | Firewall ciencia-producto |
| R10 | Mapa directo-transferible-no aplicable |
| R11 | Auditor del significado de avance |
| R12 | Ledger de coste de oportunidad |
| R13 | Control de comunicación completa |
| R14 | Firewall de readiness comercial |
| R15 | Enlace claim-fuente-ejecución-jurisdicción |
| R16 | Registro canónico de nombre y genealogía |
| R17 | Ledger de últimas correcciones del usuario |
| R18 | Detector de contaminación entre tareas |
| R19 | Validador de handoff mínimo y suficiente |
| R20 | Limitador de proliferación documental |
| R21 | Extractor de valor de resultados adversos |
| R22 | Ledger de reparación |
| R23 | Interrupción humana prioritaria |
| R24 | Auditor de divergencia decisión-evidencia |
| R25 | Canonicalizador de roles de evidencia |
| R26 | Veto de métricas degeneradas |
| R27 | Completitud de transporte y fallos unitarios |
| R28 | Degradación de autoridad cuando se pierde evidencia |

El esquema JSON exacto de argumentos no debe copiarse manualmente desde esta tabla: el cliente lo obtiene mediante `tools/list`, y el paquete portable conserva el código fuente canónico en `bundle/src/kwancode_harness/mcp_server_base.py`.

## Roles de evidencia

`DIRECT`, `DERIVED`, `TRANSPORT`, `EXECUTION` y `OUTCOME`. Un rol incorrecto o ausente cambia el significado epistemológico del registro; un hash íntegro no corrige una clasificación causal errónea.

## Resultados de controles

- `PASS`: el contexto suministrado satisface ese control.
- `BLOCK`: el control detecta una violación explícita.
- `ABSTAIN`: faltan condiciones semánticas o el control no puede emitir un sí/no responsable.
- `UNAVAILABLE`: faltan datos, transporte o evidencia necesarios.

Ninguno de estos resultados implica por sí mismo despliegue, seguridad global, validez científica externa o permiso del usuario.

