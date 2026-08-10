# Protocolo operativo — KCH-PREPILOT-FAILURES

- Fecha UTC: `2026-08-10T19:11:38.265835Z`
- Versión: `1`
- Ámbito: `KCH-PREPILOT-FAILURES`
- Pre-hash de evidencia: `db7ac2b8367156a1d152cf1db390ef8a1caecfda6a696bea884ae9e0be054278`
- Dominios: `COMPUTING, DEPLOYMENT, EPISTEMOLOGICAL, PARTICULAR, PROTOCOL, STATISTICAL`
- Estado: `GENERATED_FROM_DETECTED_EVIDENCE_REVIEW_REQUIRED`

Este protocolo sólo recompone evidencia detectada y enlazada. No convierte detección lexical en verdad ni reemplaza revisión humana.

## Pasos observados

- Corrección vinculante: ningún ensayo con arnés puede comenzar mediante una clase interna elegida ad hoc. Tiene que invocar primero la herramienta única `kch_preflight` del entrypoint canónico y conservar el recibo completo.  `[LESSON-fc521d5d-c25c-4ee8-81c7-112621fe3dc7 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Primero, congela y hashea el corpus, el prompt común, el rubric y la asignación de condiciones antes de despachar ninguna tarea.  `[LESSON-8eb8a351-61e3-4cf1-bea5-e19d76f83a39 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Primero, congela y hashea el corpus, el prompt común, el rubric y la asignación de condiciones antes de despachar ninguna tarea.  `[LESSON-e3b4cba1-7d58-4d6d-828f-f488e24d6fa6 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Segundo, arranca el brazo KCH exclusivamente por `kch_studio.mcp_server:StudioMCP`, llama `kch_preflight` y detén la ejecución si el gate no es `PASS`.  `[LESSON-8522a3d8-18c6-47cc-971e-dc89973e57ae · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Después, ejecuta ambos brazos con el mismo modelo, intensidad, corpus, red y límites de salida; la única diferencia admitida es la condición KCH predeclarada.  `[LESSON-7c2bb5a5-465a-45a5-b721-8c77cf79b056 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Después, ejecuta ambos brazos con el mismo modelo, intensidad, corpus, red y límites de salida; la única diferencia admitida es la condición KCH predeclarada.  `[LESSON-6e3177cc-ee27-4198-95eb-74cce041cddd · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Luego, persiste ambos recibos sin reescribir resultados adversos y evalúalos con un script determinista ciego a la narrativa de los agentes.  `[LESSON-19095a04-7c40-4495-84df-3f427cbdb795 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Decisión: `KCH-PREPILOT-001` se conserva como prepiloto descriptivo adverso. No se promueve a evidencia causal ni a validación industrial, aun después de reparar el entrypoint.  `[LESSON-350cdb80-efe7-4882-8169-f0194e8cbc2e · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Decisión: `KCH-PREPILOT-001` se conserva como prepiloto descriptivo adverso. No se promueve a evidencia causal ni a validación industrial, aun después de reparar el entrypoint.  `[LESSON-d4389be9-3487-4037-9d85-31129425a0de · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Decisión: `KCH-PREPILOT-001` se conserva como prepiloto descriptivo adverso. No se promueve a evidencia causal ni a validación industrial, aun después de reparar el entrypoint.  `[LESSON-72f503f8-82ab-4df5-8ffc-4147165fecb0 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`

## Fallos y correcciones que no deben repetirse

- Fallo observado: el protocolo del brazo KCH ordenó instanciar `KCHAdvancedRuntime`, que es un componente interno, en vez de arrancar el Super-MCP canónico mediante `StudioMCP`. La auditoría interna aplicó por error el alcance completo y devolvió `FAIL` por herramientas que sólo pertenecían a la composición host.  `[LESSON-4884e3a1-fd42-4cea-b3bd-713b5abd835d · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Fallo observado: el protocolo del brazo KCH ordenó instanciar `KCHAdvancedRuntime`, que es un componente interno, en vez de arrancar el Super-MCP canónico mediante `StudioMCP`. La auditoría interna aplicó por error el alcance completo y devolvió `FAIL` por herramientas que sólo pertenecían a la composición host.  `[LESSON-ec5ec249-8d7a-421b-8c79-8b5e53672b25 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Fallo observado: el protocolo del brazo KCH ordenó instanciar `KCHAdvancedRuntime`, que es un componente interno, en vez de arrancar el Super-MCP canónico mediante `StudioMCP`. La auditoría interna aplicó por error el alcance completo y devolvió `FAIL` por herramientas que sólo pertenecían a la composición host.  `[LESSON-cdb9214f-f3ee-4840-8400-703d5f07d656 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Fallo observado: el protocolo del brazo KCH ordenó instanciar `KCHAdvancedRuntime`, que es un componente interno, en vez de arrancar el Super-MCP canónico mediante `StudioMCP`. La auditoría interna aplicó por error el alcance completo y devolvió `FAIL` por herramientas que sólo pertenecían a la composición host.  `[LESSON-098b09e9-07ff-4146-bafa-78bd1291b568 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Fallo observado: el protocolo del brazo KCH ordenó instanciar `KCHAdvancedRuntime`, que es un componente interno, en vez de arrancar el Super-MCP canónico mediante `StudioMCP`. La auditoría interna aplicó por error el alcance completo y devolvió `FAIL` por herramientas que sólo pertenecían a la composición host.  `[LESSON-cd5e1b78-8627-4dcc-9bc8-6717d02d9280 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Fallo observado: el protocolo del brazo KCH ordenó instanciar `KCHAdvancedRuntime`, que es un componente interno, en vez de arrancar el Super-MCP canónico mediante `StudioMCP`. La auditoría interna aplicó por error el alcance completo y devolvió `FAIL` por herramientas que sólo pertenecían a la composición host.  `[LESSON-6573f5e5-7155-43e0-b39c-59589b10e36d · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Corrección vinculante: ningún ensayo con arnés puede comenzar mediante una clase interna elegida ad hoc. Tiene que invocar primero la herramienta única `kch_preflight` del entrypoint canónico y conservar el recibo completo.  `[LESSON-fd386b31-7542-41b8-930f-e368878827a1 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`

## Decisiones e invariantes

- Corrección vinculante: ningún ensayo con arnés puede comenzar mediante una clase interna elegida ad hoc. Tiene que invocar primero la herramienta única `kch_preflight` del entrypoint canónico y conservar el recibo completo.  `[LESSON-ca862d56-477c-43c6-9943-88ef85afff89 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Decisión: `KCH-PREPILOT-001` se conserva como prepiloto descriptivo adverso. No se promueve a evidencia causal ni a validación industrial, aun después de reparar el entrypoint.  `[LESSON-abc12d3a-5c20-43a0-a828-02f7b8d27998 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Decisión: `KCH-PREPILOT-001` se conserva como prepiloto descriptivo adverso. No se promueve a evidencia causal ni a validación industrial, aun después de reparar el entrypoint.  `[LESSON-2e0cf216-fa05-4f16-a620-0aa4db3ed461 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Decisión: `KCH-PREPILOT-001` se conserva como prepiloto descriptivo adverso. No se promueve a evidencia causal ni a validación industrial, aun después de reparar el entrypoint.  `[LESSON-c1ceb015-e07d-4b5f-b1cb-13735eba0f6a · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`

## Casos y particularidades

- Caso: `KCH-PREPILOT-001`.  `[LESSON-f5de79dd-cb38-45e3-92a4-a0324b941159 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Este caso no demuestra superioridad de KCH, valor humano, escalabilidad, seguridad abierta, selección BIND, contrato Venture Client ni validación industrial.  `[LESSON-d1518690-b153-4397-8e46-4bfc42d5eff0 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Este caso no demuestra superioridad de KCH, valor humano, escalabilidad, seguridad abierta, selección BIND, contrato Venture Client ni validación industrial.  `[LESSON-77759032-2d33-43d4-a427-2c0f8383c3df · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Este caso no demuestra superioridad de KCH, valor humano, escalabilidad, seguridad abierta, selección BIND, contrato Venture Client ni validación industrial.  `[LESSON-c133abef-5c04-4cd6-aa2b-e825fb2ff41b · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`

## Límites epistemológicos y de claims

- Después, ejecuta ambos brazos con el mismo modelo, intensidad, corpus, red y límites de salida; la única diferencia admitida es la condición KCH predeclarada.  `[LESSON-e8ef48d2-463c-4dfb-a8da-4a209e715df6 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Después, ejecuta ambos brazos con el mismo modelo, intensidad, corpus, red y límites de salida; la única diferencia admitida es la condición KCH predeclarada.  `[LESSON-94fc4a62-cd17-4115-9411-2cdc181992dc · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Finalmente, declara `NOT_ESTIMABLE` para el efecto de KCH si falla la integridad de condición, falta una réplica o el evaluador no está cegado. Una puntuación superior no rescata un gate experimental fallido.  `[LESSON-4e2ba604-7786-4b82-8fe1-9e027def137b · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Este caso no demuestra superioridad de KCH, valor humano, escalabilidad, seguridad abierta, selección BIND, contrato Venture Client ni validación industrial.  `[LESSON-74bf5faa-c582-4de4-8610-7fadb8db6e28 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Este caso no demuestra superioridad de KCH, valor humano, escalabilidad, seguridad abierta, selección BIND, contrato Venture Client ni validación industrial.  `[LESSON-3dd171a9-8fa3-458d-9d48-9c326667191b · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`
- Este caso no demuestra superioridad de KCH, valor humano, escalabilidad, seguridad abierta, selección BIND, contrato Venture Client ni validación industrial.  `[LESSON-c6217ce9-d8ae-4c0f-a507-edb371628158 · SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8]`

## Secretos y credenciales

Los valores secretos nunca se incorporan al protocolo. Sólo se admiten referencias externas y hashes no reversibles.

- Ninguna referencia secreta detectada.

## Trazabilidad

- `LESSON-f5de79dd-cb38-45e3-92a4-a0324b941159` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `50f4b980e5b032a460a550ef94b922854c89adf3aff266b7a1252d73d4cba524`
- `LESSON-4884e3a1-fd42-4cea-b3bd-713b5abd835d` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `8dd4b12b2d1eed7f9f3fc2fa9a22baf7285bdb40693370797a4eb18b457b5c6c`
- `LESSON-ec5ec249-8d7a-421b-8c79-8b5e53672b25` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `657f267b7e0d7de0e0529bc88e7911e5b8ba6985b9b9f29959941eec20b9a010`
- `LESSON-cdb9214f-f3ee-4840-8400-703d5f07d656` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `6c59339b5de75e25f2e69a87ba7fe898c7d2677f2679526a1e52ae8cdfd53f8f`
- `LESSON-098b09e9-07ff-4146-bafa-78bd1291b568` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `ded21b2b1b0e7752a5ccc7b93740228cf4ace7ea696349b07205ca2fe52e2e15`
- `LESSON-cd5e1b78-8627-4dcc-9bc8-6717d02d9280` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `e1f78d74da1194827c777f1579a8c039aa10d653e89e9c2d1c4069701c024507`
- `LESSON-6573f5e5-7155-43e0-b39c-59589b10e36d` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `158f6a4721486ac1b83d1220808936fec28c47d4fb3877be95d5b367c827f4ec`
- `LESSON-fd386b31-7542-41b8-930f-e368878827a1` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `568c29100590c040a52ff587a33c7af442d604563a58821c4460018202e572d5`
- `LESSON-fc521d5d-c25c-4ee8-81c7-112621fe3dc7` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `8634cf795b1d0a975fc73310f11f28f1393e3b16476ed42642ddf071504b4326`
- `LESSON-ca862d56-477c-43c6-9943-88ef85afff89` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `d3a286132d1d12a5202a8007e2b35a6032c69e7d34dd8c7e6923acda3d2e9c14`
- `LESSON-8eb8a351-61e3-4cf1-bea5-e19d76f83a39` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `e7687f632e9ef6e68e18399998bcac1d220b0257cdc6274f95812da7de5143de`
- `LESSON-e3b4cba1-7d58-4d6d-828f-f488e24d6fa6` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `452cb604bfc02f17472166a1b4d65fcd1fdb3ded69a16ea35f09741b1f449e07`
- `LESSON-8522a3d8-18c6-47cc-971e-dc89973e57ae` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `9eabc75e60f4de41a7f71ab08b59ff4255d698c1db5dec62dfe8820b928af881`
- `LESSON-7c2bb5a5-465a-45a5-b721-8c77cf79b056` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `2bcaf4f3cd0a8d99fbc701026a3d5c32abdbe3dcc3474a16ee9d157b473d87da`
- `LESSON-6e3177cc-ee27-4198-95eb-74cce041cddd` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `eadc43ace9a1de76b3ee6fe4e82553828038416b48f9dd198f5740db54b93ff4`
- `LESSON-e8ef48d2-463c-4dfb-a8da-4a209e715df6` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `da154d37fe1369160818501ed677480e4988396dd2d0348156b0b820539f1696`
- `LESSON-94fc4a62-cd17-4115-9411-2cdc181992dc` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `8368bd47976db3a5b1b12f7ec108b553f70f192fc5687eee6542d48eae3c9df4`
- `LESSON-19095a04-7c40-4495-84df-3f427cbdb795` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `2a4a461ac416af026a38dcf2b54bd51e4386296b8796d084430b55b543ebf5ea`
- `LESSON-4e2ba604-7786-4b82-8fe1-9e027def137b` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `ad0ad26c132a157622dbde19204b8d88548b41c7f1e0903e93c675617983b1b7`
- `LESSON-350cdb80-efe7-4882-8169-f0194e8cbc2e` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `f251e8e8f3582c4f275803facf4e362cfd818462a5ed81071caad0f566bebf2e`
- `LESSON-d4389be9-3487-4037-9d85-31129425a0de` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `d037734d05000f9e64ee0aa2e2fa4c7a7ec8763f93a8ede0bb074d4d5cc27f67`
- `LESSON-72f503f8-82ab-4df5-8ffc-4147165fecb0` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `db660a2c3498f6f070288c9ba9de60b4a1c293a50946e7e6420681c21739a7eb`
- `LESSON-abc12d3a-5c20-43a0-a828-02f7b8d27998` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `f877c3d1142daf3db1ed3a0dc2bbbfd81e8da6f7235fde171c06e2b0647e1af3`
- `LESSON-2e0cf216-fa05-4f16-a620-0aa4db3ed461` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `4ce5d8d7b2334e9e432f183ee533541ad312defc2af52c7e15469f6dfd7329a1`
- `LESSON-c1ceb015-e07d-4b5f-b1cb-13735eba0f6a` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `0b391a434f54ac073a49770264aaf5e47642be343ff1793a18b38cf93d9dbf3d`
- `LESSON-d1518690-b153-4397-8e46-4bfc42d5eff0` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `426f7bece191939f3d16651d449ed0dccbcc43ace5eb335ac29c9a7eaf8cad4e`
- `LESSON-77759032-2d33-43d4-a427-2c0f8383c3df` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `e222eeba205373f72fd384bcd3c2f8e96eb0258229ef1818dc2e3f462afb978c`
- `LESSON-c133abef-5c04-4cd6-aa2b-e825fb2ff41b` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `8efff50c47c21896814eb3c16bab266320f4d740bd76e97e2c2b92e0f5a3f63d`
- `LESSON-74bf5faa-c582-4de4-8610-7fadb8db6e28` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `28ca1d5bf022c5acdf4880f29d4c702d8428af87b47fa0c33fba8f7abdb97ad7`
- `LESSON-3dd171a9-8fa3-458d-9d48-9c326667191b` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `14b41e38f3d9be33802128a59692f9246d272ecd1883057993342328a0dc5068`
- `LESSON-c6217ce9-d8ae-4c0f-a507-edb371628158` ← `SOURCE-600a78bc-991d-4dff-9240-c632a87eb4d8` · `0ce16662c645f622b3715d336e90c4ff5917670b6647aea0154f925fce64b6b7`
