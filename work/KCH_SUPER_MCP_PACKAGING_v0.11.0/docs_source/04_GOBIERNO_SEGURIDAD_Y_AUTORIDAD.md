# Gobierno, seguridad y autoridad

## Invariante rector

`capacidad != permiso != soporte != autoridad != ejecución`.

Que un cliente vea una herramienta significa que el servidor declara una capacidad. Que el esquema acepte argumentos significa soporte de interfaz. La autoridad exige además objetivo, actor, jurisdicción, evidencia, controles y capacidad válidos. La ejecución sólo existe si la ruta y el perfil la permiten.

## Perfil recomendado

Todas las plantillas usan `agent-shadow`. `minimal` y `research` pueden servir a gates controlados; `enforced` está prohibido en KCH 0.11 hasta superar gates posteriores. No edite el código para saltar esa prohibición.

## Aprobaciones del cliente

- Cline se entrega con `autoApprove: []`.
- Codex se entrega con `default_tools_approval_mode = "prompt"`.
- VS Code mostrará su propia solicitud de confianza para servidores MCP.

No amplíe aprobaciones automáticas durante la primera instalación. La ausencia de mutación en KCH 0.11 reduce el riesgo, pero no elimina la exposición de metadatos, rutas, evidencia o contexto al cliente y al modelo que invoque las herramientas.

## Estado local

El ledger nuevo se crea fuera del bundle canónico, bajo `runtime/state`. Nunca reemplace la base histórica de evidencia incluida en `bundle/evidence`. Haga copia del ledger si necesita conservar una campaña y verifique su hash antes y después de transportarlo.

## Secretos

El paquete no contiene secretos persistentes. El HMAC efímero del lanzador protege capacidades dentro del proceso actual. Si define `KCH_011_HMAC_SECRET`, hágalo mediante el almacén seguro del entorno, nunca en una plantilla compartida, captura de pantalla, commit o ZIP.

## Protección de la evidencia

1. Ejecute `launcher/doctor.py` antes de configurar el cliente.
2. Conserve el ZIP original y su SHA-256.
3. Use `kch.super.registry.evidence.audit` para recalcular la evidencia portable.
4. No interprete `PASS` de hashes como prueba de que el claim original era correcto; prueba identidad de bytes respecto del registro.
5. Preserve resultados adversos y `ABSTAIN`/`UNAVAILABLE` en la auditoría.

## Riesgos que siguen abiertos

- No hay demostración de seguridad frente a todos los clientes, plugins o extensiones del host.
- No hay gate Linux completo en esta entrega.
- El sandbox MCP nativo de VS Code no está disponible en Windows según la documentación actual de VS Code; la confianza y el aislamiento del host siguen siendo relevantes.
- No se ha ejecutado una sesión PHL real.
- No se ha demostrado operación remota, multiusuario ni alta disponibilidad.
- No hay autoridad mutante y no debe simularse modificando la configuración.

