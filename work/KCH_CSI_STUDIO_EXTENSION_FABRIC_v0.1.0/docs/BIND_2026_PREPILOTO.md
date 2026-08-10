# BIND 11th Edition 2026/2027 — encaje específico y prepiloto KCH

## Convocatoria exacta

La referencia es la **11.ª edición BIND 2026/2027**, no una descripción genérica de BIND. La inscripción está abierta del 2 de julio al 4 de septiembre de 2026. La solicitud debe completarse en inglés y una startup puede presentar hasta tres propuestas, cada una dirigida a un grupo de casos de uso distinto.

Fuentes oficiales consultadas:

- [Convocatoria y 11 bloques de 2026](https://bind.spri.eus/es/open-innovation/)
- [Formulario de la 11th Edition](https://bind.spri.eus/application/)
- [FAQ oficial de SPRI](https://www.spri.eus/es/faq/?colapse=20276&faq_page=2&tag=bind)
- [Dossier oficial de 74 páginas](https://bind.spri.eus/wp-content/uploads/2026/06/BIND-11th-Edition_Use-Case-Dossier.pdf)

La FAQ exige que la startup esté legalmente constituida y haya completado el desarrollo tecnológico, lista para entrar al mercado o ya incorporada. Las Venture Client seleccionan finalistas, negocian el alcance y firman un contrato; las empresas financian el desarrollo de los proyectos. Esto no es una subvención automática ni garantiza contrato a una candidatura.

## Encaje primario: Grupo 6

El encaje específico más directo de KCH es el **Grupo 6: digitalización de procesos internos, conocimiento y talento**.

Prioridad de casos:

1. **ID36 — Knowledge management and transfer within the organisation.** El dossier describe información dispersa, duplicados y versiones obsoletas; documentación con extensiones heterogéneas; necesidad de capturar y organizar conocimiento histórico, construir datasets de proyectos previos, clasificar, indexar y extraer conocimiento para mejorar decisiones futuras. Es una correspondencia directa con la minisuite de trabajo/aprendizaje, KwanData, KwanDocs, persistencia, grafo, archivo y skills derivadas de evidencia.
2. **ID31 — Digital management, planning and decision-support systems.** El dossier pide integración de herramientas de reporting. KCH aporta orquestación, MIS, claims y continuidad, pero todavía no prueba integración industrial con sistemas del cliente.
3. **ID33 — Increased efficiency and quality in document management.** KCH aporta custodia, hashes, normalización separada, archivo jerárquico, transformaciones y puentes a KwanDocs; falta validar rendimiento y ergonomía con documentos y usuarios reales del Venture Client.
4. **ID42 — Internal reporting and management systems.** Es plausible para trazabilidad, checkpoints, reportes y gobierno, pero el caso concreto debe definirse con la empresa y no se presume.

## Encajes secundarios

- **Grupo 5 / ID40:** compliance, riesgo y trazabilidad regulatoria. La gobernanza de permisos, alertas, autoridad, hash-chain y recuperación es relevante, pero no demuestra certificación, cumplimiento jurídico ni eficacia de ciberseguridad.
- **Grupo 10:** sólo sería defendible con un caso y datos reales de cadena de suministro, demanda o inteligencia comercial. MIS aporta una disciplina prospectiva, no un modelo de forecasting ya validado. El estado es `NOT_ESTIMABLE_CONDITIONAL`.

## Evidencia disponible

El primer par Luna con/sin KCH logró recibos exactos de tres archivos largos y búsqueda correcta de la convocatoria. Sin embargo, el brazo KCH inició un componente interno no canónico y falló su preflight. Por tanto, `KCH-PREPILOT-001` queda como evidencia adversa descriptiva y el efecto comparativo es `NOT_ESTIMABLE`.

El fallo ya produjo automáticamente un protocolo fechado y una skill `STAGED_UNEVALUATED`; eso prueba el ciclo local de aprendizaje, no que la skill mejore resultados.

## Qué falta para una candidatura defendible

1. Repetir casos con preflight canónico `PASS`, corpus congelado, réplicas y evaluador ciego.
2. Conseguir evidencia de uso real controlado sin utilizar al usuario como detector inicial de defectos básicos.
3. Definir un MVP vendible y una arquitectura de integración concreta para ID36/ID33.
4. Medir completitud, errores evitados, tiempo, coste, trazabilidad y recuperación frente a baseline.
5. Preparar en inglés formulario, vídeo, demo y propuesta de piloto con alcance, seguridad, datos, integración, hitos y criterios de aceptación.

Hasta superar esos gates, KCH tiene un encaje de problema particularmente fuerte con ID36, pero no una validación industrial ni readiness demostrada para selección.
