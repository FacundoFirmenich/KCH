# START HERE — KCH pre-2G después de PHL gate y SCO v0.1.0

## Estado canónico de esta continuación

1. El estado personal PHL fuente sigue inalterado, con 7 decisiones y 0 feedback.
2. El gate de integración efectiva PHL↔KCH v0.2.0 cerró `PASS_BOUNDED`, 16/16.
3. SCO v0.1.0 está implementado, probado, empaquetado e instanciado con dos tareas Codex reales.
4. El gate SCO cerró `PASS_BOUNDED`, 23/23, con 21/21 pruebas unitarias.
5. El registro federado sucesor v0.5.0 contiene 18 renglones y conserva la rama QAS/CAS en cuarentena.
6. SCO es un candidato de integración KCH; no una admisión global ni una demostración de transporte vivo multiherramienta.

## Fuente y artefactos rectores

- Fuente nativa histórica: `codex://threads/019fd938-8000-7121-9078-d196bdd15ae4`.
- Tarea de construcción SCO: `codex://threads/019fe6b4-c2dd-7880-847e-d1fd16ea67a2`.
- Matriz vinculante: `SCO_vs_PROJECTS_CLASICOS_MATRIZ_DE_ACEPTACION_v0.1.0.md`.
- Resultado PHL: `PHL_EFFECTIVE_INTEGRATION_RESULT_v0.2.0.json`.
- Resultado SCO: `SCO_VALIDATION_RESULT_v0.1.0.json`.
- Bundle real: `SCO_KCH_PRE2G_PORTABLE_BUNDLE_v0.1.0.json`.
- Lowering CSI: `SCO_KCH_PRE2G_CSI_LOWERING_v0.1.0.json`.
- Descriptor KCH: `SCO_KCH_INTEGRATION_DESCRIPTOR_v0.1.0.json`.
- Registro sucesor: `KCH_SUPER_MCP_FEDERATED_REGISTRY_v0.5.0.json`.
- Release completo: `KCH_SUPERCHATS_ORCHESTRATORS_v0.1.0_RELEASE.zip`.

## Claims vigentes

Demostrado:

- orquestación local soberana y no fusionante;
- dos URIs Codex reales agrupadas en un grafo funcional;
- autoridad separada, órdenes, recibos, dependencias, adversos y conflictos;
- exportación sin contenido/memoria nativos;
- lowering CSI reproducible con primitivas existentes;
- wheel instalable y capaz de leer el estado validado.

No demostrado:

- despacho vivo autónomo ni receipt-binding contra respuesta nativa;
- conectores vivos Cline/Cowork/OpenCode/ChatGPT;
- adapter SCO → `kch.reviewable-decision.v0.2.0`;
- rutas SCO registradas en Super-MCP;
- operación distribuida/multihost;
- superioridad empírica de resultados frente a Projects.

## Próxima acción crítica

Prerregistrar y ejecutar `GATE_SCO_CODEX_LIVE_TRANSPORT_AND_KCH_DECISION_ADAPTER_v0.2.0` sobre una tarea Codex explícitamente escribible. La fuente histórica permanecerá read-only. La elección del target o la autorización para crear una tarea desechable es la única decisión del usuario necesaria antes de la escritura viva.
