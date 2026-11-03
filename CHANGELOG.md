# Historial de cambios

Todas las versiones de ForensiX Hash, de la más reciente a la más antigua. La última versión se descarga
en [Releases](https://github.com/ZaperMaster/ForensiX-Hash/releases/latest).

## 1.0.0 · 3 de noviembre de 2026

Primera versión estable.

- **Hash de archivos, carpetas y discos**: disco físico completo, volúmenes e imágenes de disco, sector a
  sector y en solo lectura, con modelo, número de serie y conexión del disco.
- MD5, SHA-1, SHA-256, SHA-512, SHA3-256 y BLAKE2b, calculados a la vez en una sola lectura.
- **Verificación automática** con una segunda lectura y verificaciones posteriores (también de una copia en
  otra ruta), con archivos añadidos, eliminados y modificados en las carpetas.
- **Datos del caso**: quién realiza el hash, organización, nº de caso y de evidencia, descripción y notas;
  fecha y hora del cálculo y de cada verificación.
- **Registros sellados** y **cadena de custodia** encadenada por hashes.
- **Informes** PDF, HTML, TXT, JSON, CSV y manifiestos `.md5`/`.sha1`/`.sha256`, en español e inglés.
- Importar un informe JSON para verificar la evidencia en otro equipo.
- App de escritorio para Windows, versión web local y línea de comandos.
