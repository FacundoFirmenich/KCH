# CHECKPOINT 12 — KCH CSI Studio Kernel y generadores v0.1.0

Fecha: 2026-08-10

## Posición sustantiva

KCH queda mejor posicionado que en el checkpoint anterior: el editor CSI ya no es únicamente una arquitectura documental. Existe un kernel Python transaccional, gobernado por el grafo compilado `HARNESS > AGENTS > RULES`, con once proveedores de artefactos, ledger SQLite hash-chain, custodia de bytes, estados no salteables y cliente visual Python conectado al mismo núcleo.

## Resultado observado

- Gate local: `8/8` pruebas PASS.
- Cobertura interna del gate: `11/11` tipos recorrieron `SPECIFIED -> GENERATED_STAGED -> VALIDATED -> SEALED_CANDIDATE`.
- Tipos ejercitados: Skill, Tool, MCP, Operator, Agent, Rule, KwanFork, Mod, Plugin, Host Adapter y Preset/KwanPrompts.
- Skills: inicialización real mediante `skill-creator/scripts/init_skill.py` y validación mediante `quick_validate.py`.
- Plugins: scaffold real mediante `plugin-creator/scripts/create_basic_plugin.py`, skill empaquetada y validación mediante `validate_plugin.py`.
- UI: `tkinter/ttk 8.6.15`, cuatro superficies conectadas — editor guiado, grafo de gobierno, Extension Fabric e instalación aislada — con smoke real.
- MCP Studio: inicialización, catálogo de once tools y consulta de estado verificadas.
- Consentimiento de instalación: cuatro decisiones exactas — Sí, No, Nunca en esta sesión, Siempre en esta sesión — probadas junto con verificación y rollback aislado.

## Resultado adverso preservado y corrección

La primera ejecución fue `7 PASS / 1 FAIL`. El fallo ocurrió al escribir un binding en una ruta pytest profunda de Windows: el inicializador oficial había devuelto éxito, pero la ruta completa agotaba el presupuesto práctico del filesystem. La corrección no ocultó el resultado:

1. verificación obligatoria de bytes y manifiesto inmediatamente después de los inicializadores oficiales;
2. UUID completo retenido en el ledger, con proyección compacta y collision-resistant en el filesystem;
3. gate explícito `WINDOWS_PATH_BUDGET_EXCEEDED` antes de generar en un root demasiado profundo;
4. rerun en staging corto controlado: `8/8 PASS`.

## Significado técnico y epistemológico

Se ha demostrado que los once proveedores pueden producir y validar candidatos locales bajo el mismo ciclo de gobierno. No se ha demostrado que todo artefacto futuro generado a partir de cualquier especificación sea correcto: los resultados valen para los contratos y casos forward incluidos. La igualdad de estado final no sustituye identidad de propósito, equivalencia de decisión, equivalencia de contrato probatorio, preservación de procedencia ni integridad de transporte; KwanFork mantiene estos campos separados.

## Límites de claim

Claim máximo vigente: `EXECUTABLE_TRANSACTIONAL_CSI_STUDIO_WITH_ELEVEN_VALIDATED_STAGED_GENERATORS_AND_PYTHON_VISUAL_CLIENT_NO_EXTERNAL_INSTALLATION`.

No está demostrado todavía:

- uso humano prolongado ni superioridad ergonómica frente a otras interfaces;
- instalación o funcionamiento en Codex, VS Code, Cline u OpenCode externos;
- exhaustividad de compatibilidad host;
- calidad de recomendación con fuentes de red vivas;
- seguridad de terceros por presencia en un registro;
- ejecución simultánea real de agentes;
- PHL real, que permanece expresamente no ejecutado.

## Artefactos cambiados

- `work/KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0/src/kch_studio/`
- `work/KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0/tests/`
- este checkpoint.

## Siguiente acción crítica

Ejecutar el gate vivo de Extension Fabric contra PyPI, npm, el registro MCP oficial y Open VSX; conservar indisponibilidades y campos `NOT_ESTIMABLE`; después cerrar instalación aislada/adaptadores e integrar la superficie en el Super-MCP sin modificar KCH 0.11 congelado.

