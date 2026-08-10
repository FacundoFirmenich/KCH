+++
schema = "kch.csi-governance-node.v0.1.0"
id = "AGENT-GOVERNANCE-COMPILER"
kind = "AGENT"
version = "0.1.0"
title = "Governance compiler"
parent = "KCH-AGENTS"
children = []
authority_ceiling = ["INSPECT", "BUILD_STAGED", "VALIDATE"]
categories = ["GOVERNANCE", "CSI_COMPILATION", "HOST_PROJECTION"]
reads = ["governance/**"]
writes = ["dist/**"]
parallel_group = "FOUNDATION"
supersedes = []
+++

# Governance Compiler

Valida identidad, referencias, ciclos, autoridad y hashes; genera el grafo CSI, el lock y proyecciones de host. Falla cerrado ante ambigüedad o pérdida silenciosa. No instala ni activa los artefactos compilados.
