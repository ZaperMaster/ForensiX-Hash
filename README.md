# ForensiX Hash

[![Tests](https://github.com/ZaperMaster/ForensiX-Hash/actions/workflows/tests.yml/badge.svg)](https://github.com/ZaperMaster/ForensiX-Hash/actions/workflows/tests.yml)
[![CodeQL](https://img.shields.io/badge/CodeQL-activo-2dd4bf?logo=github)](https://github.com/ZaperMaster/ForensiX-Hash/security/code-scanning)
[![Versión](https://img.shields.io/github/v/release/ZaperMaster/ForensiX-Hash?label=versi%C3%B3n&color=2dd4bf)](https://github.com/ZaperMaster/ForensiX-Hash/releases/latest)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB?logo=python&logoColor=white)
[![Licencia: PolyForm Strict](https://img.shields.io/badge/licencia-PolyForm%20Strict-lightgrey)](LICENSE)
[![Web](https://img.shields.io/badge/web-zapermaster.github.io-2dd4bf)](https://zapermaster.github.io/ForensiX-Hash/)

Herramienta de **hashing forense** de la marca **ForensiX**: calcula los hashes de un **archivo**, una
**carpeta** o un **disco completo** (también pendrives, volúmenes e imágenes `.dd`/`.raw`/`.iso`),
los **verifica automáticamente** con una segunda lectura y genera un **informe** con los datos del caso:
quién lo hizo, cuándo se calculó y cuándo se verificó.

**Descargar:** [última versión](https://github.com/ZaperMaster/ForensiX-Hash/releases/latest) →
`ForensiX-Hash.exe` (con su `SHA256SUMS.txt` para comprobar la descarga). Novedades de cada versión:
[CHANGELOG.md](CHANGELOG.md). Web del proyecto: **[zapermaster.github.io/ForensiX-Hash](https://zapermaster.github.io/ForensiX-Hash/)**.

## Capturas

<p align="center">
  <img src="docs/capturas/resultado.png" alt="Registro verificado de un pendrive: hashes, datos del caso y cronología" width="900">
</p>

| Nuevo hash | Elegir un disco |
|---|---|
| ![Formulario con el tipo de evidencia, los datos del caso y los algoritmos](docs/capturas/nuevo.png) | ![Lista de discos y volúmenes con modelo, número de serie y conexión](docs/capturas/discos.png) |

| Progreso | Informe PDF |
|---|---|
| ![Cálculo y verificación con velocidad y tiempo restante](docs/capturas/progreso.png) | ![Informe con el resultado, los hashes, la cronología y las firmas](docs/capturas/informe.png) |

<sub>Pruebas con un pendrive USB SanDisk de 64 GB del propio autor.</sub>

## Qué incluye

**Tres tipos de evidencia**
- **Archivo**: hashes, tamaño y marcas de tiempo del sistema de archivos (creado, modificado, último acceso).
  Avisa si el archivo cambia mientras se lee.
- **Carpeta**: hash de cada archivo y de la carpeta entera (ver [cómo se calcula](#hash-de-una-carpeta)),
  sin seguir enlaces ni uniones. Anota los archivos que no se pueden leer.
- **Disco**: el disco físico entero (`\\.\PhysicalDriveN`), un volumen (`\\.\D:`) o una imagen de disco,
  sector a sector y en **solo lectura**. Muestra modelo, número de serie, conexión (USB, NVMe, SATA…) y
  tabla de particiones. Los sectores ilegibles se leen como ceros y se anotan, como en las herramientas de
  adquisición forense.

**Hashes verificados**
- MD5, SHA-1 y SHA-256 por defecto; también SHA-512, SHA3-256 y BLAKE2b.
- Todos los algoritmos se calculan **a la vez en una sola lectura**, en paralelo.
- Al terminar, la evidencia se **lee otra vez** y los hashes deben coincidir: el resultado es
  **VERIFICADO** o **NO COINCIDE**.
- Se puede **volver a verificar** cuando se quiera (por otra persona, en otro momento, o una **copia** en
  otra ruta). En una carpeta se indican los archivos **añadidos, eliminados y modificados**.
- **Comparar** con un hash conocido pegándolo.

**Datos del caso y cronología**
- Quién realiza el hash, organización, nº de caso, nº de evidencia, descripción y notas.
- Fecha y hora (con zona horaria) del cálculo y de cada verificación, con su duración, quién la hizo y en
  qué equipo.
- Equipo, usuario, sistema operativo y versión de la herramienta.

**Integridad y cadena de custodia**
- Cada registro lleva un **sello** (SHA-256 del registro): si alguien edita el JSON —un hash, una fecha, un
  nombre— la app lo marca como **MODIFICADO**.
- **Cadena de custodia**: cada operación (hash creado, verificado, informe exportado, importado) queda en un
  registro donde cada evento incluye el hash del anterior. Si se borra o edita un evento, la cadena se rompe
  y se ve en qué punto.

**Informes**
- **PDF** e **HTML** imprimibles, con el resultado, los datos del caso, la evidencia, los hashes, la
  cronología, la cadena de custodia, el sello y espacio para **firmas**.
- **TXT**, **JSON** (se puede importar en otro equipo para verificar allí), **CSV** (un archivo por fila)
  y manifiestos **`.md5` / `.sha1` / `.sha256`** compatibles con `md5sum -c` / `sha256sum -c`.
- En **español e inglés**.

## Tres formas de usarlo

Comparten el mismo motor (`forensix_hash/`):

| | Qué es | Dónde está | Cómo se arranca |
|---|---|---|---|
| **App de escritorio** | Programa de Windows (`ForensiX-Hash.exe`) | [`desktop/`](desktop/) | `python -m desktop` o el `.exe` |
| **Web** | Servidor local + interfaz en el navegador | [`web/`](web/) | `python -m web` → http://127.0.0.1:8000 |
| **Línea de comandos** | Para scripts y automatización | [`forensix_hash/cli.py`](forensix_hash/cli.py) | `python -m forensix_hash` |

```bash
python -m forensix_hash file  informe.pdf --examiner "Ana Pérez" --case 2026-0001 --out informe.html
python -m forensix_hash dir   C:\Evidencias\EV-02 --examiner "Ana Pérez" --out ev02.sha256
python -m forensix_hash disks
python -m forensix_hash disk  \\.\PhysicalDrive1 --examiner "Ana Pérez" --evidence EV-01 --out ev01.html
python -m forensix_hash verify <id-del-registro> --examiner "Luis Gómez"
python -m forensix_hash custody
```

> Leer un **disco completo** necesita permisos de **administrador**. La app avisa y ofrece reiniciarse
> como administrador. Para evidencias reales, conecta el disco con un **bloqueador de escritura**.

## Hash de una carpeta

El hash de una carpeta es el **hash de su manifiesto**: el texto con una línea `hash  ruta` por archivo,
ordenado por ruta (rutas relativas con `/` y Unicode normalizado). Así:

- No depende de dónde esté la carpeta ni del sistema operativo.
- Cambia si se modifica, añade, elimina **o renombra** un archivo.
- Se puede comprobar con cualquier herramienta, sin ForensiX Hash:

```bash
cd carpeta
sha256sum -c ../manifiesto.sha256      # cada archivo
sha256sum ../manifiesto.sha256         # = hash SHA-256 de la carpeta en el informe
```

## Dónde se guardan los datos

En `%LOCALAPPDATA%\ForensiX Hash\` (Windows) o `~/.local/share/forensix-hash/` (Linux):
`records/` (un JSON sellado por evidencia) y `custody.jsonl` (la cadena de custodia). Se puede cambiar
con la variable de entorno `FORENSIX_HASH_HOME`. Nada sale del equipo: la app no se conecta a Internet.

## Desarrollo

```bash
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r desktop\requirements.txt
.venv\Scripts\python.exe -m pytest           # pruebas automáticas
.venv\Scripts\python.exe -m web               # versión web
.venv\Scripts\python.exe -m desktop           # app de escritorio
desktop\build_windows.bat                     # dist\ForensiX-Hash.exe + SHA256SUMS.txt
```

`desktop\requirements.txt` incluye todo lo de la web; para trabajar solo con la web o la línea de
comandos basta con `requirements.txt`. La página web del proyecto está en `docs/` (GitHub Pages desde
la carpeta `/docs`).

### Publicar una versión

1. Sube la versión en `forensix_hash/__init__.py` y `desktop/version_info.txt`.
2. Escribe las novedades en [CHANGELOG.md](CHANGELOG.md).
3. Ejecuta `desktop\build_windows.bat` y crea la Release con `dist\ForensiX-Hash.exe` y
   `dist\SHA256SUMS.txt`:

```bash
gh release create v1.0.0 dist/ForensiX-Hash.exe dist/SHA256SUMS.txt --title "ForensiX Hash v1.0.0" --notes-file notas.md
```

### Estructura

```
forensix_hash/            Motor (compartido por la app, la web y la línea de comandos)
  hasher.py               Varios algoritmos a la vez, en paralelo, en una sola lectura
  sources.py              Archivo, carpeta (manifiesto) y disco sector a sector
  devices.py              Discos y volúmenes del equipo, tamaño real y permisos
  engine.py               Cálculo + verificación automática y verificaciones posteriores
  record.py / store.py    Registro sellado y cadena de custodia
  report.py               Informes HTML, TXT, JSON, CSV y manifiestos (es/en)
  jobs.py / progress.py   Operaciones en segundo plano con progreso y cancelación
  cli.py                  Línea de comandos
web/                      Versión web       → ver web/README.md
  server.py               API local (FastAPI), solo en 127.0.0.1
  static/                 Interfaz (HTML, CSS y JavaScript)
desktop/                  App de escritorio → ver desktop/README.md
  window.py               Ventana WebView2, diálogos de Windows y PDF
  build_windows.bat       Crea dist\ForensiX-Hash.exe
docs/                     Página web del proyecto (GitHub Pages)
tests/                    Pruebas del motor, los informes, la línea de comandos y la API
```

## Seguridad

- La evidencia se abre **solo en modo lectura**; la app nunca escribe en ella.
- La API web solo escucha en `127.0.0.1`, comprueba que el `Host` sea local (contra *DNS rebinding*) y
  exige una cabecera propia en cada petición (una web ajena no puede llamarla).
- El código se revisa con **CodeQL**, las dependencias con **Dependabot** y el repositorio tiene
  **escaneo de secretos** con protección al subir. Ver [SECURITY.md](SECURITY.md).

> El sello y la cadena de custodia **detectan** cambios en los registros, pero no son una firma digital:
> quien tenga acceso al equipo podría recalcularlos. Guarda una copia del informe (PDF firmado o JSON) fuera
> del equipo, como en cualquier procedimiento de custodia.

## Licencia

[PolyForm Strict 1.0.0](LICENSE) © 2026 Alejandro Zapata. Todos los demás derechos reservados.

- **Sí se puede:** descargar y usar ForensiX Hash gratis para cualquier fin no comercial (uso personal,
  estudio, organizaciones sin ánimo de lucro, instituciones públicas…) y leer su código.
- **No se puede:** venderla ni usarla con fines comerciales, ni usar su código (copiarlo, modificarlo o
  reutilizarlo en otros proyectos) ni redistribuirla.

Las librerías de terceros incluidas en el `.exe` y sus licencias están en
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Autor

Hecho por [ZaperMaster](https://github.com/ZaperMaster) · parte de **ForensiX**.
