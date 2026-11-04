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
- **Solo unidades locales:** se rechazan las rutas de red, que entregarían el hash NTLM del usuario al servidor.
- **Registros sellados y firmados:** cada registro lleva el SHA-256 de su contenido y una firma Ed25519 con una clave
  protegida por DPAPI; un informe modificado no se importa.
- **Sello de tiempo externo (RFC 3161):** la fecha no depende del reloj del equipo. Solo se envía un hash.
- **Cadena de custodia encadenada:** cada evento incluye el hash del anterior y un ancla guarda el último; se detecta
  editar, borrar o recortar eventos.
- **Informe fuera de la evidencia:** el PDF no se puede guardar dentro de la carpeta ni en el disco que se hashea.
- **Actualizaciones firmadas:** cada versión publica `SHA256SUMS.txt` firmado con Ed25519. La app solo instala un
  `.exe` cuya firma sea válida con la clave pública que lleva dentro y cuyo SHA-256 coincida. La clave privada nunca
  sale del equipo del autor.
- **Sin enviar datos:** evidencias, registros e informes no salen del equipo. Las únicas conexiones son buscar
  actualizaciones en GitHub y pedir el sello de tiempo, y las dos se pueden desactivar en Ajustes.
- **Repositorio:** análisis de código con CodeQL, Dependabot (alertas y actualizaciones de seguridad),
  escaneo de secretos con protección al subir y la rama `main` protegida.

**Límites conocidos:** quien controle la cuenta del usuario puede firmar con su clave, aunque no obtener un sello de tiempo
con fecha anterior. La firma identifica una clave, no a una persona. El registro de custodia puede rehacerse entero por
quien controle el equipo: conserva una copia del PDF fuera de él.

## Versiones con soporte

Solo la última versión publicada en **Releases** recibe correcciones de seguridad.
