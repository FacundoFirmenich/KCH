+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-FULL-READ-SOURCE-ORDER"
kind = "RULE"
version = "0.1.0"
title = "Complete reading and native source order"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "VALIDATE"]
routines = ["read_all_bytes", "preserve_native_order", "declare_order_semantics", "verify_receipt_independently"]
subroutines = ["record_bytes", "record_physical_lines", "record_sha256", "reject_fragment_substitution", "compare_ordered_inventory", "preserve_adverse_mismatch"]
native_exec_rules = []
supersedes = []
+++

# Lectura completa y orden nativo

Cuando una misión exige lectura completa, búsquedas, fragmentos, previews y resúmenes sólo pueden localizar o auxiliar: nunca sustituyen `read_all_bytes` ni la evidencia equivalente de lectura íntegra.

Para archivos UTF-8 de la raíz estable, `full_read_file` materializa esta rutina mediante dos lecturas independientes y sólo habilita el claim si todo el contenido se transporta. Todo límite de transporte, denegación, discordancia de hash, cambio entre lecturas o archivo no textual queda como gate adverso; nunca se presenta como lectura completa.

Para inventarios de varios archivos, `full_read_batch` es la fuente del orden, los ordinals y los recibos: queda prohibida su reconstrucción manual. `full_read_verify_batch` vuelve a leer las fuentes y bloquea cualquier discordancia aun cuando el recibo alterado posea un autosellado canónico válido. Los claims semánticos específicos exigen spans literales preregistrados, localizados y verificados; el transporte completo de bytes no los autoriza por sí solo.

Todo recibo debe registrar método, bytes, líneas físicas, SHA-256 y límites. Los inventarios extraídos preservan por defecto el orden nativo/de fuente. Un orden alfabético, cronológico alternativo, por ranking u otra clave sólo es válido cuando el usuario lo pide o el contrato lo predeclara; la semántica de orden debe quedar explícita.

Antes del cierre se recomputa el recibo independientemente. Un conjunto completo con orden incorrecto se conserva como resultado adverso de representación: no puede rescatarse alegando equivalencia de conjuntos.
