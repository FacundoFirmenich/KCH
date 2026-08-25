# Formato LIBRESOURCE v0.1.0

Schema canónico inicial: `kch.libresource.package.v0.1.0`.

## Sobre obligatorio

Cada paquete contiene:

- identidad, versión y zona;
- hashes de contenido y contratos CSI;
- SBOM y procedencia;
- dependencias, roles, jurisdicciones, carácter constitutivo y alternativas;
- capacidades y permisos solicitados;
- autoridad inicial `NONE`;
- recetas de construcción y plataformas;
- seis rutas `NATIVE/IMPORT/EXPORT/COEXIST/REPLACE/ROLLBACK` con evidencia;
- estado exportable, migraciones, pruebas de conformidad y recuperación;
- licencia y firmas reemplazables;
- política humana que prohíbe discriminación por nacionalidad.

Además declara expresamente:

- contrato de capacidades con núcleo común, extensiones namespaced y degradación visible;
- representación del estado canónico con exportación, restauración y verificación;
- implementación de referencia y rutas alternativas, sin plataforma constitucionalmente canónica;
- ocho dimensiones separadas de compatibilidad: sintáctica, semántica, de estado, operacional, agéntica, de autoridad, histórica e inversa;
- por cada dependencia: tipo de recurso, función, jurisdicción, autoridad, carácter constitutivo, alternativas y ruta de retirada.

## Reglas

1. Una versión de nodo es inmutable por identidad lógica: una modificación crea versión sucesora.
2. El contenido se serializa como JSON UTF-8 canónico para sellado lógico. El contenedor físico futuro puede cambiar sin alterar la semántica.
3. Un hash encadenado local detecta alteraciones; no demuestra inmutabilidad física ni anclaje externo.
4. Los formatos de proveedor sólo aparecen dentro de adaptadores o extensiones namespaced.
5. Una capacidad sin equivalencia se declara como degradada o no disponible; nunca se simula soporte.
6. La exportación debe ser completa, legible y verificable; la importación no puede conceder autoridad implícita.
7. Las firmas y primitivas criptográficas se identifican algorítmicamente y admiten migración.

## Ejemplo estructural mínimo válido

```json
{
  "schema": "kch.libresource.package.v0.1.0",
  "node_id": "example-node",
  "version": "1.0.0",
  "zone": "FOREIGN_CAPABILITY_ZONE",
  "initial_authority": "NONE",
  "license": "SPDX-or-LIBRESOURCE-candidate-id",
  "state_export": "state/export.json",
  "content_hashes": ["sha256:..."],
  "csi_contracts": ["csi:example.v1"],
  "sbom": ["sbom/spdx.json"],
  "provenance": ["provenance/source.json"],
  "dependencies": [],
  "permissions": [],
  "build_recipes": ["build/reproducible.json"],
  "platforms": ["platform:declared"],
  "alternatives": [],
  "migrations": ["migration/export-import-v1"],
  "conformance_tests": ["test:round-trip"],
  "signatures": [],
  "capability_contract": {
    "core": ["example-capability"],
    "namespaced_extensions": ["vendor.example/advanced-capability"],
    "degradation_policy": "DECLARE_AND_PRESERVE"
  },
  "canonical_state": {
    "schema": "example.state.v1",
    "export": "state/export.json",
    "restore": "example:restore",
    "verification": "example:round-trip"
  },
  "platform_independence": {
    "reference_implementation": "platform:declared",
    "alternate_paths": [],
    "single_platform_is_canonical": false
  },
  "compatibility": {
    "SYNTACTIC": {"contract": "csi:compat:syntactic", "evidence_refs": []},
    "SEMANTIC": {"contract": "csi:compat:semantic", "evidence_refs": []},
    "STATE": {"contract": "csi:compat:state", "evidence_refs": []},
    "OPERATIONAL": {"contract": "csi:compat:operational", "evidence_refs": []},
    "AGENTIC": {"contract": "csi:compat:agentic", "evidence_refs": []},
    "AUTHORITY": {"contract": "csi:compat:authority", "evidence_refs": []},
    "HISTORICAL": {"contract": "csi:compat:historical", "evidence_refs": []},
    "INVERSE": {"contract": "csi:compat:inverse", "evidence_refs": []}
  },
  "routes": {
    "NATIVE": {"supported": true, "evidence_refs": ["test:native"]},
    "IMPORT": {"supported": true, "evidence_refs": ["test:import"]},
    "EXPORT": {"supported": true, "evidence_refs": ["test:export"]},
    "COEXIST": {"supported": true, "evidence_refs": ["test:coexist"]},
    "REPLACE": {"supported": true, "evidence_refs": ["test:replace"]},
    "ROLLBACK": {"supported": true, "evidence_refs": ["test:rollback"]}
  },
  "human_policy": {"nationality_discrimination": false}
}
```

Los puntos suspensivos del ejemplo representan un hash que debe ser real en un paquete ejecutado; el ejemplo no es un paquete conforme ni evidencia de un nodo existente.
