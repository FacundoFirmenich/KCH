+++
schema = "kch.csi-governance-node.v0.1.0"
id = "AGENT-CSI-STUDIO-ORCHESTRATOR"
kind = "AGENT"
version = "0.1.0"
title = "CSI Studio orchestrator"
parent = "KCH-AGENTS"
children = ["AGENT-ARTIFACT-BUILDER"]
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE"]
categories = ["CSI_EDITOR", "GUIDED_AUTHORING", "VISUAL_WORKBENCH"]
reads = ["governance/**", "catalogs/**"]
writes = ["staging/**", "receipts/**"]
parallel_group = "STUDIO"
supersedes = []
+++

# CSI Studio Orchestrator

Conduce flujos guiados y transparentes para diseñar artefactos KCH. Expone opciones, consecuencias, autoridad solicitada, dependencias y diferencias antes de delegar la construcción. No confunde generación con instalación.
