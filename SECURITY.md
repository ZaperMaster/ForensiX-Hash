# Seguridad y uso responsable

## Uso responsable

ForensiX Hash es una herramienta **forense defensiva**: sirve para documentar la integridad de evidencias
digitales. Úsala solo sobre equipos, discos y archivos **propios** o para los que tengas **autorización**
(por ejemplo, dentro de un encargo pericial o de una investigación interna).

- Conecta los discos de evidencias reales a través de un **bloqueador de escritura**. La app solo abre
  la evidencia en modo lectura, pero el sistema operativo puede escribir en un volumen al montarlo.
- Revisa los resultados antes de incorporarlos a un informe pericial.

El autor no se hace responsable del uso indebido de la herramienta.

## Informar de una vulnerabilidad en ForensiX Hash

Si encuentras un fallo de seguridad **en la propia herramienta** (por ejemplo, en la API local, en las
actualizaciones, en el sello de los registros o en la cadena de custodia):

1. **No abras una issue pública.**
2. Usa la opción privada de GitHub: pestaña **Security → Report a vulnerability** de este repositorio.
3. Incluye los pasos para reproducirlo, la versión afectada («Acerca de») y el impacto que crees que tiene.
   **No adjuntes datos de evidencias reales.**

Intentaré responder en un plazo de 7 días y avisarte cuando esté corregido.

## Cómo se protege la app

- **Solo lectura:** archivos, carpetas y discos se abren en modo lectura; la app nunca escribe en la evidencia.
- **API solo local:** la versión web escucha únicamente en `127.0.0.1`, rechaza peticiones con un `Host`
  que no sea local (protección contra *DNS rebinding*) y exige la cabecera `X-ForensiX` en cada llamada,
  que una web ajena no puede enviar sin permiso CORS.
- **Registros sellados:** cada registro lleva el SHA-256 de su contenido; un informe JSON editado se marca
  como modificado y no se importa.
- **Cadena de custodia encadenada:** cada evento incluye el hash del anterior; borrar o editar uno se detecta.
- **Informe fuera de la evidencia:** el PDF no se puede guardar dentro de la carpeta ni en el disco que se hashea.
- **Actualizaciones firmadas:** cada versión publica `SHA256SUMS.txt` firmado con Ed25519. La app solo instala un
  `.exe` cuya firma sea válida con la clave pública que lleva dentro y cuyo SHA-256 coincida. La clave privada nunca
  sale del equipo del autor.
- **Sin enviar datos:** evidencias, registros e informes no salen del equipo. La única conexión es la consulta de
  actualizaciones a GitHub (se puede desactivar en Ajustes).
- **Repositorio:** análisis de código con CodeQL, Dependabot (alertas y actualizaciones de seguridad),
  escaneo de secretos con protección al subir y la rama `main` protegida.

**Límite conocido:** el sello y la cadena detectan cambios, pero no son una firma digital con clave privada.
Quien controle el equipo podría recalcularlos. Conserva una copia del informe fuera del equipo.

## Versiones con soporte

Solo la última versión publicada en **Releases** recibe correcciones de seguridad.
