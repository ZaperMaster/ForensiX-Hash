# Historial de cambios

Todas las versiones de ForensiX Hash, de la más reciente a la más antigua. La última versión se descarga
en [Releases](https://github.com/ZaperMaster/ForensiX-Hash/releases/latest); la app se actualiza sola.

## 1.0.0 · 3 de noviembre de 2026

Primera versión estable.

- **Asistente por pasos**: evidencia → datos → hash → dónde guardar → proceso.
- **Hash de archivos, carpetas y discos**: disco físico completo, volúmenes e imágenes de disco, sector a sector y en
  solo lectura, con modelo, número de serie y conexión del disco.
- MD5, SHA-1, SHA-256, SHA-512, SHA3-256 y BLAKE2b, calculados a la vez en una sola lectura.
- **Verificación automática** con una segunda lectura y verificaciones posteriores (también de una copia en otra
  ruta), con archivos añadidos, eliminados y modificados en las carpetas.
- **Informe PDF** como comprobante en la carpeta elegida (nunca dentro de la evidencia), en español o inglés.
- **Registros sellados** y **cadena de custodia** encadenada por hashes.
- **Ajustes**: tema claro u oscuro (la primera vez, el de Windows); idioma; **actualizaciones automáticas firmadas** (Ed25519).
- App de escritorio para Windows a pantalla completa, versión web local y línea de comandos.
