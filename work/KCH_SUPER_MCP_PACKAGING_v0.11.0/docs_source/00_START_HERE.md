# Super-MCP de KCH 0.11 — punto de entrada

Este paquete explica el Super-MCP canónico contenido en KCH 0.11 y cómo desplegarlo como servidor MCP local por `stdio` en Cline, Codex o el soporte MCP nativo de Visual Studio Code.

## Qué se entrega

El Super-MCP es el plano federado de integración y gobierno de KwanCode Harness. Expone 49 herramientas MCP: 12 operaciones estables de orquestación, 9 operaciones de inspección federada y 28 controles reflexivos ejecutables. Publica además cuatro recursos MCP de solo lectura.

No es una fusión de componentes, memorias, chats, estados ni autoridades. Cada subsistema conserva su soberanía; el Super-MCP verifica identidades, evidencia, jurisdicción, capacidades y trazabilidad antes de permitir rutas federadas. En KCH 0.11 la ejecución mutante está prohibida y las rutas ejecutables son de solo lectura.

## Recorrido recomendado

1. Lea `01_QUE_ES_Y_QUE_NO_ES.md`.
2. Revise `02_ARQUITECTURA_Y_FLUJO.md` y `03_CATALOGO_DE_INTERFAZ.md`.
3. Ejecute el diagnóstico del paquete de runtime: `python -X utf8 launcher/doctor.py`.
4. Genere configuraciones absolutas: `python -X utf8 launcher/generate_client_configs.py --output-dir generated_configs`.
5. Siga `05_INSTALACION_Y_VERIFICACION.md` y la guía específica de su cliente.
6. Mantenga las aprobaciones automáticas desactivadas durante el uso inicial.

## Dos ZIP diferentes

- El ZIP de documentación contiene explicaciones, arquitectura, catálogo, instrucciones y plantillas revisables.
- El ZIP completo portable contiene el runtime real, los ocho wheels sellados, fuentes, pruebas, registro, evidencia portable, lanzadores, diagnóstico y documentación operacional mínima.

El ZIP documental no ejecuta KCH. El ZIP portable sí puede iniciar el servidor, pero sigue sujeto al techo de claims de KCH 0.11.

## Requisito mínimo

Python 3.11 o posterior. No es necesario instalar los wheels en el Python global: el lanzador los carga directamente desde el paquete portable.

## Estado de PHL

La interfaz expone únicamente `kch.phl.projection`, que lee y verifica una proyección integrada. Este paquete no inicia, alimenta, cierra ni promociona ninguna sesión PHL. La sesión PHL real solicitada por el usuario permanece deliberadamente aplazada.

