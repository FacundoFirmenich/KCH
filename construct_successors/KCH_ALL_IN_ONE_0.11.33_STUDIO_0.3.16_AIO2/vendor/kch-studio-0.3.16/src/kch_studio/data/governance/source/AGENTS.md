+++
schema = "kch.csi-governance-node.v0.1.0"
id = "KCH-AGENTS"
kind = "AGENTS"
version = "0.3.0"
title = "KCH sovereign and coral agent topology"
parent = "KCH-HARNESS"
children = ["AGENT-CORAL-INTEGRATION-AUDITOR", "AGENT-CONSTITUTIONAL-LOCK-GOVERNOR", "AGENT-EVIDENCE-SKILL-CONTINUITY", "AGENT-GOVERNANCE-COMPILER", "AGENT-CSI-STUDIO-ORCHESTRATOR", "AGENT-EXTENSION-CURATOR", "KCH-RULES"]
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND", "REQUEST_INSTALL"]
topology = "MIXED_HORIZONTAL_SIMULTANEOUS_CATEGORIAL_AND_SUBHIERARCHICAL"
conflict_policy = "HARNESS_FIRST_THEN_EXPLICIT_WRITESET_AND_MOST_RESTRICTIVE_AUTHORITY_INTERSECTION"
supersedes = ["KCH-AGENTS@0.2.0"]
+++

# AGENTS — topología soberana, componible y coral

Los agentes son unidades operativas CSI con función, entradas, salidas, memoria, autoridad, estado, ámbito de escritura y relaciones declaradas. No son personajes ni copias reducidas de contexto.

## Formas admitidas

- **Horizontal:** agentes pares cubren categorías distintas sin subordinarse entre sí.
- **Simultánea:** agentes compatibles operan concurrentemente cuando sus conjuntos de escritura no colisionan y existe reconciliación explícita.
- **Subjerárquica:** un orquestador delega a agentes hijos sin transferir autoridad superior a la propia.
- **Categorial:** la selección responde al tipo de artefacto, host, riesgo, jurisdicción, evidencia o fase.
- **SCO soberana:** tareas de Codex, Cline, Cowork, OpenCode u otros hosts cooperan sin fusionar contexto, memoria ni identidad.

## Agentes gobernantes

- `AGENT-CORAL-INTEGRATION-AUDITOR`: comprueba que ninguna capacidad estratégica quede huérfana y aplica los gates local y sistémico.
- `AGENT-EVIDENCE-SKILL-CONTINUITY`: detecta aprendizajes históricos, prepara protocolos y skills trazables, organiza el archivo y gobierna la continuidad según evidencia presupuestaria.
- `AGENT-GOVERNANCE-COMPILER`: valida y compila HARNESS/AGENTS/RULES, grafo, hashes y proyecciones.
- `AGENT-CSI-STUDIO-ORCHESTRATOR`: conduce la construcción guiada CSI y supervisa constructores de artefactos.
- `AGENT-EXTENSION-CURATOR`: descubre, resuelve y recomienda extensiones sin instalarlas por sí mismo.

El grafo CSI, no el orden textual, fija las relaciones. Cada agente conserva su jurisdicción, pero debe declarar puentes verificables con los demás subsistemas implicados.
