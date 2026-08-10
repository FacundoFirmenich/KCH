# KwanCode Harness (KCH) 0.11

Repositorio privado canónico de trabajo y custodia de **KCH 0.11 pre-2G**.

KCH es el sistema nodriza de integración, orquestación y gobierno multicapas y multiescala del ecosistema KwanCode. KwanCode/CSI aporta el sistema composicional; KCH integra construcciones operativas preensambladas, sus contratos de autoridad, evidencia, permisos, persistencia y recuperación.

## Estado verificable de esta captura

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

## Navegación

- Implementación integrada principal: `work/KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0/`
- Artefactos de salida: `outputs/`
- Prepiloto y benchmarks: `benchmarks/`
- Linajes y componentes históricos: `work/`

Esta captura excluye únicamente residuos regenerables de ejecución (`__pycache__`, bytecode, cachés de pytest y Ruff). No excluye código, documentación, evidencia, resultados adversos ni releases.
