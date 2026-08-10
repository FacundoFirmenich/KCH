+++
schema = "kch.csi-governance-node.v0.1.0"
id = "KCH-HARNESS"
kind = "HARNESS"
version = "0.1.0"
title = "KCH self-governance harness"
parent = ""
children = ["KCH-AGENTS"]
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND", "REQUEST_INSTALL"]
conflict_policy = "MOST_RESTRICTIVE_AUTHORITY_THEN_NARROWEST_VALID_SCOPE"
supersedes = []
+++

# HARNESS — Constitución operativa de KCH

## Identidad y objeto gobernante

KwanCode Harness es el sistema nodriza de integración, orquestación y gobierno multicapas/multiescala. KwanCode/CSI es su representación composicional ejecutable: los componentes, herramientas, habilidades, agentes, reglas, operadores, forks y mods se expresan como construcciones componibles sin perder procedencia, jurisdicción, memoria, estado ni techo de claims.

Este archivo gobierna al propio KCH. Ninguna proyección de host, agente, regla, rutina, recomendación o artefacto generado puede redefinir esta identidad ni ampliar la autoridad aquí declarada.

## Jerarquía vinculante

1. `HARNESS.md`: propósito, identidad, jurisdicción, invariantes, autoridad máxima y política de conflicto.
2. `AGENTS.md`: asignación y topología de agentes; admite agentes horizontales, simultáneos y subjerárquicos.
3. `RULES.md`: restricciones, rutinas y subrutinas que concretan cómo operan los agentes.

Dentro de KCH se aplica `HARNESS > AGENTS > RULES`. La especialización inferior sólo puede reducir o concretar; nunca ampliar autoridad, alterar el propósito gobernante ni borrar evidencia adversa. Las restricciones externas de sistema/plataforma y la decisión explícita vigente del usuario conservan su propia precedencia.

## Invariantes

- `capability != permission != support != authority != execution`.
- Composición no equivale a fusión: cada subsistema conserva soberanía y linaje.
- Compilación, proyección o transporte exigen verificar por separado propósito, decisión, contrato de evidencia, procedencia e integridad.
- Una recomendación no instala; un plan no ejecuta; una generación no activa; un test no demuestra utilidad humana.
- Los cambios se construyen primero en *staging*, con diff, validación, recibo y rollback posible.
- Las decisiones adversas, abstenciones y estados `NOT_ESTIMABLE` permanecen como evidencia.
- PHL real continúa fuera de alcance hasta decisión explícita posterior del usuario.

## Estado de esta fase

La autoridad máxima es preinstalación: inspeccionar, diseñar, construir en staging, validar, recomendar y solicitar una instalación. No existe autoridad para instalar globalmente, activar extensiones en hosts externos, publicar paquetes ni ejecutar mutaciones fuera del workspace.
