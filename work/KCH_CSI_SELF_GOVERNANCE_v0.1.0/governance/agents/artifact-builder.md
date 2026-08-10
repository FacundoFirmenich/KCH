+++
schema = "kch.csi-governance-node.v0.1.0"
id = "AGENT-ARTIFACT-BUILDER"
kind = "AGENT"
version = "0.1.0"
title = "CSI artifact builder"
parent = "AGENT-CSI-STUDIO-ORCHESTRATOR"
children = []
authority_ceiling = ["DESIGN", "BUILD_STAGED", "VALIDATE"]
categories = ["SKILL", "TOOL", "OPERATOR", "FORK", "MOD", "PLUGIN", "MCP", "RULE", "AGENT"]
reads = ["staging/specifications/**", "governance/**"]
writes = ["staging/artifacts/**", "receipts/validation/**"]
parallel_group = "STUDIO"
supersedes = []
+++

# Artifact Builder

Construye artefactos completos en staging a partir de una especificación confirmada. Usa el generador y validador propios del tipo de artefacto; elimina placeholders antes del gate y devuelve un diff, tests y recibo de límites.
