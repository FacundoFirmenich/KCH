# KwanCode Harness (KCH) 0.11

Repositorio público canónico de trabajo y custodia de **KCH 0.11 pre-2G**.

KCH es el sistema nodriza de integración, orquestación y gobierno multicapas y multiescala del ecosistema KwanCode. KwanCode/CSI aporta el sistema composicional; KCH integra construcciones operativas preensambladas, sus contratos de autoridad, evidencia, permisos, persistencia y recuperación.

## Distribución operativa actual: AIO2

KCH All-in-One 0.11.33 / 0.11.33-aio.2 integra la proyección nativa Codex, la distribución completa para Cline/VS Code, Studio 0.3.16, Super MCP, 20 skills, lifecycle gobernado, custodia recuperable y el Contractual Rigor Fader.

La fuente reproducible vive en construct_successors/KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2/. Los binarios completos se publican como assets de release, no dentro del historial Git:

- KCH_AIO2_CODEX_COMPLETE.zip
- KCH_AIO2_CLINE_COMPLETE.zip
- KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2.zip

Estado observado: paquete PASS 1382/1382 y suite fuente Studio PASS 156/156; proyección marketplace/MIS PASS 11/11; Cline end-to-end PASS con hooks, fader, 294 herramientas MCP, reinstalación idempotente y rollback. La fuente Codex AIO2 está desplegada y su preflight real responde; la observación desde la caché recargada de la aplicación requiere reiniciar Codex.

No se incorporó ni modificó ninguna rama R34. PHL permanece autorizado, no entrenado y no ejecutado.
## Estado verificable de esta captura

La captura canónica vigente es R21. R10 permanece en el historial y en sus artefactos como evidencia precedente; no fue reescrita.

- Candidato portable integrado: `KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R21.zip`.
- SHA-256 del candidato R21: `98ba1faa4c63302f67ec386b9ecf684762e7923febc3039cd8c201a024091b54`.
- Regresión fuente final: **102/102** pruebas y Ruff PASS, sin relanzamientos y con fuente idéntica antes/después.
- Gate postinstalación fresca A2: **22/22**, estado `PASS_BOUNDED`, 294 herramientas combinadas.
- Gobernanza compilada: 23 nodos, 7 agentes y 13 reglas.
- R21 incorpora llaves constitucionales opcionales: bloqueo antes del efecto, propuesta explicada, autorización local exacta de un uso y detección de deriva acotada.
- El gate instalado verificó que `ALWAYS_THIS_SESSION` no atraviesa una llave, que una alteración no consume la autorización y que el cambio exacto sólo puede ejecutarse una vez.
- PHL continúa autorizado, no entrenado y no ejecutado.

Evidencia principal: `benchmarks/KCH_R21_LOCK_KEYS_GATE/`. Checkpoint sustantivo: `CHECKPOINT_MATERIAL_R21_LLAVES_CONSTITUCIONALES_ES.md`.

## Captura histórica R10

- Candidato portable integrado: `KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R10.zip`.
- SHA-256 del candidato R10: `90069c91fe8d57aca44b19d515fa7fad0664395c06e5ab99dfd0803ab39c67ea`.
- Regresión local exhaustiva dividida: **40/40** pruebas superadas.
- Gate postinstalación limpia: **14/14**, estado `PASS_BOUNDED`.
- Superficie estratégica observada: 31 clases, 232 métodos públicos, 205 herramientas expuestas y 27 métodos internos.
- PHL está autorizado arquitectónicamente, pero no entrenado ni validado mediante uso real del usuario.
- MIS dispone de integración portable acotada; no constituye por sí misma validación industrial ni autoridad automática.

## Límite de los claims

Esta evidencia acredita una integración local, portable y reproducible dentro de la jurisdicción ensayada. No acredita todavía robustez industrial, utilidad longitudinal, superioridad general, seguridad completa ni validación de PHL real.

Los resultados adversos y gates fallidos se conservan como evidencia histórica y no se reescriben a partir del éxito posterior.

## Navegación AIO2

- [Arquitectura funcional completa y defectos que corrige](docs/KCH_AIO2_ARQUITECTURA_FUNCIONAL_COMPLETA_ES.md)
- [Catálogo completo de las 294 herramientas observadas](docs/KCH_AIO2_CATALOGO_COMPLETO_294_HERRAMIENTAS_ES.md)
- [Metrología byte a byte y límites probatorios](docs/KCH_AIO2_METROLOGIA_BYTE_A_BYTE_ES.md)
- [Roadmap multiplataforma y SuperAgentic Assistant 3G](docs/ROADMAP_KCH_MULTIPLATAFORMA_SUPERAGENTIC_ASSISTANT_3G_Q4_2026_ES.md)
- [Programa de preparación para JOSS](docs/JOSS_READINESS_AIO2.md)
- [Evidencia pública de gates de host](benchmarks/KCH_AIO2_HOST_GATES/README.md)

## Navegación histórica

- Implementación integrada principal: `work/KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0/`
- Artefactos de salida: `outputs/`
- Prepiloto y benchmarks: `benchmarks/`
- Linajes y componentes históricos: `work/`

Esta captura excluye únicamente residuos regenerables de ejecución (`__pycache__`, bytecode, cachés de pytest y Ruff). No excluye código, documentación, evidencia, resultados adversos ni releases.
