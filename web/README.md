# ForensiX Hash · versión web

Servidor local (FastAPI) con la misma interfaz que la app de escritorio, para usarla desde el navegador.

```bash
python -m pip install -r requirements.txt
python -m web            # http://127.0.0.1:8000
```

- Solo escucha en `127.0.0.1`. Toda la API (`/api/...`) exige la cabecera `X-ForensiX: 1` y un `Host` local.
- Para elegir archivos y carpetas, la web trae su propio explorador (el navegador no puede dar rutas).
- El **PDF** se genera con el diálogo de impresión del navegador («Guardar como PDF») desde `/report/<id>`.
- Para leer **discos completos**, arranca el servidor desde una consola de administrador.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/info` | Versión, algoritmos y si hay permisos de administrador |
| GET | `/api/disks` | Discos y volúmenes |
| GET | `/api/browse?path=` | Contenido de una carpeta |
| POST | `/api/jobs` | Calcular y verificar (`kind`, `target`, `algorithms`, `case`) |
| GET / DELETE | `/api/jobs/{id}` | Progreso / cancelar |
| GET | `/api/records` | Registros |
| GET / DELETE | `/api/records/{id}` | Registro con su custodia / eliminar de la lista |
| POST | `/api/records/{id}/verify` | Verificar de nuevo (`examiner`, `target` opcional) |
| POST | `/api/records/{id}/export` | Informe (`html`, `txt`, `json`, `csv`, `md5`, `sha256`…) |
| POST | `/api/import` | Importar un informe JSON (se comprueba el sello) |
| GET | `/api/custody` | Cadena de custodia y su comprobación |
| GET | `/report/{id}` | Informe HTML (`?print=1` abre el diálogo de impresión) |
