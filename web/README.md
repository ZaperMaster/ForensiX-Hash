# ForensiX Hash · versión web

Servidor local (FastAPI) con la misma interfaz que la app de escritorio, para usarla desde el navegador.

```bash
python -m pip install -r requirements.txt
python -m web            # http://127.0.0.1:8000
```

- Solo escucha en `127.0.0.1`. Toda la API (`/api/...`) exige la cabecera `X-ForensiX: 1` y un `Host` local.
- Para elegir archivos y carpetas, la web trae su propio explorador (el navegador no puede dar rutas).
- El **informe PDF** lo crea el servidor con Microsoft Edge sin ventana, en la carpeta elegida.
- Para leer **discos completos**, arranca el servidor desde una consola de administrador.
- Tema, idioma y actualizaciones se eligen en **Ajustes** (rueda dentada).

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/info` | Versión, algoritmos, carpeta de informes y permisos |
| GET | `/api/disks` | Discos y volúmenes |
| GET | `/api/browse?path=` | Contenido de una carpeta |
| POST | `/api/jobs` | Calcular, verificar y crear el PDF (`kind`, `target`, `algorithms`, `case`, `output`, `lang`) |
| GET / DELETE | `/api/jobs/{id}` | Progreso (y ruta del PDF al terminar) / cancelar |
| GET | `/api/records` | Registros |
| GET / DELETE | `/api/records/{id}` | Registro con su custodia e informes / eliminar de la lista |
| POST | `/api/records/{id}/verify` | Verificar de nuevo (`examiner`, `target`, `output`) |
| POST | `/api/records/{id}/pdf` | Crear otro PDF (`folder`, `lang`) |
| POST | `/api/open` | Abrir un PDF creado por la app o su carpeta |
| GET | `/api/custody` | Cadena de custodia y su comprobación |
| GET | `/api/update` | ¿Hay una versión nueva en GitHub? |
| GET | `/report/{id}` | Informe HTML (lo que se imprime en el PDF) |
