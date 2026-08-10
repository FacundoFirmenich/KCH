+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-GENERATION-STAGED"
kind = "RULE"
version = "0.1.0"
title = "Staged artifact generation"
parent = "KCH-RULES"
children = []
authority_ceiling = ["DESIGN", "BUILD_STAGED", "VALIDATE"]
routines = ["specify", "generate", "validate", "seal_candidate"]
subroutines = ["select_artifact_contract", "materialize_complete_files", "reject_placeholders", "run_type_specific_gate", "emit_diff_and_receipt"]
native_exec_rules = []
supersedes = []
+++

# Generación en staging

Skills, herramientas, operadores, forks, mods, plugins y adaptadores se generan primero en un espacio aislado. El gate debe rechazar TODOs, placeholders, manifiestos incompletos, dependencias no declaradas y tests simulados. Un candidato sellado continúa inactivo hasta una decisión separada de instalación o promoción.
