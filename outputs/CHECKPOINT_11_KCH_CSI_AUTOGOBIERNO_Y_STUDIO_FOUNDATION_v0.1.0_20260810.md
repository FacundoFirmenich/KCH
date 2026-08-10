# CHECKPOINT 11 — KCH CSI Self-Governance y fundamento del Studio v0.1.0

Fecha: 2026-08-10

## Cambio de posición

KCH queda **mejor posicionado, pero todavía no instalable como sistema integral**. El diagnóstico del usuario era correcto: KCH 0.11 y el overlay proactivo carecían de gobierno jerárquico fundado en KwanCode/CSI sobre el propio KCH. No existían `HARNESS.md`, `AGENTS.md`, `RULES.md`, editor CSI, interfaz visual integral ni tejido federado de extensiones.

Esta fase corrige el primer vacío mediante una capa nueva y reversible: `KCH_CSI_SELF_GOVERNANCE_v0.1.0`. KCH 0.11 permanece congelado.

## Jerarquía vinculante materializada

1. `HARNESS.md`: constitución operativa, identidad, propósito, invariantes, jurisdicción, techo de autoridad y política de conflicto.
2. `AGENTS.md`: topología de agentes horizontales, simultáneos, categoriales y subjerárquicos.
3. `RULES.md`: plano semántico de reglas, rutinas y subrutinas.

Regla de resolución interna: `HARNESS > AGENTS > RULES`. Una capa inferior sólo especializa o restringe; nunca amplía autoridad ni redefine el objeto gobernante. Para permisos se usa la intersección más restrictiva. Las restricciones de sistema/plataforma y la decisión explícita del usuario conservan su precedencia externa.

## Qué se implementó realmente

- Parser estricto de Markdown con frontmatter TOML, sin dependencia YAML.
- Grafo CSI con hashes, padres/hijos y relaciones `GOVERNS`, `DELEGATES`, `SUPERVISES`, `DEFINES_RULE` y `CONSTRAINS`.
- Trece nodos: un HARNESS, planos AGENTS/RULES, cuatro agentes y seis reglas.
- Tres agentes de primer nivel horizontales y un constructor subjerárquico bajo CSI Studio Orchestrator.
- Validador de IDs, campos, referencias, ciclos, hijos declarados y no escalamiento de autoridad.
- Compilador determinista y lock de fuentes/artefactos.
- Proyección Codex consciente de pérdidas.
- Catálogos materiales de 11 tipos de artefacto y 14 proveedores de descubrimiento previstos, todos con estado explícito.
- Arquitectura completa del CSI Studio visual y Extension Fabric.

La autoridad de esta capa termina en `REQUEST_INSTALL`: puede inspeccionar, diseñar, construir en staging, validar, recomendar y solicitar instalación. No puede instalar, habilitar, publicar ni modificar hosts externos.

## Corrección crítica de compatibilidad

Codex soporta `AGENTS.md` de forma nativa y los concatena jerárquicamente por directorio, pero sólo incorpora un archivo por nivel. Por tanto, varios agentes CSI soberanos no se representan fielmente sólo con AGENTS.md. La proyección los aplana como instrucciones de host y preserva el grafo soberano aparte.

Las Rules nativas de Codex son archivos `.rules` Starlark para decidir qué comandos pueden ejecutarse fuera del sandbox. No equivalen a un `RULES.md` semántico. El compilador sólo generará reglas nativas cuando exista un mapeo exacto declarado. En v0.1.0 genera cero `prefix_rule`: no concede permisos de shell.

## Gates

Resultado: **PASS, 11/11 tests**.

Se verificó:

- jerarquía exacta `HARNESS > AGENTS > RULES`;
- cuatro agentes y seis reglas con rutinas/subrutinas reales;
- preservación de topología horizontal y subjerárquica;
- rechazo de escalamiento de autoridad;
- rechazo de referencias de hijos inconsistentes;
- compilación determinista;
- lock con hashes de fuentes y artefactos;
- negativa a sobrescribir directorios no generados;
- recibo explícito de pérdidas de la proyección Codex;
- ninguna concesión nativa de comandos;
- catálogos futuros rotulados `SPECIFICATION_ONLY`/`NOT_IMPLEMENTED`;
- KCH 0.11 y el estado PHL históricos intactos.

## CSI Studio visual fijado, no simulado

Arquitectura elegida:

- motor soberano Python, desacoplado de la vista;
- cliente de escritorio PySide6/Qt como primera opción, pendiente de gate de dependencia/licencia/empaquetado;
- API/eventos comunes para CLI, navegador local y paneles delgados de VS Code/Cline;
- cápsula KCH visible, compacta y desplegable;
- árbol CSI, inspector, grafo, diff, consola, tests, ventanas acoplables/flotantes y modales sólo para decisiones consecuenciales;
- modos `GUIDED_COMPLETE`, `ASSISTED` y `EXPERT`;
- flujo transaccional hasta candidato sellado, con instalación como decisión separada.

Artefactos previstos: skills, tools, MCP, operadores, agentes, reglas, KwanForks, mods, plugins, adaptadores y presets. Cada tipo exigirá un proveedor material con esquema, generador completo, validador, pruebas, proyección CSI y rollback. Un proveedor ausente producirá `UNAVAILABLE_PROVIDER`, no un toy genérico.

## Extension Fabric fijado

Fuentes iniciales:

- plugins/skills/hooks/MCP de Codex;
- VS Code Marketplace y Open VSX;
- MCP Registry y configuraciones locales;
- PyPI, npm, Conda;
- GitHub/GitLab releases;
- OCI/container registries;
- Winget/Homebrew/apt para runtimes;
- futuros adaptadores crates.io, Go modules, NuGet y Maven.

Elementos que no podían omitirse: inventario de hosts/runtimes, OAuth/secretos, licencias, SBOM, vulnerabilidades, firmas/attestations, lockfiles, caché offline, actualizaciones, compatibilidad, aislamiento y rollback.

La recomendación conservará carriles separados —adecuación, compatibilidad, autoridad, procedencia, mantenimiento, seguridad, licencia, coste/red, reproducibilidad y popularidad— sin fabricar un ranking global. Búsqueda, descarga, instalación, habilitación, autenticación y primera ejecución serán transiciones distintas.

## Qué NO está todavía implementado

- enforcement de esta jerarquía dentro del runtime KCH/Super-MCP;
- ejecución simultánea real de los agentes descritos;
- aplicación del grafo en SCO;
- CSI Studio visual;
- generadores guiados de skills/tools/operators/forks/mods;
- buscador/recomendador MCP;
- proveedores PyPI/npm/marketplaces;
- instalación plug-and-play, verificación o rollback reales;
- adaptadores VS Code/Cline u otros hosts;
- PHL real.

Por ello, tener el grafo y el compilador no demuestra gobernanza operacional efectiva, ergonomía, calidad recomendatoria ni instalación robusta.

## Custodia y hashes

- Grafo CSI: `2a19eb48af091526fbccc14a36ba37b9bb90bdf5743ce9a5e1f1e8943b7eea46`.
- HARNESS: `907fbce94e4cf5bf7e7ac4e0f22251e5862605422e12abfd3685ee63acf72988`.
- Gate result: `be4cf4116460b12e23362f5f7806f63b420271edaf72f0c309cbdf18e3b9fea5`.
- Manifest: `d331f2f404e257d750ca16edadc7f99ee66d8d7a533d440412173f1f321bcd42`.
- ZIP: `590ad1e30d62ba0bd29f2976a7d461e0478d16f11bb12354d81e91044cacb27f` (40 miembros; CRC íntegro).
- KCH 0.11: `a4e08bb2833dffbfe3a3f2036579d1c8e56c20ea67ec94d4685a3618d528ee02`, sin cambio.
- Estado PHL: `d17a982e55203cdce6ffba1a2a2455260bea1df88536ac4456969ae755a07c21`, sin cambio.
- Entornos externos modificados: `0`.

## Claim máximo

`EXECUTABLE_KCH_CSI_SELF_GOVERNANCE_FOUNDATION_WITH_LOSS_AWARE_CODEX_PROJECTION_NO_INSTALLATION`

## Siguiente acción crítica

Construir **CSI Studio Kernel v0.1** sobre este compilador: máquina transaccional de sesiones guiadas, registro `ArtifactProvider` y dos verticales completas en staging —una skill real y una herramienta/servidor MCP real— con diff, tests, sello candidato y plan de instalación sin ejecutar. Inmediatamente después debe conectarse una primera carcasa PySide6 a ese backend real. Sólo entonces corresponde añadir el inventario local read-only y los primeros proveedores MCP/PyPI/npm.

## Fuentes técnicas oficiales

- Codex AGENTS: `https://learn.chatgpt.com/docs/agent-configuration/agents-md`.
- Codex Rules: `https://learn.chatgpt.com/docs/agent-configuration/rules`.
- Codex MCP: `https://learn.chatgpt.com/docs/extend/mcp?surface=cli`.
- Plugins/MCP/UI: `https://developers.openai.com/plugins/build/mcp-server`.
