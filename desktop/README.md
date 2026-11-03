# ForensiX Hash · app de escritorio (Windows)

Ventana WebView2 sin marco con la interfaz de `web/static`, la barra de título propia y:

- Diálogos de Windows para elegir archivo, carpeta o imagen de disco.
- Informes **PDF** generados directamente (WebView2 → PDF), sin pasar por el diálogo de impresión.
- Botón **Reiniciar como administrador** para leer discos completos (UAC).

```bash
python -m pip install -r desktop\requirements.txt
python -m desktop                     # en desarrollo
desktop\build_windows.bat             # dist\ForensiX-Hash.exe y dist\SHA256SUMS.txt
```

Requisitos: Windows 10/11 con **Microsoft Edge WebView2 Runtime** (viene instalado en Windows 11).

`make_icon.py` dibuja el logo y genera `assets/app.ico`, `docs/icon.png`, `docs/favicon.png` y
`docs/social.png`. `version_info.txt` son los datos de versión del `.exe`.
