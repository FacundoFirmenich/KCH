+++
schema = "kch.csi-governance-node.v0.1.0"
id = "KCH-AGENTS"
kind = "AGENTS"
version = "0.1.0"
title = "KCH agent topology"
parent = "KCH-HARNESS"
children = ["AGENT-GOVERNANCE-COMPILER", "AGENT-CSI-STUDIO-ORCHESTRATOR", "AGENT-EXTENSION-CURATOR", "KCH-RULES"]
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND", "REQUEST_INSTALL"]
topology = "MIXED_HORIZONTAL_AND_SUBHIERARCHICAL"
conflict_policy = "HARNESS_FIRST_THEN_MOST_RESTRICTIVE_AGENT_INTERSECTION"
supersedes = []
+++

# AGENTS — Topología soberana y componible

Los agentes no son personajes ni copias de contexto. Son unidades operativas CSI con función, entradas, salidas, memoria, autoridad y relaciones declaradas.

## Formas admitidas

- **Horizontal**: varios agentes pares trabajan sobre categorías distintas sin subordinarse entre sí.
- **Simultánea**: agentes compatibles pueden operar concurrentemente si sus conjuntos de escritura no colisionan y existe un protocolo de reconciliación.
- **Subjerárquica**: un agente orquestador puede delegar a agentes hijos, sin transferir autoridad superior a la propia.
- **Categorial**: un agente puede ser seleccionado por tipo de artefacto, host, riesgo, jurisdicción o fase del ciclo.

## Agentes iniciales

- `AGENT-GOVERNANCE-COMPILER`: valida y compila la jerarquía HARNESS/AGENTS/RULES.
- `AGENT-CSI-STUDIO-ORCHESTRATOR`: conduce la edición guiada y supervisa constructores de artefactos.
- `AGENT-EXTENSION-CURATOR`: descubre y recomienda extensiones sin instalarlas por sí mismo.

La descripción completa vive en `agents/*.md`. El grafo CSI, no el orden textual, fija las relaciones. Todo agente debe declarar autoridad, categorías, entradas, salidas y ámbito de escritura.
