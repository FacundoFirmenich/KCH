# KCH Storage Governor v0.1.0

Gobernador de presión de almacenamiento, preservación mínima y migración verificable.

No es un limpiador autónomo. Separa diagnóstico, archivo, verificación remota y
eliminación. Una ruta sólo puede pasar a limpieza cuando existe un recibo que
identifica el archivo remoto y su tamaño; si el proveedor no expone un digest,
el límite queda declarado y se exige autorización explícita del usuario.

El primer uso real de este sucesor es la recuperación del agotamiento de C:
observado durante la integración completa de MIS 0.3.1.

