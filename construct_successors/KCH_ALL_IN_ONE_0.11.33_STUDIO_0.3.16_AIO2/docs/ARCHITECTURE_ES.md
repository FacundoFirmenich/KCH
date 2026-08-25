# Arquitectura all-in-one

## Unidad física, pluralidad constitucional

El ZIP es único, pero no aplana sus componentes. La topología es:

1. **Linaje preservado:** snapshots R21 y R33 de sólo recuperación.
2. **Núcleo compartido:** KwanCode Harness 0.11.0, MIS 0.3.1, runtimes R33 y Studio 0.3.16.
3. **Proyección Codex:** plugin personal con un único lifecycle R33, 20 skills y dos servidores MCP de arranque gobernado.
4. **Proyección Cline/VS Code:** regla de proyecto y Super-MCP directo, con mezcla transaccional de configuración.
5. **Custodia:** manifiesto por archivo, procedencia por árbol, ZIP determinista y recibos de instalación.

La relación constitucional permanece:

`capability != support != permission != authority != execution != training`.

PHL permanece autorizado, pero no entrenado ni ejecutado. Studio y los adapters no crean autoridad científica ni operativa por instalación.

## Jurisdicción de los hosts

- Codex puede cargar skills y hooks nativos; MCP se usa únicamente para la superficie Studio/Super-MCP que no cabe en esas capas.
- Cline recibe rules y MCP. En Windows no se declara soporte de hooks hasta que el host lo soporte oficialmente.
- Ningún adapter es soberano: traduce el mismo núcleo y conserva provenance, permisos, locks y rollback.

## Rollback

El instalador nunca borra el predecesor. Antes de escribir crea un `.bak.<timestamp>`; cada recibo registra destino, hashes y backup. El rollback de AIO2 restaura la proyeccion anterior, incluido AIO1 cuando corresponda, sin reconstruir historia.
